# Triển khai Case Vault trên Oracle Cloud (tiếng Việt)

Website: **https://casevault.halosparkinc.com** (prod) và **https://staging.casevault.halosparkinc.com** (staging, để thử trước khi lên prod). Hai tên miền này đổi được qua `DOMAIN` / `STAGING_DOMAIN` trong `.env`.

Kiến trúc trên **một** VM:
- Docker Compose chạy hai bản độc lập là `prod` và `staging`. Mỗi bản có app, worker, Postgres riêng và một container backup chạy `pg_dump` hằng ngày, giữ 14 bản.
- Một **Caddy** dùng chung lo HTTPS Let's Encrypt tự động cho cả hai tên miền.
- Image app lấy từ **GHCR (private)**. Image được build tự động khi gắn tag `casevault-vX.Y.Z` trên GitHub.

Mọi khoá bí mật chỉ nằm trong `/opt/casevault/<prod|staging>/.env` **trên server** (quyền 600), không bao giờ commit.

---

## 1. Tạo VM Oracle Cloud

1. Oracle Cloud Console → **Compute → Instances → Create instance**.
2. **Image**: Canonical **Ubuntu 24.04**.
3. **Shape** gợi ý: `VM.Standard.A1.Flex` (Ampere ARM, nằm trong gói Always Free), **1 OCPU + 6 GB RAM**, ổ boot 50 GB. Image Case Vault build cho cả amd64 lẫn arm64.
   Nếu hết slot A1: chọn `VM.Standard.E2.1.Micro` (1 GB RAM) và tạo thêm swap 2 GB, chỉ đủ khi lưu lượng nhỏ.
4. **Networking**: chọn VCN có subnet **public**, tick **Assign a public IPv4 address**.
5. **SSH keys**: dán public key của anh. Bấm **Create**, rồi ghi lại **Public IP**.
6. Đổi IP thành **Reserved public IP** để IP không đổi khi tạo lại VM: Instance → Attached VNICs → IPv4 addresses → Edit → *Reserved public IP*.

## 2. Mở cổng 80/443 ở tầng mạng Oracle (VCN)

Networking → **Virtual cloud networks** → VCN của VM → **Security Lists** → `Default Security List` → **Add Ingress Rules**, thêm 3 rule:

| Source CIDR | Protocol | Destination port |
|---|---|---|
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |
| `0.0.0.0/0` | UDP | `443` (HTTP/3, tuỳ chọn) |

Nếu VCN dùng **Network Security Group**, thêm các rule tương tự vào NSG gắn với VNIC của VM. Riêng tường lửa **trong máy** (iptables) thì script ở bước 4 tự mở.

## 3. DNS cho `casevault` và `staging.casevault`

Tại nơi quản lý DNS của `halosparkinc.com`:

| Type | Name | Value |
|---|---|---|
| A | `casevault` | Public IP của VM |
| A | `staging.casevault` | Public IP của VM |

**Nếu DNS ở Cloudflare**, chọn một trong hai cách:
- **Cách 1 (đơn giản nhất)**: để hai bản ghi ở chế độ **DNS only** (mây xám). Caddy tự lấy chứng chỉ Let's Encrypt.
- **Cách 2 (có proxy Cloudflare, mây cam)**:
  1. SSL/TLS → Overview → **Full (strict)**.
  2. SSL/TLS → Origin Server → **Create certificate** cho `casevault.halosparkinc.com` và `*.casevault.halosparkinc.com`. Lưu thành `/opt/casevault/prod/certs/origin.pem` và `origin.key` (chmod 600).
  3. Trong `/opt/casevault/prod/.env`: đặt `CADDYFILE=Caddyfile.cloudflare-origin` và `TRUST_CLOUDFLARE=1`.
  4. Đặt `TRUST_CLOUDFLARE=1` cả trong `/opt/casevault/staging/.env`.

  Lưu ý: chứng chỉ Universal SSL miễn phí của Cloudflare chỉ phủ một cấp subdomain. Tên `staging.casevault…` là cấp hai, nên với Cách 2 hãy để `staging.casevault` ở **DNS only**, hoặc dùng `casevault-staging.halosparkinc.com` cho staging.

