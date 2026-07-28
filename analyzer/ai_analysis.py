"""Gemini-based commit analysis, with a disk cache so reruns on unchanged
commit history don't re-spend Gemini API quota."""
import hashlib
import json
import os

import pandas as pd

from analyzer.config import GEMINI_API_KEY, AI_CACHE_DIRNAME
from analyzer.vietnamese import remove_vietnamese_accents


# Bump when the prompt template or the data fed into it changes, so cached
# results from an older, less detailed prompt aren't served after an update.
_PROMPT_VERSION = 2

_TIMELINE_SAMPLE_CAP = 150


def _data_fingerprint(data, model_name):
    payload = json.dumps(
        [{'date-time': d['date-time'], 'comments': d['comments'],
          'lines_added': d['lines_added'], 'lines_deleted': d['lines_deleted']} for d in data],
        sort_keys=True,
    )
    return hashlib.sha256(f'{_PROMPT_VERSION}|{model_name}|{payload}'.encode('utf-8')).hexdigest()


def _cache_path(output_dir, student_name, fingerprint):
    cache_dir = os.path.join(output_dir, AI_CACHE_DIRNAME)
    os.makedirs(cache_dir, exist_ok=True)
    safe_name = remove_vietnamese_accents(student_name)
    return os.path.join(cache_dir, f'{safe_name}_{fingerprint[:16]}.json')


def _load_cached(cache_path):
    if not os.path.exists(cache_path):
        return None
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _save_cache(cache_path, result):
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False)


def _sampled_timeline(data):
    """Full commit timeline if small enough, otherwise an evenly-spaced
    sample (always including the first and last commit) so the model can
    cite specific real commits instead of only the first/last 5."""
    n = len(data)
    if n <= _TIMELINE_SAMPLE_CAP:
        indices = range(n)
    else:
        # i=0 maps to index 0 and i=cap-1 maps to index n-1, so the first and
        # last commit are always included regardless of n.
        indices = sorted({round(i * (n - 1) / (_TIMELINE_SAMPLE_CAP - 1)) for i in range(_TIMELINE_SAMPLE_CAP)})

    lines = []
    for idx in indices:
        item = data[idx]
        msg = item['comments'][:140]
        lines.append(f"{idx+1}. [{item['date-time']}] (+{item['lines_added']}/-{item['lines_deleted']}) \"{msg}\"")

    note = '' if n <= _TIMELINE_SAMPLE_CAP else f'\n(Đã lấy mẫu {len(lines)}/{n} commits, rải đều theo thời gian)'
    return '\n'.join(lines) + note


def _weekly_breakdown(df):
    weekly = df.groupby(df['date-time'].dt.to_period('W')).size()
    return '\n'.join(f"- Tuần {period.start_time.strftime('%Y-%m-%d')}: {count} commits" for period, count in weekly.items())


def _longest_gap_days(df):
    unique_dates = sorted(df['date-time'].dt.date.unique())
    if len(unique_dates) < 2:
        return 0
    gaps = [(unique_dates[i + 1] - unique_dates[i]).days for i in range(len(unique_dates) - 1)]
    return max(gaps)


def _half_comparison(data):
    """Compare the first half vs second half of the commit timeline so the
    model has real numbers to base a 'did quality improve?' answer on,
    instead of guessing from 10 sampled messages."""
    mid = len(data) // 2
    first_half, second_half = data[:mid] or data, data[mid:]

    def stats(chunk):
        avg_msg = sum(len(c['comments']) for c in chunk) / len(chunk)
        avg_size = sum(c['lines_added'] + c['lines_deleted'] for c in chunk) / len(chunk)
        short_ratio = sum(1 for c in chunk if len(c['comments']) < 10) / len(chunk) * 100
        return avg_msg, avg_size, short_ratio

    return stats(first_half), stats(second_half)


