# PROMPTS — Các prompt dùng với Claude Code (claude.ai/code)

## 1. Lần đầu: Bootstrap
Dán toàn bộ nội dung `BOOTSTRAP_PROMPT.md` vào session đầu tiên. Claude Code tự tạo tài liệu, commit và bắt đầu code từ P0.1.

## 2. Các session sau: "Tiếp tục"
```
Đọc CLAUDE.md, docs/STATUS.md và docs/ROADMAP.md. Tiếp tục làm các task chưa xong theo đúng
workflow mục 7 của CLAUDE.md (branch theo phase, test trước, commit + push sau mỗi task).
Làm liên tục đến khi gặp điều kiện STOP. Báo cáo bằng tiếng Việt.
```

## 3. Sau milestone (P1.8, P3.11), khi tôi đã duyệt PDF
(Claude Code dán sẵn checklist + mẫu trả lời trong tin nhắn; file `review/<mã>.md` và ảnh trang nằm trong repo.)
```
Đọc CLAUDE.md và docs/STATUS.md. Tôi đã duyệt milestone <mã>. Nhận xét của tôi:
- <nhận xét 1>
- <nhận xét 2>
Sửa theo nhận xét (thêm task vào ROADMAP nếu cần), rồi tiếp tục các task sau theo workflow.
```

## 4. Báo lỗi khi chạy trên VM
```
Đọc CLAUDE.md. Lỗi khi chạy trên VM Ubuntu:
Lệnh: <lệnh>
Log:
<dán log>
Tìm nguyên nhân, viết test tái hiện, sửa, commit + push. Hướng dẫn tôi cách kiểm tra lại trên VM.
```

## 5. Đổi yêu cầu
```
Đọc CLAUDE.md. Tôi muốn thay đổi: <mô tả>. Cập nhật SPEC/MYSTERY_DESIGN/ROADMAP trước,
cho tôi xem 3–5 dòng tóm tắt thay đổi, rồi code theo workflow.
```

## 6. Chạy trên VM cá nhân (sau khi merge PR)
Lần đầu: làm theo `docs/INSTALL_VM.md` (Claude Code viết ở task P0.5).
Các lần sau:
```bash
cd ~/puzzle-forge && git pull && uv sync
uv run pytest -q
uv run forge book build configs/books/example_wordsearch.yaml
```
