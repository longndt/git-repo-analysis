import csv
import pandas as pd
from github import Github, Auth
from datetime import datetime, timezone
import matplotlib.pyplot as plt
from collections import Counter
import os
import time
import warnings as python_warnings
from dotenv import load_dotenv

# Suppress gRPC and ALTS warnings
python_warnings.filterwarnings('ignore')
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GLOG_minloglevel'] = '2'

# ==================== CONFIGURATION ====================
# Load environment variables from .env file
load_dotenv()

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')

def remove_vietnamese_accents(text):
    """Chuyển đổi tiếng Việt có dấu thành không dấu"""
    # Mapping cho các ký tự đặc biệt tiếng Việt
    vietnamese_map = {
        'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
        'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
        'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
        'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
        'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
        'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
        'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
        'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
        'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
        'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
        'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
        'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
        'đ': 'd',
        'À': 'A', 'Á': 'A', 'Ả': 'A', 'Ã': 'A', 'Ạ': 'A',
        'Ă': 'A', 'Ằ': 'A', 'Ắ': 'A', 'Ẳ': 'A', 'Ẵ': 'A', 'Ặ': 'A',
        'Â': 'A', 'Ầ': 'A', 'Ấ': 'A', 'Ẩ': 'A', 'Ẫ': 'A', 'Ậ': 'A',
        'È': 'E', 'É': 'E', 'Ẻ': 'E', 'Ẽ': 'E', 'Ẹ': 'E',
        'Ê': 'E', 'Ề': 'E', 'Ế': 'E', 'Ể': 'E', 'Ễ': 'E', 'Ệ': 'E',
        'Ì': 'I', 'Í': 'I', 'Ỉ': 'I', 'Ĩ': 'I', 'Ị': 'I',
        'Ò': 'O', 'Ó': 'O', 'Ỏ': 'O', 'Õ': 'O', 'Ọ': 'O',
        'Ô': 'O', 'Ồ': 'O', 'Ố': 'O', 'Ổ': 'O', 'Ỗ': 'O', 'Ộ': 'O',
        'Ơ': 'O', 'Ờ': 'O', 'Ớ': 'O', 'Ở': 'O', 'Ỡ': 'O', 'Ợ': 'O',
        'Ù': 'U', 'Ú': 'U', 'Ủ': 'U', 'Ũ': 'U', 'Ụ': 'U',
        'Ư': 'U', 'Ừ': 'U', 'Ứ': 'U', 'Ử': 'U', 'Ữ': 'U', 'Ự': 'U',
        'Ỳ': 'Y', 'Ý': 'Y', 'Ỷ': 'Y', 'Ỹ': 'Y', 'Ỵ': 'Y',
        'Đ': 'D'
    }

    result = ''
    for char in text:
        result += vietnamese_map.get(char, char)
    return result

# Initialize the GitHub object
if GITHUB_TOKEN and GITHUB_TOKEN.strip():
    auth = Auth.Token(GITHUB_TOKEN.strip())
    g = Github(auth=auth)
    print("✅ Using GitHub token - Rate limit: 5000 requests/hour")
else:
    g = Github()
    print("⚠️  No GitHub token - Rate limit: 60 requests/hour")
    print("   Add GITHUB_TOKEN to increase limit to 5000/hour")
    print("   Get token at: https://github.com/settings/tokens\n")

