import csv
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from analyzer.ai_analysis import analyze_with_ai
from analyzer.analysis import analyze_commit_messages, detect_productivity_warnings
from analyzer.charts import create_contribution_chart
from analyzer.config import GITHUB_TOKEN
from analyzer.github_client import fetch_commits, init_rest_client
from analyzer.report import create_student_directory, save_analysis_report, save_data
from analyzer.vietnamese import remove_vietnamese_accents

# matplotlib's pyplot state is process-global and not thread-safe; serialize
# chart creation when process_teams runs multiple students concurrently.
_CHART_LOCK = threading.Lock()


def _parse_student_rows(file_team):
    rows = []
    with open(file_team, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or len(row) < 2:
                continue
            if row[0].strip().lower() in ('student_name', 'name'):
                continue

            student_name = row[0].strip()
            repo_url = row[1].strip().replace(' ', '').rstrip('/').replace('.git', '')
            github_username = row[2].strip() if len(row) >= 3 and row[2].strip() else None

            if not student_name or not repo_url:
                continue

            url_parts = repo_url.split('/')
            if len(url_parts) < 2:
                print(f'Invalid URL: {repo_url}')
                continue

            repo_name = f'{url_parts[-2]}/{url_parts[-1]}'
            rows.append((student_name, repo_name, github_username))
    return rows


def process_student(student_name, repo_name, github_username, g, output_dir, model_name, skip_ai):
    print(f'\n{"="*80}')
    print(f'Processing: {student_name}')
    print(f'Repository: {repo_name}')
    if github_username:
        print(f'GitHub user: {github_username} (loc commit theo tac gia)')
    print(f'{"="*80}')

    data = fetch_commits(g, GITHUB_TOKEN, repo_name, author=github_username)
    if not data:
        print('No data - skipping')
        return

    total_lines = 0
    for item in data:
        total_lines += item['lines_added'] - item['lines_deleted']
        item['total_lines'] = total_lines

    student_name_normalized = remove_vietnamese_accents(student_name)
    student_dir = create_student_directory(student_name_normalized, base_dir=output_dir)

    print("Saving data...")
    save_data(data, os.path.join(student_dir, f'{student_name_normalized}.csv'))

    print("Analyzing...")
    commit_analysis = {'total_commits': len(data)}
    message_analysis = analyze_commit_messages(data)
    warnings = detect_productivity_warnings(data, commit_analysis, message_analysis)
    print(f"   Found {len(warnings)} warnings")

    print("Creating charts...")
    with _CHART_LOCK:
        create_contribution_chart(data, student_name_normalized, student_dir)

    ai_result = None
    if not skip_ai:
        print("AI analysis...")
        ai_result = analyze_with_ai(data, warnings, student_name, student_dir, message_analysis=message_analysis, model_name=model_name)

    print("Generating report...")
    save_analysis_report(student_name, data, commit_analysis, message_analysis, warnings, ai_result, student_dir)

    print("Completed")


def process_teams(file_team, output_dir='output', model_name='gemini-2.5-flash', skip_ai=False, workers=4):
    rows = _parse_student_rows(file_team)
    g = init_rest_client(GITHUB_TOKEN)

    if workers <= 1 or len(rows) <= 1:
        for student_name, repo_name, github_username in rows:
            process_student(student_name, repo_name, github_username, g, output_dir, model_name, skip_ai)
        return

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(process_student, student_name, repo_name, github_username, g, output_dir, model_name, skip_ai): student_name
            for student_name, repo_name, github_username in rows
        }
        for future in as_completed(futures):
            student_name = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f'Error processing {student_name}: {e}')
