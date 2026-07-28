import os

import matplotlib
# Headless backend: this script only saves PNGs and never shows a window.
# Also required for correctness once chart creation runs on background
# threads (see pipeline.py) - GUI backends like the default TkAgg are not
# thread-safe.
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd


def create_contribution_chart(data, student_name, output_dir):
    """Ve bieu do contribution (lines added/deleted over time).

    Expects each item in ``data`` to already carry a running ``total_lines``
    (cumulative net lines), computed by the pipeline before this is called.
    """
    os.makedirs(output_dir, exist_ok=True)

    df = pd.DataFrame(data)
    df['date-time'] = pd.to_datetime(df['date-time'])
    df['hour'] = df['date-time'].dt.hour
    df['day_of_week'] = df['date-time'].dt.day_name()

    fig, axes = plt.subplots(3, 2, figsize=(16, 12))
    fig.suptitle(f'Code Contribution Analysis - {student_name}', fontsize=16, fontweight='bold')

    ax1 = axes[0, 0]
    ax1.plot(df['date-time'], df['total_lines'], marker='o', linestyle='-', linewidth=2, markersize=4, color='#2E86AB')
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Total Lines')
    ax1.set_title('Cumulative Lines of Code Over Time')
    ax1.grid(True, alpha=0.3)
    ax1.tick_params(axis='x', rotation=45)

    ax2 = axes[0, 1]
    ax2.bar(range(len(df)), df['lines_added'], alpha=0.7, label='Added', color='#06A77D')
    ax2.bar(range(len(df)), -df['lines_deleted'], alpha=0.7, label='Deleted', color='#D62828')
    ax2.set_xlabel('Commit Number')
    ax2.set_ylabel('Lines')
    ax2.set_title('Lines Added vs Deleted per Commit')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

    df_grouped = df.groupby(df['date-time'].dt.date).size()
    ax3 = axes[1, 0]
    ax3.bar(range(len(df_grouped)), df_grouped.values, color='#F77F00', alpha=0.7)
    ax3.set_xlabel('Date')
    ax3.set_ylabel('Number of Commits')
    ax3.set_title('Commit Frequency by Date')
    ax3.grid(True, alpha=0.3)

    commits_per_hour = df.groupby('hour').size()
    ax4 = axes[1, 1]
    ax4.bar(commits_per_hour.index, commits_per_hour.values, color='#9B59B6', alpha=0.7)
    ax4.set_xlabel('Hour of Day')
    ax4.set_ylabel('Number of Commits')
    ax4.set_title('Commit Frequency by Hour of Day')
    ax4.set_xticks(range(0, 24, 2))
    ax4.grid(True, alpha=0.3)

    df['total_changes'] = df['lines_added'] + df['lines_deleted']
    size_bins = [0, 10, 100, float('inf')]
    size_labels = ['Small (<10)', 'Medium (10-99)', 'Large (>=100)']
    commit_sizes = pd.cut(df['total_changes'], bins=size_bins, labels=size_labels, right=False).value_counts().reindex(size_labels, fill_value=0)
    ax5 = axes[2, 0]
    bars5 = ax5.bar(commit_sizes.index, commit_sizes.values, color=['#06A77D', '#F77F00', '#D62828'], alpha=0.7)
    for bar in bars5:
        height = bar.get_height()
        pct = height / len(df) * 100 if len(df) else 0
        ax5.text(bar.get_x() + bar.get_width() / 2, height, f'{int(height)}\n({pct:.0f}%)',
                  ha='center', va='bottom', fontsize=9)
    ax5.set_xlabel('Commit Size (lines changed)')
    ax5.set_ylabel('Number of Commits')
    ax5.set_title('Commit Size Distribution')
    ax5.grid(True, alpha=0.3, axis='y')

    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    commits_per_weekday = df['day_of_week'].value_counts().reindex(day_order, fill_value=0)
    ax6 = axes[2, 1]
    ax6.barh(commits_per_weekday.index, commits_per_weekday.values, color='#06A77D', alpha=0.7)
    ax6.set_xlabel('Number of Commits')
    ax6.set_title('Commits by Day of Week')
    ax6.grid(True, alpha=0.3, axis='x')

    plt.tight_layout()
    chart_path = os.path.join(output_dir, f'{student_name}_contribution_chart.png')
    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
    plt.close(fig)

    print(f"  Chart saved: {chart_path}")
    return chart_path