def read_repo(repo_name, author=None, max_retries=3):
    try:
        # Get the repository
        repo = g.get_repo(repo_name)

        data = []
        # Filter server-side by author when a GitHub username is provided
        if author:
            commits = repo.get_commits(author=author)
        else:
            commits = repo.get_commits()

        for commit in commits:
            # Skip merge commits (they have more than one parent)
            if len(commit.parents) > 1:
                continue

            commit_info = {
                'date-time': commit.commit.author.date.strftime('%Y-%m-%d %H:%M:%S'),
                'who': commit.commit.author.name,
                'comments': commit.commit.message.replace('\n', ' ').strip(),
                'lines_added': commit.stats.additions,
                'lines_deleted': commit.stats.deletions
            }
            data.append(commit_info)

        # Sort by date after collecting all commits
        return sorted(data, key=lambda x: x['date-time'])
    except Exception as e:
        error_msg = str(e)
        if '404' in error_msg:
            print(f"\n  ⚠ Repository not found or is private.")
            print(f"     This script only works with public repositories.")
            print(f"     Make sure the repository exists and is public.")
        elif '403' in error_msg or 'rate limit' in error_msg.lower():
            print(f"\n  ❌ Rate limit exceeded!")

            # Check current rate limit status
            try:
                rate_limit = g.get_rate_limit()
                core = rate_limit.core
                reset_time = core.reset
                # PyGithub may return a naive (UTC) or aware datetime; normalize to UTC
                if reset_time.tzinfo is None:
                    reset_time = reset_time.replace(tzinfo=timezone.utc)
                wait_seconds = (reset_time - datetime.now(timezone.utc)).total_seconds()

                print(f"     Remaining requests: {core.remaining}/{core.limit}")
                print(f"     Rate limit resets at: {reset_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                print(f"     Need to wait: {wait_seconds/60:.1f} minutes")

                if not GITHUB_TOKEN or not GITHUB_TOKEN.strip():
                    print(f"\n  💡 Add GitHub Token in .env to increase limit to 5000/hour")
                    print(f"     Get token at: https://github.com/settings/tokens")

                # Auto-retry if wait time is reasonable
                if 0 < wait_seconds < 3600 and max_retries > 0:
                    print(f"\n  ⏳ Waiting {wait_seconds/60:.1f} minutes...")
                    time.sleep(wait_seconds + 10)
                    print(f"  🔄 Retrying: {repo_name}")
                    return read_repo(repo_name, author=author, max_retries=0)
                else:
                    print(f"  ❌ Skipping repository")
                    return []

            except Exception as rate_check_error:
                print(f"     Could not check rate limit: {str(rate_check_error)}")
        else:
            print(f"\n  ❌ Error: {error_msg}")
        return []

def save_data(data, csv_file):
    # Create a DataFrame
    df = pd.DataFrame(data)
    df.to_csv(csv_file, index=False)
    print(f"Data saved to {csv_file}")

def create_student_directory(student_name, base_dir='output'):
    """Tạo thư mục riêng cho từng sinh viên"""
    student_dir = os.path.join(base_dir, student_name)
    if not os.path.exists(student_dir):
        os.makedirs(student_dir)
    return student_dir

def create_contribution_chart(data, student_name, output_dir):
    """Vẽ biểu đồ contribution (lines added/deleted over time)"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    df = pd.DataFrame(data)
    df['date-time'] = pd.to_datetime(df['date-time'])
    df['hour'] = df['date-time'].dt.hour
    df['day_of_week'] = df['date-time'].dt.day_name()

    fig, axes = plt.subplots(3, 2, figsize=(16, 12))
    fig.suptitle(f'Code Contribution Analysis - {student_name}', fontsize=16, fontweight='bold')

    # 1. Lines Added/Deleted Over Time
    ax1 = axes[0, 0]
    ax1.plot(df['date-time'], df['total_lines'], marker='o', linestyle='-', linewidth=2, markersize=4, color='#2E86AB')
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Total Lines')
    ax1.set_title('Cumulative Lines of Code Over Time')
    ax1.grid(True, alpha=0.3)
    ax1.tick_params(axis='x', rotation=45)

    # 2. Lines Added vs Deleted per Commit
    ax2 = axes[0, 1]
    ax2.bar(range(len(df)), df['lines_added'], alpha=0.7, label='Added', color='#06A77D')
    ax2.bar(range(len(df)), -df['lines_deleted'], alpha=0.7, label='Deleted', color='#D62828')
    ax2.set_xlabel('Commit Number')
    ax2.set_ylabel('Lines')
    ax2.set_title('Lines Added vs Deleted per Commit')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

    # 3. Commit Frequency by Date
    df_grouped = df.groupby(df['date-time'].dt.date).size()
    ax3 = axes[1, 0]
    ax3.bar(range(len(df_grouped)), df_grouped.values, color='#F77F00', alpha=0.7)
    ax3.set_xlabel('Date')
    ax3.set_ylabel('Number of Commits')
    ax3.set_title('Commit Frequency by Date')
    ax3.grid(True, alpha=0.3)

    # 4. Commit Frequency by Hour
    commits_per_hour = df.groupby('hour').size()
    ax4 = axes[1, 1]
    ax4.bar(commits_per_hour.index, commits_per_hour.values, color='#9B59B6', alpha=0.7)
    ax4.set_xlabel('Hour of Day')
    ax4.set_ylabel('Number of Commits')
    ax4.set_title('Commit Frequency by Hour of Day')
    ax4.set_xticks(range(0, 24, 2))
    ax4.grid(True, alpha=0.3)

    # 5. Average Lines Changed per Commit
    df['total_changes'] = df['lines_added'] + df['lines_deleted']
    ax5 = axes[2, 0]
    ax5.plot(range(len(df)), df['total_changes'], marker='o', linestyle='-', linewidth=2, markersize=4, color='#E63946')
    ax5.set_xlabel('Commit Number')
    ax5.set_ylabel('Total Lines Changed')
    ax5.set_title('Total Lines Changed per Commit')
    ax5.grid(True, alpha=0.3)

    # 6. Productivity Heatmap (Commits per Day of Week)
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    commits_per_weekday = df['day_of_week'].value_counts().reindex(day_order, fill_value=0)
    ax6 = axes[2, 1]
    bars = ax6.barh(commits_per_weekday.index, commits_per_weekday.values, color='#06A77D', alpha=0.7)
    ax6.set_xlabel('Number of Commits')
    ax6.set_title('Commits by Day of Week')
    ax6.grid(True, alpha=0.3, axis='x')

    plt.tight_layout()
    chart_path = os.path.join(output_dir, f'{student_name}_contribution_chart.png')
    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"  📊 Chart saved: {chart_path}")
    return chart_path

def analyze_commit_messages(data):
    """Phân tích commit messages"""
    messages = [item['comments'] for item in data]
    messages_lower = [msg.lower() for msg in messages]

    keywords = Counter()
    keyword_list = ['fix', 'bug', 'feature', 'add', 'update', 'remove',
                   'refactor', 'test', 'doc', 'wip', 'initial', 'improve', 'clean', 'optimize']

    for msg in messages_lower:
        for keyword in keyword_list:
            if keyword in msg:
                keywords[keyword] += 1

    return {
        'keywords': dict(keywords),
        'avg_message_length': sum(len(msg) for msg in messages) / len(messages) if messages else 0,
        'short_messages_count': sum(1 for msg in messages if len(msg) < 10),
        'total_commits': len(messages)
    }

def detect_productivity_warnings(data, commit_analysis, message_analysis):
    """Phát hiện các cảnh báo về productivity"""
    warnings = []

    df = pd.DataFrame(data)

    # Warning 1: Too many small commits
    small_commits = sum(1 for item in data if item['lines_added'] + item['lines_deleted'] < 5)
    if small_commits / len(data) > 0.3:
        warnings.append({
            'level': 'WARNING',
            'message': f'Có {small_commits}/{len(data)} commits quá nhỏ (< 5 lines). Nên gom commits lại.',
            'metric': 'small_commits_ratio',
            'value': f'{(small_commits/len(data)*100):.1f}%'
        })

    # Warning 2: Poor commit message quality
    if message_analysis['short_messages_count'] / message_analysis['total_commits'] > 0.5:
        warnings.append({
            'level': 'WARNING',
            'message': f'Có {message_analysis["short_messages_count"]} commit messages quá ngắn. Cần mô tả rõ hơn.',
            'metric': 'poor_message_quality',
            'value': f'{(message_analysis["short_messages_count"]/message_analysis["total_commits"]*100):.1f}%'
        })

    # Warning 3: Irregular commit pattern
    if commit_analysis['total_commits'] < 5:
        warnings.append({
            'level': 'CRITICAL',
            'message': f'Chỉ có {commit_analysis["total_commits"]} commits. Quá ít so với một dự án.',
            'metric': 'low_commit_count',
            'value': commit_analysis['total_commits']
        })

    # Warning 4: Late night commits (might indicate procrastination)
    df['hour'] = pd.to_datetime(df['date-time']).dt.hour
    late_night_commits = sum(1 for hour in df['hour'] if hour >= 23 or hour <= 4)
    if late_night_commits / len(data) > 0.4:
        warnings.append({
            'level': 'INFO',
            'message': f'{late_night_commits} commits vào đêm muộn (23h-4h). Cần quản lý thời gian tốt hơn.',
            'metric': 'late_night_ratio',
            'value': f'{(late_night_commits/len(data)*100):.1f}%'
        })

    # Warning 5: Code deletion ratio too high
    total_added = sum(item['lines_added'] for item in data)
    total_deleted = sum(item['lines_deleted'] for item in data)
    if total_deleted > total_added * 0.7 and len(data) > 10:
        warnings.append({
            'level': 'WARNING',
            'message': f'Tỷ lệ xóa code cao ({total_deleted} deleted vs {total_added} added). Có thể thiếu kế hoạch.',
            'metric': 'high_deletion_ratio',
            'value': f'{(total_deleted/total_added*100):.1f}%'
        })

    return warnings

def analyze_with_ai(data, warnings, student_name):
    """Phân tích dữ liệu bằng Gemini AI và đưa ra đánh giá"""

    # Check if API key is configured
    if not GEMINI_API_KEY or not GEMINI_API_KEY.strip() or GEMINI_API_KEY.strip() == "your_gemini_api_key_here":
        print("  ⚠️  Gemini API key chưa được cấu hình. Bỏ qua AI analysis.")
        print("     Để sử dụng AI analysis, thêm GEMINI_API_KEY vào file .env.")
        return None

    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')

        # Prepare data summary for AI
        df = pd.DataFrame(data)
        df['date-time'] = pd.to_datetime(df['date-time'])

        # Tính toán các metrics chi tiết
        total_added = sum(item['lines_added'] for item in data)
        total_deleted = sum(item['lines_deleted'] for item in data)
        net_lines = total_added - total_deleted
        avg_lines_per_commit = (total_added + total_deleted) / len(data)

        # Phân tích thời gian
        date_range_days = (df['date-time'].max() - df['date-time'].min()).days + 1
        commits_per_day = len(data) / date_range_days if date_range_days > 0 else 0

        # Phân tích commit messages
        all_messages = [item['comments'] for item in data]
        avg_msg_length = sum(len(msg) for msg in all_messages) / len(all_messages)

        # Phân tích patterns
        df['hour'] = df['date-time'].dt.hour
        df['date'] = df['date-time'].dt.date
        most_active_hour = df['hour'].mode()[0] if not df['hour'].mode().empty else 0
        most_active_day = df['date'].mode()[0] if not df['date'].mode().empty else None

        # Commits size distribution
        small_commits = sum(1 for item in data if (item['lines_added'] + item['lines_deleted']) < 10)
        medium_commits = sum(1 for item in data if 10 <= (item['lines_added'] + item['lines_deleted']) < 100)
        large_commits = sum(1 for item in data if (item['lines_added'] + item['lines_deleted']) >= 100)

        # Lấy commits đầu và cuối để thấy xu hướng
        first_5_commits = [item['comments'] for item in data[:5]]
        last_5_commits = [item['comments'] for item in data[-5:]]

        summary = {
            'student_name': student_name,
            'total_commits': len(data),
            'total_lines_added': total_added,
            'total_lines_deleted': total_deleted,
            'net_lines': net_lines,
            'date_range': f"{df['date-time'].min().strftime('%Y-%m-%d')} to {df['date-time'].max().strftime('%Y-%m-%d')}",
            'date_range_days': date_range_days,
            'commits_per_day': commits_per_day,
            'avg_lines_per_commit': avg_lines_per_commit,
            'avg_msg_length': avg_msg_length,
            'most_active_hour': most_active_hour,
            'commit_size_distribution': {
                'small': small_commits,
                'medium': medium_commits,
                'large': large_commits
            },
            'first_5_commits': first_5_commits,
            'last_5_commits': last_5_commits,
            'warnings': [w['message'] for w in warnings]
        }

        # Create prompt for AI
        prompt = f"""
Bạn là một chuyên gia phân tích Git và đánh giá kỹ năng lập trình của sinh viên. Hãy phân tích CHI TIẾT hiệu suất làm việc của sinh viên dựa trên dữ liệu Git commits sau:

========== THÔNG TIN TỔNG QUAN ==========
👤 Sinh viên: {summary['student_name']}
📊 Tổng số commits: {summary['total_commits']}
📅 Thời gian làm việc: {summary['date_range']} ({summary['date_range_days']} ngày)
⏱️ Tần suất commit: {summary['commits_per_day']:.2f} commits/ngày

========== PHÂN TÍCH CODE ==========
✅ Tổng dòng code THÊM: {summary['total_lines_added']:,} dòng
❌ Tổng dòng code XÓA: {summary['total_lines_deleted']:,} dòng
📈 Dòng code RÒNG (net): {summary['net_lines']:,} dòng
📏 Trung bình mỗi commit: {summary['avg_lines_per_commit']:.1f} dòng thay đổi

========== QUY MÔ COMMITS ==========
🔹 Commits nhỏ (< 10 dòng): {summary['commit_size_distribution']['small']} commits ({summary['commit_size_distribution']['small']/summary['total_commits']*100:.1f}%)
🔸 Commits trung bình (10-99 dòng): {summary['commit_size_distribution']['medium']} commits ({summary['commit_size_distribution']['medium']/summary['total_commits']*100:.1f}%)
🔺 Commits lớn (≥ 100 dòng): {summary['commit_size_distribution']['large']} commits ({summary['commit_size_distribution']['large']/summary['total_commits']*100:.1f}%)

========== THÓI QUEN LÀM VIỆC ==========
🕐 Giờ làm việc chủ yếu: {summary['most_active_hour']}:00

========== 5 COMMIT ĐẦU TIÊN ==========
{chr(10).join(f'{i+1}. "{msg}"' for i, msg in enumerate(summary['first_5_commits']))}

========== 5 COMMIT GẦN ĐÂY NHẤT ==========
{chr(10).join(f'{i+1}. "{msg}"' for i, msg in enumerate(summary['last_5_commits']))}

========== CẢNH BÁO TỰ ĐỘNG ==========
{chr(10).join(f'⚠️ {w}' for w in summary['warnings']) if summary['warnings'] else '✅ Không có cảnh báo đáng kể'}

========== YÊU CẦU PHÂN TÍCH ==========
Hãy đưa ra phân tích CHI TIẾT, CỤ THỂ và MẶT THỰC theo cấu trúc sau:

## 1. 📝 Đánh Giá Chất Lượng Commit Messages
- Phân tích độ rõ ràng, tính mô tả của các commit messages
- So sánh chất lượng messages đầu kỳ vs cuối kỳ (có cải thiện không?)
- Có tuân thủ quy ước commit messages chuẩn không? (ví dụ: conventional commits)
- Đưa ra ví dụ CỤ THỂ từ messages trên về messages tốt/xấu

## 2. 📊 Đánh Giá Tần Suất và Quy Mô Commits
- Tần suất {summary['commits_per_day']:.2f} commits/ngày có hợp lý không? (so với mức lý tưởng 1-3 commits/ngày cho dự án học tập)
- Phân bố quy mô commits có hợp lý không? (nên tập trung ở commits vừa phải)
- Có dấu hiệu "commit bombing" (nhiều commits nhỏ liên tiếp) hay "commit dumping" (ít commits nhưng quá lớn) không?
- Đánh giá về thói quen làm việc dựa trên giờ commit chủ yếu ({summary['most_active_hour']}:00)

## 3. 🎯 Đánh Giá Xu Hướng Phát Triển
- So sánh messages/code style đầu kỳ vs cuối kỳ: Có tiến bộ rõ rệt không?
- Tỷ lệ code added/deleted có hợp lý không? (tỷ lệ deleted quá cao = thiếu kế hoạch)
- Dự án có phát triển đều đặn hay làm dồn cuối kỳ?
- Net lines {summary['net_lines']:,} dòng có phù hợp với quy mô dự án không?

## 4. ⚠️ Các Vấn Đề Cần Chú Ý
- Liệt kê CỤ THỂ các vấn đề đáng lo ngại (dựa vào warnings và dữ liệu)
- Mức độ nghiêm trọng của từng vấn đề
- Hậu quả có thể xảy ra nếu không khắc phục

## 5. 💡 Khuyến Nghị Chi Tiết
Đưa ra 5-7 khuyến nghị CỤ THỂ, THỰC TẾ và CÓ THỂ THỰC HIỆN NGAY:
- Mỗi khuyến nghị phải bao gồm: Vấn đề → Giải pháp → Cách thực hiện cụ thể
- Ưu tiên theo mức độ quan trọng (Critical → High → Medium → Low)
- Đưa ra ví dụ cụ thể về cách viết commit message tốt hơn
- Gợi ý công cụ/quy trình có thể sử dụng

## 6. 🏆 Điểm Mạnh Đáng Khen Ngợi
- Liệt kê những điểm làm tốt (nếu có) để động viên sinh viên

## 7. 📈 Đánh Giá Tổng Thể
- Cho điểm từ 1-10 cho các tiêu chí:
  + Chất lượng commit messages: ?/10
  + Tần suất làm việc: ?/10
  + Quy mô commits: ?/10
  + Tiến độ phát triển: ?/10
  + TỔNG ĐIỂM: ?/40
- Xếp loại: Xuất sắc (35-40) / Tốt (28-34) / Trung bình (20-27) / Cần cải thiện (<20)

LƯU Ý:
- Phân tích phải DỰA TRÊN DỮ LIỆU CỤ THỂ, không chung chung
- Trích dẫn CỤ THỂ các commit messages làm ví dụ
- Đưa ra con số, tỷ lệ phần trăm cụ thể trong phân tích
- Khuyến nghị phải THỰC TẾ và CÓ THỂ ÁP DỤNG NGAY
- Trả lời bằng TIẾNG VIỆT, văn phong chuyên nghiệp nhưng gần gũi
"""

        response = model.generate_content(prompt)

        return {
            'ai_analysis': response.text,
            'summary': summary
        }

    except ImportError:
        print("  ⚠️  Thư viện google-generativeai chưa được cài đặt.")
        print("     Chạy: pip install google-generativeai")
        return None
    except Exception as e:
        print(f"  ⚠️  Lỗi khi gọi Gemini API: {str(e)}")
        return None

def save_analysis_report(student_name, data, commit_analysis, message_analysis, warnings, ai_result, output_dir):
    """Lưu báo cáo phân tích chi tiết"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Use an accent-free name for the file path (consistent with CSV/chart),
    # while keeping the accented name for display inside the report.
    safe_name = remove_vietnamese_accents(student_name)
    report_path = os.path.join(output_dir, f'{safe_name}_analysis_report.md')

    with open(report_path, 'w', encoding='utf-8') as f:
        # Header
        f.write(f"# 📊 Báo Cáo Phân Tích Git Commits\n\n")
        f.write(f"**Sinh viên:** {student_name}\n\n")
        f.write(f"**Ngày tạo báo cáo:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")

        # Basic statistics
        f.write("## 📈 Thống Kê Cơ Bản\n\n")
        total_added = sum(item['lines_added'] for item in data)
        total_deleted = sum(item['lines_deleted'] for item in data)

        f.write("| Chỉ số | Giá trị |\n")
        f.write("|--------|--------|\n")
        f.write(f"| Tổng số commits | {commit_analysis['total_commits']} |\n")
        f.write(f"| Tổng dòng code thêm | {total_added:,} |\n")
        f.write(f"| Tổng dòng code xóa | {total_deleted:,} |\n")
        f.write(f"| Dòng code ròng | {data[-1]['total_lines']:,} |\n")
        f.write(f"| Trung bình dòng/commit | {(total_added + total_deleted) / len(data):.1f} |\n\n")

        # Commit message analysis
        f.write("## 💬 Phân Tích Commit Messages\n\n")
        f.write(f"- **Độ dài trung bình:** {message_analysis['avg_message_length']:.1f} ký tự\n")
        f.write(f"- **Messages quá ngắn:** {message_analysis['short_messages_count']}/{message_analysis['total_commits']}\n\n")

        f.write("### Từ Khóa Phổ Biến\n\n")
        sorted_keywords = sorted(message_analysis['keywords'].items(), key=lambda x: x[1], reverse=True)
        has_keywords = False
        for keyword, count in sorted_keywords[:10]:
            if count > 0:
                if not has_keywords:
                    f.write("| Từ khóa | Số lần xuất hiện |\n")
                    f.write("|---------|------------------|\n")
                    has_keywords = True
                f.write(f"| `{keyword}` | {count} |\n")

        if not has_keywords:
            f.write("*Không tìm thấy từ khóa phổ biến.*\n")
        f.write("\n")

        # Warnings
        f.write("## ⚠️ Cảnh Báo & Khuyến Nghị\n\n")
        if warnings:
            for warning in warnings:
                icon = "🔴" if warning['level'] == "CRITICAL" else "🟡" if warning['level'] == "WARNING" else "🔵"
                f.write(f"### {icon} {warning['level']}\n\n")
                f.write(f"**Vấn đề:** {warning['message']}\n\n")
                f.write(f"**Giá trị:** `{warning['value']}`\n\n")
        else:
            f.write("### ✅ Không Có Cảnh Báo\n\n")
            f.write("Làm việc tốt! Không phát hiện vấn đề nào.\n\n")

        # AI Analysis
        if ai_result:
            f.write("## 🤖 Phân Tích AI\n\n")
            f.write(ai_result['ai_analysis'])
            f.write("\n\n")

        f.write("---\n\n")
        f.write(f"*Báo cáo được tạo tự động bởi Git Commits Analysis Tool*\n")

    print(f"  📄 Report saved: {report_path}")
    return report_path

def process_teams(file_team):
    with open(file_team, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or len(row) < 2:
                continue

            # Skip header row if present
            if row[0].strip().lower() in ('student_name', 'name'):
                continue

            student_name = row[0].strip()
            repo_url = row[1].strip().replace(' ', '').rstrip('/').replace('.git', '')
            # Optional 3rd column: GitHub username to attribute commits to a single student
            github_username = row[2].strip() if len(row) >= 3 and row[2].strip() else None

            if not student_name or not repo_url:
                continue

            student_name_normalized = remove_vietnamese_accents(student_name)
            url_parts = repo_url.split('/')

            if len(url_parts) < 2:
                print(f'❌ Invalid URL: {repo_url}')
                continue

            repo_name = f'{url_parts[-2]}/{url_parts[-1]}'
            print(f'\n{"="*80}')
            print(f'Processing: {student_name}')
            print(f'Repository: {repo_name}')
            if github_username:
                print(f'GitHub user: {github_username} (lọc commit theo tác giả)')
            print(f'{"="*80}')
            data = read_repo(repo_name, author=github_username)

            if not data:
                print('❌ No data - skipping')
                continue

            # Calculate cumulative lines
            total_lines = 0
            for item in data:
                total_lines += item['lines_added'] - item['lines_deleted']
                item['total_lines'] = total_lines

            student_dir = create_student_directory(student_name_normalized)

            print(f"💾 Saving data...")
            save_data(data, os.path.join(student_dir, f'{student_name_normalized}.csv'))

            print(f"📊 Analyzing...")
            commit_analysis = {'total_commits': len(data)}
            message_analysis = analyze_commit_messages(data)
            warnings = detect_productivity_warnings(data, commit_analysis, message_analysis)
            print(f"   Found {len(warnings)} warnings")

            print(f"📈 Creating charts...")
            create_contribution_chart(data, student_name_normalized, student_dir)

            print(f"🤖 AI analysis...")
            ai_result = analyze_with_ai(data, warnings, student_name)

            print(f"📄 Generating report...")
            save_analysis_report(student_name, data, commit_analysis, message_analysis, warnings, ai_result, student_dir)

            print(f"✅ Completed")

if __name__ == '__main__':
    print("🚀 Starting Git Commits Analysis Tool")
    print("="*80)
    process_teams('student_repo_list.csv')
    print("\n" + "="*80)
    print("✨ All processing completed!")
    print("="*80)