Kiểm tra DNS: `dig +short casevault.halosparkinc.com` phải ra IP của VM.

## 4. Cài đặt server (một lệnh)

SSH vào VM bằng user `ubuntu`, clone repo (private: dùng deploy key chỉ đọc, như mục 1 Cách B trong `docs/INSTALL_VM.md`), rồi chạy:

```bash
sudo bash ~/puzzle-forge/scripts/casevault/install_oracle.sh --ghcr-user <tên-github-của-anh>
```

Script hỏi một **GitHub token** có quyền `read:packages`: GitHub → Settings → Developer settings → Personal access tokens → *Tokens (classic)* → tick **read:packages**.

Script tự làm các việc sau:
- Cài Docker.
- Tạo user `deploy` (thuộc nhóm docker, dùng lại SSH key của anh).
- Mở cổng 80/443 trong iptables và lưu lại.
- Bật fail2ban cho SSH và tự động cập nhật bảo mật.
- Đăng nhập GHCR.
- Cài lệnh `casevault` và thư mục `/opt/casevault`.

> Không bật `ufw` trên Oracle: image Oracle tự quản lý iptables, bật ufw sẽ xung đột và có thể khoá luôn SSH.

## 5. Điền `.env` và khởi động

```bash
sudo -iu deploy
```
```bash
casevault init
```

`init` tạo `/opt/casevault/prod/.env` và `/opt/casevault/staging/.env`, sinh sẵn ngẫu nhiên `SECRET_KEY`, `POSTGRES_PASSWORD`, `VAULT_ADMIN_TOKEN` và `VAULT_ANSWER_KEY`.

```bash
nano /opt/casevault/prod/.env
```

Cần điền:
- `ACME_EMAIL`: email của anh.
- `CASEVAULT_VERSION`: ví dụ `0.2.0`.
- `TURNSTILE_SITE_KEY` và `TURNSTILE_SECRET`: Cloudflare → Turnstile → Add site, thêm cả hai tên miền.
- Klaviyo: `KLAVIYO_API_KEY`, `KLAVIYO_LIST_ID` (xem `docs/KLAVIYO_SETUP.md`).
- Shopify: `SHOPIFY_SHOP`, `SHOPIFY_ADMIN_TOKEN`, `SHOPIFY_STORE_URL`.
- Etsy (nếu đã có app key): `ETSY_API_KEY`, `ETSY_SHOP_ID`, `ETSY_SHOP_URL`.
- Telegram: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

Staging nên dùng key **test**: Klaviyo list riêng (hoặc để trống để không gửi mail), Shopify development store, không có Etsy, Turnstile *test key* hoặc để trống.

```bash
casevault up --staging
```
```bash
casevault up
```

## 6. Kiểm tra HTTPS

```bash
curl -I https://casevault.halosparkinc.com/healthz
```
```bash
casevault status
```

`/healthz` phải trả `"missing_config": []` trước khi mở cho khách.

Kiểm tra header bảo mật (`Strict-Transport-Security`, `Content-Security-Policy`…) trên https://securityheaders.com.

## 7. Tạo tài khoản admin + 2FA

```bash
casevault admin create owner
```

Nhập mật khẩu (tối thiểu 12 ký tự). Lệnh in ra `secret` và `otpauth://…`: thêm vào Google Authenticator / Authy / 1Password. Sau đó đăng nhập `https://casevault.halosparkinc.com/admin`.

Làm tương tự cho staging với `--staging`.

## 8. Kết nối Puzzle Forge (VM ở nhà) → Case Vault

Copy hai token **của từng môi trường** từ `.env` trên server sang Puzzle Forge. Cách nhanh nhất là qua web Forge: **Cài đặt**, nhập vào ô token đã mã hoá.

