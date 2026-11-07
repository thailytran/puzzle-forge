# Triển khai website Case Vault (tiếng Việt)

Website nằm trong `apps/casevault/`. Có hai cách chạy:

- **A. Oracle Cloud VM + Caddy (khuyên dùng).** Có IP công khai và HTTPS tự động. Website vẫn chạy khi máy nhà tắt.
- **B. Cloudflare Tunnel từ VM ở nhà.** Không mở port, không cần IP tĩnh, nhưng website tắt khi VM nhà tắt.

Mọi khoá bí mật chỉ nằm trong `apps/casevault/.env` **trên server**, không bao giờ commit.

## 0. Chuẩn bị

1. Tên miền: ví dụ `casevault.tenmien.com`. Anh cần chốt tên miền và tên website chính thức.
2. Tạo hai chuỗi ngẫu nhiên. Chạy `openssl rand -hex 32` hai lần để lấy:
   - `VAULT_ADMIN_TOKEN`
   - `VAULT_ANSWER_KEY`

   Đặt **cùng một giá trị** cho mỗi biến ở cả hai nơi:
   - `.env` của Puzzle Forge (VM)
   - `apps/casevault/.env` (server)

   Thêm `SECRET_KEY` và `POSTGRES_PASSWORD`, tạo cũng bằng `openssl rand -hex 32`.

> ⚠️ Nếu đổi `VAULT_ANSWER_KEY` sau khi đã đăng ký sách, phải chạy lại `forge vault sync` cho mọi sách. Hash đáp án và Book Code phụ thuộc khoá này.

## A. Oracle Cloud VM (Always Free) + Caddy

1. Tạo VM Ubuntu 24.04 (Ampere A1 hoặc AMD micro).
   - Trong *Security List*, mở cổng 80 và 443.
   - Trên VM, mở firewall:
     ```bash
     sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
     sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
     sudo netfilter-persistent save
     ```
2. Trỏ DNS: bản ghi `A` của tên miền → IP công khai của VM.
3. Cài Docker:
   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker $USER
   ```
   Đăng xuất rồi đăng nhập lại.
4. Lấy code (repo private: dùng `gh auth login` như trong INSTALL_VM.md):
   ```bash
   git clone https://github.com/thailytran/puzzle-forge.git /opt/puzzle-forge
   cd /opt/puzzle-forge/apps/casevault
   cp .env.example .env && nano .env      # điền DOMAIN, PUBLIC_URL, các khoá
   mkdir -p data && sudo chown 10001 data  # thư mục token Etsy (user trong container)
   docker compose --profile caddy up -d --build
   ```
5. Tạo tài khoản admin có 2FA:
   ```bash
   docker compose exec web python -m casevault create-admin owner
   ```
   Lệnh in ra `secret` và `otpauth://…`. Thêm vào Google Authenticator, Authy hoặc 1Password, rồi đăng nhập `https://<DOMAIN>/admin`.
6. Kiểm tra: mở `https://<DOMAIN>/healthz`. Danh sách `missing_config` phải rỗng trước khi mở cho khách.

## B. Cloudflare Tunnel từ VM ở nhà

1. Vào Cloudflare → Zero Trust → Networks → Tunnels → *Create tunnel*. Copy token.
2. Thêm *Public hostname*: `casevault.tenmien.com` → `http://web:8000`.
3. Trong `.env`, đặt `CLOUDFLARE_TUNNEL_TOKEN=…`, rồi chạy:
   ```bash
   docker compose --profile tunnel up -d --build
   ```
   Không cần mở port 80/443.

## Sao lưu hằng ngày

```bash
crontab -e
15 3 * * * /opt/puzzle-forge/apps/casevault/scripts/backup.sh >> /var/log/casevault-backup.log 2>&1
```

Script giữ 14 bản gần nhất trong `apps/casevault/backups/`. Nên chép thêm ra ngoài server (rclone sang Google Drive/R2).

Khôi phục:
```bash
gunzip -c backups/<file>.sql.gz | docker compose exec -T db psql -U casevault casevault
```

## Cập nhật phiên bản

```bash
cd /opt/puzzle-forge && git pull && cd apps/casevault && docker compose up -d --build
```

## Kết nối Puzzle Forge (VM) → website

Trong `.env` của Puzzle Forge:
```
VAULT_URL=https://<DOMAIN>
VAULT_DOMAIN=<DOMAIN>
VAULT_ADMIN_TOKEN=<giống server>
VAULT_ANSWER_KEY=<giống server>
```

Quy trình cho mỗi sách:
1. Chạy `forge vault init output/<book_id>` rồi điền đáp án và listing.
2. Duyệt: `forge review output/<book_id> --approve`. Sách tự đăng ký lên website. Nếu mất mạng thì vào hàng đợi.
3. Gửi lại hàng đợi bằng `forge vault sync`; xem trạng thái bằng `forge vault status`.

## Etsy, Shopify, Turnstile, Telegram

- **Turnstile:** dash.cloudflare.com → Turnstile → Add site (tên miền) → Site key + Secret key → `.env`.
- **Shopify:** tạo app (Shopify admin → Settings → Apps → Develop apps, hoặc Dev Dashboard).
  - Scope: `read_orders`, `read_all_orders` (đơn cũ hơn 60 ngày) và `write_discounts`.
  - Lấy Admin API access token → `SHOPIFY_ADMIN_TOKEN`.
- **Etsy:**
  - Nếu chưa có API: dùng CSV. Etsy Shop Manager → Settings → Options → Download Data → **Orders – Order Items** → upload ở trang Admin, hoặc chạy:
    ```bash
    docker compose exec web python -m casevault import-etsy file.csv
    ```
    Đơn đang *pending* được duyệt tự động, khách nhận email.
  - Mã giảm giá Etsy (10/20/30/40 %):
    - Tạo trong Shop Manager → Marketing → Sales and discounts.
    - Xuất thành CSV `percent,code,expires`, rồi upload ở trang Admin.
    - Telegram báo khi mỗi mức còn dưới 20 mã.
  - Khi có app key Etsy: điền `ETSY_API_KEY`, `ETSY_SHOP_ID`. Đặt token OAuth vào `data/etsy_token.json` (hướng dẫn cấp token sẽ bổ sung khi anh có app key).
- **Telegram:**
  - Tạo bot với @BotFather → `TELEGRAM_BOT_TOKEN`.
  - Nhắn bot một tin, lấy `chat_id` qua `https://api.telegram.org/bot<TOKEN>/getUpdates`.
