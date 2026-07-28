import os
from datetime import datetime

import pandas as pd

from analyzer.analysis import compute_line_totals
from analyzer.vietnamese import remove_vietnamese_accents


def save_data(data, csv_file):
    df = pd.DataFrame(data)
    df.to_csv(csv_file, index=False)
    print(f"Data saved to {csv_file}")


def create_student_directory(student_name, base_dir='output'):
    """Tao thu muc rieng cho tung sinh vien"""
    student_dir = os.path.join(base_dir, student_name)
    os.makedirs(student_dir, exist_ok=True)
    return student_dir


def save_analysis_report(student_name, data, commit_analysis, message_analysis, warnings, ai_result, output_dir):
    """Luu bao cao phan tich chi tiet"""
    os.makedirs(output_dir, exist_ok=True)

    # Use an accent-free name for the file path (consistent with CSV/chart),
    # while keeping the accented name for display inside the report.
    safe_name = remove_vietnamese_accents(student_name)
    report_path = os.path.join(output_dir, f'{safe_name}_analysis_report.md')

    total_added, total_deleted = compute_line_totals(data)

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# 📊 Báo Cáo Phân Tích Git Commits\n\n")
        f.write(f"**Sinh viên:** {student_name}\n\n")
        f.write(f"**Ngày tạo báo cáo:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")

        f.write("## 📈 Thống Kê Cơ Bản\n\n")
        f.write("| Chỉ số | Giá trị |\n")
        f.write("|--------|--------|\n")
        f.write(f"| Tổng số commits | {commit_analysis['total_commits']} |\n")
        f.write(f"| Tổng dòng code thêm | {total_added:,} |\n")
        f.write(f"| Tổng dòng code xóa | {total_deleted:,} |\n")
        f.write(f"| Dòng code ròng | {data[-1]['total_lines']:,} |\n")
        f.write(f"| Trung bình dòng/commit | {(total_added + total_deleted) / len(data):.1f} |\n\n")

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

        if ai_result:
            f.write("## 🤖 Phân Tích AI\n\n")
            f.write(ai_result['ai_analysis'])
            f.write("\n\n")

        f.write("---\n\n")
        f.write("*Báo cáo được tạo tự động bởi Git Commits Analysis Tool*\n")

    print(f"  Report saved: {report_path}")
    return report_path