def analyze_with_ai(data, warnings, student_name, output_dir, message_analysis=None,
                     model_name='gemini-2.5-flash', use_cache=True):
    """Phan tich du lieu bang Gemini AI va dua ra danh gia"""

    if not GEMINI_API_KEY or not GEMINI_API_KEY.strip() or GEMINI_API_KEY.strip() == "your_gemini_api_key_here":
        print("  Gemini API key chua duoc cau hinh. Bo qua AI analysis.")
        print("     De su dung AI analysis, them GEMINI_API_KEY vao file .env.")
        return None

    fingerprint = _data_fingerprint(data, model_name)
    cache_path = _cache_path(output_dir, student_name, fingerprint)

    if use_cache:
        cached = _load_cached(cache_path)
        if cached is not None:
            print("  AI analysis loaded from cache (commit history unchanged).")
            return cached

    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name)

        df = pd.DataFrame(data)
        df['date-time'] = pd.to_datetime(df['date-time'])

        total_added = sum(item['lines_added'] for item in data)
        total_deleted = sum(item['lines_deleted'] for item in data)
        net_lines = total_added - total_deleted
        avg_lines_per_commit = (total_added + total_deleted) / len(data)

        date_range_days = (df['date-time'].max() - df['date-time'].min()).days + 1
        commits_per_day = len(data) / date_range_days if date_range_days > 0 else 0

        all_messages = [item['comments'] for item in data]
        avg_msg_length = sum(len(msg) for msg in all_messages) / len(all_messages)

        df['hour'] = df['date-time'].dt.hour
        df['date'] = df['date-time'].dt.date
        most_active_hour = df['hour'].mode()[0] if not df['hour'].mode().empty else 0

        small_commits = sum(1 for item in data if (item['lines_added'] + item['lines_deleted']) < 10)
        medium_commits = sum(1 for item in data if 10 <= (item['lines_added'] + item['lines_deleted']) < 100)
        large_commits = sum(1 for item in data if (item['lines_added'] + item['lines_deleted']) >= 100)

        weekend_commits = int((df['date-time'].dt.dayofweek >= 5).sum())
        (first_msg, first_size, first_short_pct), (second_msg, second_size, second_short_pct) = _half_comparison(data)
        keyword_counts = (message_analysis or {}).get('keywords', {})

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
            'weekend_commits': weekend_commits,
            'weekend_pct': weekend_commits / len(data) * 100,
            'longest_gap_days': _longest_gap_days(df),
            'first_half_stats': {'avg_msg_len': first_msg, 'avg_size': first_size, 'short_pct': first_short_pct},
            'second_half_stats': {'avg_msg_len': second_msg, 'avg_size': second_size, 'short_pct': second_short_pct},
            'keyword_counts': keyword_counts,
            'warnings': [w['message'] for w in warnings]
        }

        weekly_breakdown = _weekly_breakdown(df)
        timeline = _sampled_timeline(data)
        keyword_lines = '\n'.join(f'- `{kw}`: {count} lần' for kw, count in sorted(keyword_counts.items(), key=lambda x: -x[1]) if count > 0) or 'Không phát hiện từ khóa chuẩn nào'

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
📆 Commits cuối tuần (T7/CN): {summary['weekend_commits']}/{summary['total_commits']} ({summary['weekend_pct']:.1f}%)
⏳ Khoảng cách dài nhất giữa 2 lần commit: {summary['longest_gap_days']} ngày

