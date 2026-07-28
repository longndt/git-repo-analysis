# Git Repository Analysis Tool

## Giới thiệu

Tool phân tích lịch sử commit từ GitHub repositories, tạo báo cáo chi tiết với biểu đồ trực quan và phân tích AI để đánh giá chất lượng làm việc.

## Tính năng

- **Phân tích commit**: Thu thập lịch sử commit, thống kê dòng code thêm/xóa
- **Biểu đồ trực quan**: 6 loại biểu đồ phân tích xu hướng và tần suất commit
- **Phân tích commit messages**: Đánh giá chất lượng và từ khóa phổ biến
- **Cảnh báo tự động**: Phát hiện các vấn đề về số lượng, quy mô commits
- **AI Analysis**: Gemini AI phân tích dựa trên toàn bộ lịch sử commit (không chỉ vài commit đầu/cuối), kèm phân bố theo tuần, so sánh nửa đầu/nửa cuối dự án, từ khóa message — yêu cầu mọi nhận định phải có dẫn chứng cụ thể
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

Tạo file `student_repo_list.csv` từ template (`student_repo_list.csv` chứa tên thật của sinh viên nên đã được thêm vào `.gitignore` — không commit lên Git):

```bash
cp student_repo_list.example.csv student_repo_list.csv
```

```csv
student_name,repo_url
student1,https://github.com/username1/repo1
student2,https://github.com/username2/repo2
```

> Tool tự động lấy **username** từ chính `repo_url` (phần chủ sở hữu repo) để lọc commit theo tác giả đó — phù hợp khi mỗi sinh viên có repo riêng. Nếu chủ sở hữu không phải một tài khoản GitHub cá nhân (ví dụ repo thuộc một tổ chức), tool sẽ tự động phân tích **toàn bộ** commit của repo thay vì lọc.

## Sử dụng

```bash
python git_repo.py
```

Các tùy chọn dòng lệnh:

| Flag | Mặc định | Ý nghĩa |
|------|----------|---------|
| `--input` | `student_repo_list.csv` | File CSV danh sách sinh viên/repo |
| `--output-dir` | `output` | Thư mục ghi kết quả |
| `--model` | `gemini-2.5-flash` | Model Gemini dùng cho AI analysis |
| `--skip-ai` | tắt | Bỏ qua bước gọi Gemini (vẫn có CSV, biểu đồ, cảnh báo rule-based) |
| `--workers` | `4` | Số sinh viên xử lý song song (đặt `1` để chạy tuần tự) |

Ví dụ:

```bash
python git_repo.py --input teams.csv --output-dir results --workers 8
```

Tool sẽ:
1. Đọc danh sách repositories từ file CSV
2. Phân tích từng repository (commit history được lấy qua GitHub GraphQL API khi có `GITHUB_TOKEN`, giúp giảm số request so với REST API)
3. Tạo báo cáo và biểu đồ trong thư mục output (mặc định `output/`)

Kết quả phân tích AI được cache theo nội dung commit trong `output/<sinh_viên>/.ai_cache/` — chạy lại tool trên dữ liệu chưa đổi sẽ không gọi lại Gemini API.

## Cấu trúc mã nguồn

```
git_repo.py          # Entry point mỏng, gọi analyzer.cli.main()
analyzer/
├── config.py         # Đọc .env, hằng số mặc định
├── vietnamese.py      # Chuẩn hóa tên tiếng Việt
├── github_client.py   # Lấy commit qua GraphQL (fallback REST khi không có token)
├── analysis.py        # Phân tích commit message + cảnh báo rule-based
├── ai_analysis.py      # Gọi Gemini AI + cache kết quả
├── charts.py           # Vẽ biểu đồ contribution
├── report.py            # Ghi CSV + báo cáo Markdown
├── pipeline.py           # Điều phối xử lý từng sinh viên (tuần tự hoặc song song)
└── cli.py                 # argparse + entry point
```

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
- File `student_repo_list.csv` (chứa tên thật + repo URL sinh viên) cũng nằm trong `.gitignore`; dùng `student_repo_list.example.csv` làm template để chia sẻ