| Puzzle Forge | Giá trị lấy từ |
|---|---|
| `VAULT_URL=https://casevault.halosparkinc.com`, `VAULT_DOMAIN=casevault.halosparkinc.com` | — |
| `VAULT_ADMIN_TOKEN`, `VAULT_ANSWER_KEY` | `/opt/casevault/prod/.env` |
| `VAULT_STAGING_URL=https://staging.casevault.halosparkinc.com`, `VAULT_STAGING_DOMAIN=…` | — |
| `VAULT_STAGING_ADMIN_TOKEN`, `VAULT_STAGING_ANSWER_KEY` | `/opt/casevault/staging/.env` |

- Forge ở `FORGE_ENV=test` đẩy lên **staging**; `FORGE_ENV=prod` đẩy lên **prod**.
- Website tạm offline thì Forge giữ trong hàng đợi và tự gửi lại; xem bằng `forge vault status`.

## 9. Thử redeem bằng sách mẫu (staging)

Trên VM Forge (chế độ test):

```bash
sudo forge smoke
```

Lệnh này build sách mẫu, chạy QA, đẩy sách lên staging, tạo một Book Code rồi gửi đáp án qua form staging. Kết quả phải là "Case solved".

Kiểm tra thêm trên staging:
- Trang admin hiện cuốn sách và lượt giải.
- Klaviyo (list test) có sự kiện **Case Solved**.

## 10. Bảo trì

| Việc | Lệnh (user `deploy`) |
|---|---|
| Cập nhật phiên bản (thử staging trước) | `casevault update 0.2.1 --staging`, kiểm tra, rồi `casevault update 0.2.1` |
| Xem log | `casevault logs app` / `casevault logs caddy` (access log JSON) |
| Trạng thái | `casevault status` |
| Sao lưu ngay | `casevault backup` |
| Khôi phục | `casevault restore /opt/casevault/prod/backups/casevault-YYYYMMDD-HHMM.sql.gz` |
| Đẩy backup ra ngoài (Object Storage / Google Drive) | `docker run --rm -it -v /opt/casevault/prod/rclone:/config/rclone rclone/rclone:1.68 config`, đặt `BACKUP_REMOTE=tên:thư-mục` trong `.env`, rồi `casevault upload on` |
| Nhập đơn Etsy / mã coupon Etsy | `casevault import-etsy file.csv` / `casevault import-coupons file.csv` (hoặc upload trên trang admin) |
| Sửa luật thưởng / consent | `nano /opt/casevault/prod/config/casevault.yaml` rồi `casevault restart` |

**Bảo mật đã có sẵn:**
- HTTPS bắt buộc, kèm HSTS, CSP, X-Frame-Options, nosniff và Referrer-Policy.
- Giới hạn tần suất theo IP, email và bằng chứng mua, tạm khoá khi sai nhiều lần.
- Turnstile chống bot; admin đăng nhập mật khẩu + 2FA.
- Log truy cập JSON (Caddy) và log ứng dụng.
- Telegram báo khi ứng dụng lỗi (HTTP 500), khi có dấu hiệu gian lận (dùng lại bằng chứng, bị khoá, admin đăng nhập sai) và khi một tác vụ gửi lỗi 3 lần.
- fail2ban cho SSH, tự động cập nhật bảo mật.

## 11. Chạy từ VM ở nhà thay cho Oracle (tuỳ chọn)

Có thể chạy cùng stack trên VM ở nhà, đi qua **Cloudflare Tunnel** thay cho mở cổng.
1. Tạo tunnel: Cloudflare → Zero Trust → Networks → Tunnels → Create.
2. Thêm *Public hostname* `casevault.halosparkinc.com` → `http://prod-app:8000`.
3. Chạy `cloudflared` trong network `edge`:
   ```bash
   docker run -d --name tunnel --restart unless-stopped --network edge cloudflare/cloudflared:latest tunnel --no-autoupdate run --token <TOKEN>
   ```
4. Không bật profile `edge` (không cần Caddy).

Nhược điểm: website tắt khi VM ở nhà tắt.