========== SO SÁNH NỬA ĐẦU vs NỬA CUỐI DỰ ÁN ==========
(Chia theo thứ tự thời gian commit, mỗi nửa ~{len(data)//2} commits)
| Chỉ số | Nửa đầu | Nửa cuối |
|--------|---------|----------|
| Độ dài message trung bình | {summary['first_half_stats']['avg_msg_len']:.1f} ký tự | {summary['second_half_stats']['avg_msg_len']:.1f} ký tự |
| Quy mô commit trung bình | {summary['first_half_stats']['avg_size']:.1f} dòng | {summary['second_half_stats']['avg_size']:.1f} dòng |
| Tỷ lệ message quá ngắn | {summary['first_half_stats']['short_pct']:.1f}% | {summary['second_half_stats']['short_pct']:.1f}% |

========== PHÂN BỐ COMMITS THEO TUẦN ==========
{weekly_breakdown}

========== TỪ KHÓA TRONG COMMIT MESSAGES ==========
{keyword_lines}

========== TOÀN BỘ LỊCH SỬ COMMIT (ngày giờ, +thêm/-xóa, message) ==========
{timeline}

========== CẢNH BÁO TỰ ĐỘNG ==========
{chr(10).join(f'⚠️ {w}' for w in summary['warnings']) if summary['warnings'] else '✅ Không có cảnh báo đáng kể'}

========== YÊU CẦU PHÂN TÍCH ==========
Hãy đưa ra phân tích CHI TIẾT, CỤ THỂ và THỰC TẾ theo cấu trúc sau. Với MỌI nhận định, PHẢI trích dẫn commit cụ thể (số thứ tự, ngày, hoặc nội dung message trong danh sách trên) hoặc con số cụ thể từ dữ liệu - không được nhận định chung chung kiểu "commit messages khá tốt" mà không có dẫn chứng.

## 1. 📝 Đánh Giá Chất Lượng Commit Messages
- Phân tích độ rõ ràng, tính mô tả của các commit messages, trích dẫn ít nhất 3 message cụ thể (kèm số thứ tự) làm ví dụ tốt và 3 message làm ví dụ xấu
- So sánh bảng "Nửa đầu vs Nửa cuối" ở trên: độ dài message có tăng không, tỷ lệ message ngắn có giảm không? Kết luận có tiến bộ hay không DỰA TRÊN SỐ LIỆU
- Có tuân thủ quy ước commit messages chuẩn không? (ví dụ: conventional commits `feat:`, `fix:`...). Đếm số lượng message tuân thủ / không tuân thủ
- Đối chiếu với bảng từ khóa: những từ khóa nào bị dùng quá ít (ví dụ `test`, `doc`) so với đặc thù dự án?

## 2. 📊 Đánh Giá Tần Suất và Quy Mô Commits
- Tần suất {summary['commits_per_day']:.2f} commits/ngày có hợp lý không? (so với mức lý tưởng 1-3 commits/ngày cho dự án học tập)
- Dựa vào "Phân bố commits theo tuần" ở trên: tuần nào làm nhiều nhất, tuần nào ít/không có commit? Có tuần nào bất thường không?
- Phân bố quy mô commits ({summary['commit_size_distribution']['small']} nhỏ / {summary['commit_size_distribution']['medium']} vừa / {summary['commit_size_distribution']['large']} lớn) có hợp lý không?
- Có dấu hiệu "commit bombing" (nhiều commits nhỏ liên tiếp) hay "commit dumping" (ít commits nhưng quá lớn) không? Chỉ rõ cụm commit nào (theo số thứ tự) thể hiện điều này
- Khoảng cách dài nhất không commit là {summary['longest_gap_days']} ngày - đây có phải dấu hiệu trì hoãn không?
- Đánh giá thói quen làm việc: giờ chủ yếu {summary['most_active_hour']}:00, tỷ lệ cuối tuần {summary['weekend_pct']:.1f}%

## 3. 🎯 Đánh Giá Xu Hướng Phát Triển
- Dựa trên bảng so sánh nửa đầu/nửa cuối VÀ phân bố theo tuần: xu hướng code có đều đặn hay dồn về cuối kỳ? Chỉ rõ bằng số liệu (ví dụ: "N/{summary['total_commits']} commits trong tuần cuối cùng")
- Tỷ lệ code added/deleted có hợp lý không? (tỷ lệ deleted quá cao = thiếu kế hoạch)
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
- Phân tích phải DỰA TRÊN DỮ LIỆU CỤ THỂ ở trên (danh sách commit, bảng so sánh, phân bố theo tuần, từ khóa), không chung chung
- MỖI nhận định trong mục 1-4 phải kèm ít nhất một dẫn chứng cụ thể: số thứ tự commit, ngày tháng, nội dung message nguyên văn, hoặc con số/tỷ lệ % tính từ dữ liệu
- Không lặp lại nguyên văn các dòng dữ liệu đã cho - hãy DIỄN GIẢI Ý NGHĨA của chúng
- Khuyến nghị phải THỰC TẾ và CÓ THỂ ÁP DỤNG NGAY
- Trả lời bằng TIẾNG VIỆT, văn phong chuyên nghiệp nhưng gần gũi, độ dài đầy đủ cho cả 7 mục (không rút gọn)
"""

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=8192,
            ),
        )

        result = {
            'ai_analysis': response.text,
            'summary': summary
        }
        if use_cache:
            _save_cache(cache_path, result)
        return result

    except ImportError:
        print("  Thu vien google-generativeai chua duoc cai dat.")
        print("     Chay: pip install google-generativeai")
        return None
    except Exception as e:
        print(f"  Loi khi goi Gemini API: {str(e)}")
        return None
