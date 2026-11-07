# Cài đặt Klaviyo cho Case Vault (tiếng Việt)

Website gửi **sự kiện** (metric) sang Klaviyo. Mỗi sự kiện kích hoạt một **Flow** gửi email. Website tự lưu phần thưởng trước khi gửi, nên Klaviyo lỗi cũng không mất thưởng: sự kiện nằm trong hàng đợi, website tự gửi lại và báo Telegram.

## 1. API key và List

1. Vào Klaviyo → Settings → **API keys** → *Create Private API Key*.
   - Tên: `Case Vault`.
   - Quyền **Full** cho: Profiles, Lists, Events, Subscriptions (hoặc Custom: write cho 4 mục này).
   - Dán key vào `KLAVIYO_API_KEY` trong `apps/casevault/.env` trên server.
2. Vào Audience → Lists & Segments → *Create List* → tên **Case Vault Newsletter**.
   - Bật **double opt-in** nếu muốn (khuyên dùng cho khách EU/UK).
   - Mở list, copy **List ID** (6 ký tự trên URL) → `KLAVIYO_LIST_ID`.
3. Khách chỉ được thêm vào list khi đã tick ô newsletter.
   - Website gửi `consent: SUBSCRIBED` kèm thời điểm và nguồn `Case Vault form vN`.
   - Website cũng tự lưu bằng chứng đồng ý: thời gian, IP, câu chữ, phiên bản form.

## 2. Các sự kiện website gửi

| Metric | Khi nào | Biến dùng trong email (`{{ event.… }}`) |
|---|---|---|
| **Case Solved** | giải đúng và có bằng chứng mua hợp lệ | `book_title`, `sku`, `solve_count`, `reward_tier` (1–5), `reward_percent`, `is_gift`, `coupon_code`, `coupon_platform` (`etsy`/`shopify`), `coupon_where` (link shop), `coupon_expires` (YYYY-MM-DD), `certificate_url`, `progress_text` (vd. "2/5 cases solved – 3 more to earn a FREE book"), `next_milestone`, `account_url` |
| **Verification Pending** | đáp án đúng, nhưng đơn Etsy/Shopify chưa có trong dữ liệu | `book_title`, `sku` |
| **Verification Approved** | đơn pending vừa được xác minh (CSV/API/admin) | `book_title`, `sku` (sau đó còn có thêm sự kiện *Case Solved*) |
| **Verification Rejected** | không xác minh được (quá 45 ngày hoặc admin từ chối) | `book_title`, `reason` |
| **Gift Ready** | khách đã chọn sách tặng ở mốc 5 | `book_title`, `coupon_code`, `coupon_where`, `coupon_expires`, `account_url` |
| **Login Link** | khách xin link đăng nhập trang tài khoản | `login_url` (hết hạn sau 30 phút) |

Profile cũng được cập nhật với các thuộc tính: `cases_solved`, `books_solved`, `current_tier`, `purchase_place`, `country`, `first_name`.

## 3. Tạo Flow "Case Solved" (có nhánh theo mức thưởng)

1. Flows → *Create Flow* → *Build your own*.
   - Tên: `Case Vault – Case Solved`.
   - Trigger: **Metric → Case Solved** (metric chỉ hiện sau khi website gửi sự kiện đầu tiên; xem mục 5 để gửi thử).
2. Thêm **Conditional split**: `reward_tier equals 5` (sự kiện *Case Solved* → thuộc tính `reward_tier`).
   - **YES → email "FREE book":** chúc mừng, mời chọn sách tặng tại `{{ event.account_url }}`.
   - **NO → email coupon:** có thể tách tiếp 1/2/3/4 nếu muốn tiêu đề khác nhau, hoặc dùng một email chung với `{{ event.reward_percent }} %`.
3. Bật **Smart Sending: OFF** cho flow này (email giao dịch, mỗi lần giải phải nhận).
   - Đánh dấu email là **Transactional** nếu tài khoản được Klaviyo duyệt. Khi đó khách đã hủy newsletter vẫn nhận email thưởng.
   - Nếu chưa được duyệt, gửi Klaviyo yêu cầu "transactional flow". Trước khi được duyệt, email chỉ tới khách còn nhận email.
4. Làm tương tự cho các Flow còn lại:
   - *Verification Pending*
   - *Verification Approved*
   - *Verification Rejected*
   - *Gift Ready*
   - *Login Link* (Login Link bắt buộc là transactional)

## 4. Mẫu email (HTML theo brand)

Tiêu đề: `Case solved: {{ event.book_title }} 🔓`

```html
<h1 style="color:#1F4E79">Brilliant deduction!</h1>
<p>You solved <strong>{{ event.book_title }}</strong>.</p>
{% if event.is_gift %}
<p><strong>That's 5 cases – your FREE new book is waiting.</strong>
<a href="{{ event.account_url }}">Choose your book</a></p>
{% else %}
<p>Your reward: <strong>{{ event.reward_percent }}% off</strong> on
{% if event.coupon_platform == 'etsy' %}our Etsy shop{% else %}our online shop{% endif %}</p>
<p style="font:700 22px monospace;background:#eef3f8;padding:8px 12px;display:inline-block">{{ event.coupon_code }}</p>
<p>Use it at <a href="{{ event.coupon_where }}">{{ event.coupon_where }}</a> before
{{ event.coupon_expires }}. Single use, not combinable with other offers.</p>
{% endif %}
<p>{{ event.progress_text }}</p>
<p><a href="{{ event.certificate_url }}">Download your certificate (PDF)</a></p>
```

- Thêm logo và màu brand trong *Universal content* → header/footer.
- Footer bắt buộc có `{% unsubscribe %}` cho email marketing, và địa chỉ doanh nghiệp.
- Email giao dịch vẫn nên có dòng: "You receive this e-mail because you submitted a case on Case Vault".
- **Không** xin hoặc thưởng cho đánh giá (review) trong bất kỳ email nào.

## 5. Gửi thử

1. Trên server, đặt `KLAVIYO_API_KEY` và `KLAVIYO_LIST_ID`, rồi chạy `docker compose up -d`.
2. Đăng ký một sách thử từ VM:
   - `forge vault init` → điền đáp án.
   - `forge review --approve`, hoặc `forge vault sync`.
3. Tạo Book Code thử: `forge vault codes output/<book_id> --count 1`. Mở `https://<DOMAIN>/solve/<book_id>`, nhập đáp án, chọn "In person", dán Book Code, dùng email của anh.
4. Klaviyo → Analytics → Metrics: phải thấy **Case Solved**. Mở Flow → *Preview* với profile đó để xem biến.
5. Kiểm tra lỗi: trang Admin → *Outbox* hiển thị sự kiện chưa gửi được cùng lỗi. Telegram sẽ báo nếu một việc lỗi 3 lần liên tiếp.

## 6. Hủy đăng ký

- Khách bấm unsubscribe trong email Klaviyo → Klaviyo gỡ khỏi list.
- Trang `/unsubscribe` của website cũng gỡ khỏi list.
- Hủy đăng ký **không** xóa coupon đã nhận. Khách vẫn nhận email thưởng (flow transactional).
- Danh sách xuất CSV ở Admin chỉ gồm khách **còn** đồng ý nhận newsletter.
