# Git Repository Analysis Tool

## Giới thiệu

Tool phân tích lịch sử commit từ GitHub repositories, tạo báo cáo chi tiết với biểu đồ trực quan và phân tích AI để đánh giá chất lượng làm việc.

## Tính năng

- **Phân tích commit**: Thu thập lịch sử commit, thống kê dòng code thêm/xóa
- **Biểu đồ trực quan**: 6 loại biểu đồ phân tích xu hướng và tần suất commit
- **Phân tích commit messages**: Đánh giá chất lượng và từ khóa phổ biến
- **Cảnh báo tự động**: Phát hiện các vấn đề về số lượng, quy mô commits
- **AI Analysis**: Sử dụng Gemini AI để đưa ra đánh giá và khuyến nghị
- **Báo cáo Markdown**: Xuất báo cáo chi tiết định dạng .md

## Cấu trúc output

```
output/
├── [student_name]/
│   ├── [student_name].csv                    # Dữ liệu commit
│   ├── [student_name]_contribution_chart.png # Biểu đồ
│   └── [student_name]_analysis_report.md     # Báo cáo
```

## Cài đặt

### 1. Yêu cầu

- Python 3.8+
- GitHub Personal Access Token
- Gemini API Key

### 2. Clone repository

```bash
git clone https://github.com/longndt/git-repo-analysis.git
cd git-repo-analysis
```

### 3. Cài đặt thư viện

```bash
pip install -r requirements.txt
```

### 4. Cấu hình API keys

Tạo file `.env` từ template:

```bash
cp .env.example .env
```

Mở file `.env` và điền API keys:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GITHUB_TOKEN=your_github_token_here
```

**Lấy API keys:**
- **Gemini API**: https://aistudio.google.com/app/apikey
- **GitHub Token**: https://github.com/settings/tokens (chọn scope `public_repo`)

### 5. Danh sách repository

Tạo file `student_repo_list.csv`:

```csv
student_name,repo_url
student1,https://github.com/username/repo1
student2,https://github.com/username/repo2
```

## Sử dụng

```bash
python git_repo.py
```

Tool sẽ:
1. Đọc danh sách repositories từ `student_repo_list.csv`
2. Phân tích từng repository
3. Tạo báo cáo và biểu đồ trong thư mục `output/`

## Output

Mỗi sinh viên sẽ có thư mục riêng chứa:
- **CSV file**: Dữ liệu commit chi tiết
- **PNG chart**: 6 biểu đồ trực quan phân tích
- **MD report**: Báo cáo đầy đủ với AI analysis

## Xử lý lỗi

**Rate Limit Exceeded**: Thêm GitHub Token vào `.env` (tăng limit lên 5000/giờ)
**Repository Not Found**: Kiểm tra URL và đảm bảo repo là public
**Gemini API Error**: Kiểm tra API key trong `.env` và quota tại Google AI Studio

## Bảo mật

- File `.env` đã được thêm vào `.gitignore` để không commit API keys lên Git
- Sử dụng `.env.example` làm template để chia sẻ cấu hình
- Không hard-code API keys trong source code
