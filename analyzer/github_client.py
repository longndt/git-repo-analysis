"""GitHub commit fetching.

Two code paths are supported:

- GraphQL (used whenever a GITHUB_TOKEN is configured): fetches commit
  ``additions``/``deletions`` in the same paginated query as the commit
  list, so a repo with N commits costs ~N/100 requests instead of N+1.
  The REST API's commit-list endpoint doesn't include stats, so PyGithub
  has to make one extra request per commit to lazily load ``commit.stats``.
- REST via PyGithub (used when there is no token, since the GraphQL API
  requires authentication): kept as the original implementation so
  unauthenticated usage (60 requests/hour) keeps working unchanged.
"""
import time
from datetime import datetime, timezone

import requests
from github import Github, Auth

GRAPHQL_URL = 'https://api.github.com/graphql'

_USER_ID_QUERY = """
query($login: String!) {
  user(login: $login) { id }
}
"""

_HISTORY_QUERY = """
query($owner: String!, $name: String!, $cursor: String, $author: CommitAuthor) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef {
      target {
        ... on Commit {
          history(first: 100, after: $cursor, author: $author) {
            pageInfo { hasNextPage endCursor }
            nodes {
              committedDate
              message
              additions
              deletions
              parents { totalCount }
              author { name }
            }
          }
        }
      }
    }
  }
}
"""

_RATE_LIMIT_QUERY = "query { rateLimit { remaining resetAt } }"


class GraphQLError(Exception):
    pass


def init_rest_client(token):
    if token and token.strip():
        g = Github(auth=Auth.Token(token.strip()))
        print("Using GitHub token - Rate limit: 5000 requests/hour")
    else:
        g = Github()
        print("No GitHub token - Rate limit: 60 requests/hour")
        print("   Add GITHUB_TOKEN to increase limit to 5000/hour")
        print("   Get token at: https://github.com/settings/tokens\n")
    return g


def _graphql_post(token, query, variables):
    resp = requests.post(
        GRAPHQL_URL,
        json={'query': query, 'variables': variables},
        headers={'Authorization': f'Bearer {token}'},
        timeout=30,
    )
    payload = resp.json()
    if resp.status_code != 200 or 'errors' in payload:
        raise GraphQLError(payload.get('errors') or resp.text)
    return payload['data']


def _is_rate_limited(error):
    errors = error.args[0] if error.args else None
    if isinstance(errors, list):
        return any(isinstance(e, dict) and e.get('type') == 'RATE_LIMITED' for e in errors)
    return False


def _wait_for_graphql_reset(token):
    try:
        data = _graphql_post(token, _RATE_LIMIT_QUERY, {})
        reset_at = datetime.fromisoformat(data['rateLimit']['resetAt'].replace('Z', '+00:00'))
        wait_seconds = max((reset_at - datetime.now(timezone.utc)).total_seconds(), 0)
    except Exception:
        wait_seconds = 60
    print(f"  Waiting {wait_seconds/60:.1f} minutes for GraphQL rate limit reset...")
    time.sleep(wait_seconds + 5)


def _resolve_author_id(token, username):
    if not username:
        return None
    data = _graphql_post(token, _USER_ID_QUERY, {'login': username})
    user = data.get('user')
    return user['id'] if user else None


def fetch_commits_graphql(token, repo_name, author=None, max_retries=3):
    owner, name = repo_name.split('/', 1)
    author_id = _resolve_author_id(token, author)
    author_filter = {'id': author_id} if author_id else None

    data_out = []
    cursor = None
    while True:
        variables = {'owner': owner, 'name': name, 'cursor': cursor, 'author': author_filter}
        try:
            data = _graphql_post(token, _HISTORY_QUERY, variables)
        except GraphQLError as e:
            if max_retries > 0 and _is_rate_limited(e):
                _wait_for_graphql_reset(token)
                return fetch_commits_graphql(token, repo_name, author=author, max_retries=max_retries - 1)
            raise

        repo = data.get('repository')
        if not repo or not repo.get('defaultBranchRef'):
            raise GraphQLError(f'Repository not found or has no commits: {repo_name}')

        history = repo['defaultBranchRef']['target']['history']
        for node in history['nodes']:
            if node['parents']['totalCount'] > 1:
                continue
            committed = datetime.fromisoformat(node['committedDate'].replace('Z', '+00:00'))
            data_out.append({
                'date-time': committed.strftime('%Y-%m-%d %H:%M:%S'),
                'who': node['author']['name'] if node['author'] else None,
                'comments': node['message'].replace('\n', ' ').strip(),
                'lines_added': node['additions'],
                'lines_deleted': node['deletions'],
            })

        page_info = history['pageInfo']
        if not page_info['hasNextPage']:
            break
        cursor = page_info['endCursor']

    return sorted(data_out, key=lambda x: x['date-time'])


def read_repo_rest(g, repo_name, author=None, max_retries=3):
    """Original REST fallback (one extra API call per commit for stats)."""
    try:
        repo = g.get_repo(repo_name)

        data = []
        commits = repo.get_commits(author=author) if author else repo.get_commits()

        for commit in commits:
            if len(commit.parents) > 1:
                continue

            commit_info = {
                'date-time': commit.commit.author.date.strftime('%Y-%m-%d %H:%M:%S'),
                'who': commit.commit.author.name,
                'comments': commit.commit.message.replace('\n', ' ').strip(),
                'lines_added': commit.stats.additions,
                'lines_deleted': commit.stats.deletions,
            }
            data.append(commit_info)

        return sorted(data, key=lambda x: x['date-time'])
    except Exception as e:
        error_msg = str(e)
        if '404' in error_msg:
            print("\n  Repository not found or is private.")
            print("     This script only works with public repositories.")
        elif '403' in error_msg or 'rate limit' in error_msg.lower():
            print("\n  Rate limit exceeded!")
            try:
                rate_limit = g.get_rate_limit()
                core = rate_limit.core
                reset_time = core.reset
                if reset_time.tzinfo is None:
                    reset_time = reset_time.replace(tzinfo=timezone.utc)
                wait_seconds = (reset_time - datetime.now(timezone.utc)).total_seconds()

                print(f"     Remaining requests: {core.remaining}/{core.limit}")
                print(f"     Rate limit resets at: {reset_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                print(f"     Need to wait: {wait_seconds/60:.1f} minutes")

                if 0 < wait_seconds < 3600 and max_retries > 0:
                    print(f"\n  Waiting {wait_seconds/60:.1f} minutes...")
                    time.sleep(wait_seconds + 10)
                    print(f"  Retrying: {repo_name}")
                    return read_repo_rest(g, repo_name, author=author, max_retries=0)
                else:
                    print("  Skipping repository")
                    return []
            except Exception as rate_check_error:
                print(f"     Could not check rate limit: {str(rate_check_error)}")
        else:
            print(f"\n  Error: {error_msg}")
        return []


def fetch_commits(g, token, repo_name, author=None):
    """Fetch commit history for repo_name, preferring the cheaper GraphQL path."""
    if token and token.strip():
        try:
            return fetch_commits_graphql(token.strip(), repo_name, author=author)
        except GraphQLError as e:
            print(f"  GraphQL fetch failed ({e}); falling back to REST API.")
        except requests.RequestException as e:
            print(f"  GraphQL request error ({e}); falling back to REST API.")
    return read_repo_rest(g, repo_name, author=author)
