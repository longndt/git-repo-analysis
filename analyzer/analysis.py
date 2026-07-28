import re
from collections import Counter

import pandas as pd

# Explicit word forms per keyword (rather than a substring or \w* wildcard match,
# which also matched "add" inside "address" or "doc" inside "docker").
_KEYWORD_WORD_FORMS = {
    'fix': ['fix', 'fixes', 'fixed', 'fixing'],
    'bug': ['bug', 'bugs'],
    'feature': ['feature', 'features'],
    'add': ['add', 'adds', 'added', 'adding'],
    'update': ['update', 'updates', 'updated', 'updating'],
    'remove': ['remove', 'removes', 'removed', 'removing'],
    'refactor': ['refactor', 'refactors', 'refactored', 'refactoring'],
    'test': ['test', 'tests', 'tested', 'testing'],
    'doc': ['doc', 'docs'],
    'wip': ['wip'],
    'initial': ['initial'],
    'improve': ['improve', 'improves', 'improved', 'improving', 'improvement', 'improvements'],
    'clean': ['clean', 'cleans', 'cleaned', 'cleaning', 'cleanup'],
    'optimize': ['optimize', 'optimizes', 'optimized', 'optimizing', 'optimization'],
}
KEYWORDS = list(_KEYWORD_WORD_FORMS)
_KEYWORD_PATTERNS = {
    kw: re.compile(r'\b(?:' + '|'.join(re.escape(w) for w in forms) + r')\b')
    for kw, forms in _KEYWORD_WORD_FORMS.items()
}


def compute_line_totals(data):
    """Shared added/deleted totals, used by both the report and the AI prompt."""
    total_added = sum(item['lines_added'] for item in data)
    total_deleted = sum(item['lines_deleted'] for item in data)
    return total_added, total_deleted


def analyze_commit_messages(data):
    """Phan tich commit messages"""
    messages = [item['comments'] for item in data]
    messages_lower = [msg.lower() for msg in messages]

    keywords = Counter()
    for msg in messages_lower:
        for keyword, pattern in _KEYWORD_PATTERNS.items():
            if pattern.search(msg):
                keywords[keyword] += 1

    return {
        'keywords': dict(keywords),
        'avg_message_length': sum(len(msg) for msg in messages) / len(messages) if messages else 0,
        'short_messages_count': sum(1 for msg in messages if len(msg) < 10),
        'total_commits': len(messages)
    }


def detect_productivity_warnings(data, commit_analysis, message_analysis):
    """Phat hien cac canh bao ve productivity"""
    warnings = []

    df = pd.DataFrame(data)

    small_commits = sum(1 for item in data if item['lines_added'] + item['lines_deleted'] < 5)
    if small_commits / len(data) > 0.3:
        warnings.append({
            'level': 'WARNING',
            'message': f'Co {small_commits}/{len(data)} commits qua nho (< 5 lines). Nen gom commits lai.',
            'metric': 'small_commits_ratio',
            'value': f'{(small_commits/len(data)*100):.1f}%'
        })

    if message_analysis['short_messages_count'] / message_analysis['total_commits'] > 0.5:
        warnings.append({
            'level': 'WARNING',
            'message': f'Co {message_analysis["short_messages_count"]} commit messages qua ngan. Can mo ta ro hon.',
            'metric': 'poor_message_quality',
            'value': f'{(message_analysis["short_messages_count"]/message_analysis["total_commits"]*100):.1f}%'
        })

    if commit_analysis['total_commits'] < 5:
        warnings.append({
            'level': 'CRITICAL',
            'message': f'Chi co {commit_analysis["total_commits"]} commits. Qua it so voi mot du an.',
            'metric': 'low_commit_count',
            'value': commit_analysis['total_commits']
        })

    df['hour'] = pd.to_datetime(df['date-time']).dt.hour
    late_night_commits = sum(1 for hour in df['hour'] if hour >= 23 or hour <= 4)
    if late_night_commits / len(data) > 0.4:
        warnings.append({
            'level': 'INFO',
            'message': f'{late_night_commits} commits vao dem muon (23h-4h). Can quan ly thoi gian tot hon.',
            'metric': 'late_night_ratio',
            'value': f'{(late_night_commits/len(data)*100):.1f}%'
        })

    total_added = sum(item['lines_added'] for item in data)
    total_deleted = sum(item['lines_deleted'] for item in data)
    if total_added > 0 and total_deleted > total_added * 0.7 and len(data) > 10:
        warnings.append({
            'level': 'WARNING',
            'message': f'Ty le xoa code cao ({total_deleted} deleted vs {total_added} added). Co the thieu ke hoach.',
            'metric': 'high_deletion_ratio',
            'value': f'{(total_deleted/total_added*100):.1f}%'
        })

    return warnings
