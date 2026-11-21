# Cài Puzzle Forge trên VM Ubuntu 24.04 (cá nhân)

Puzzle Forge chạy như một **dịch vụ hệ thống** trên VM ở nhà. Anh dùng nó qua trình duyệt (qua Tailscale), không cần mở terminal hằng ngày.

| Thành phần | Vị trí |
|---|---|
| Code (mỗi phiên bản một thư mục) | `/opt/puzzle-forge/releases/vX.Y.Z`, bản đang chạy: `/opt/puzzle-forge/current` |
| Dữ liệu: sách, database, bản sao lưu | `/var/lib/puzzle-forge/` (`output/`, `data/forge.db`, `backups/`) |
| Cấu hình + khoá API (đã mã hoá) | `/etc/puzzle-forge/` (`forge.env` quyền 600, `secrets.enc`, `ai_routing.yaml`, `brand.yaml`) |
| Dịch vụ systemd | `forge-web` (giao diện web, chỉ nghe trên IP Tailscale), `forge-worker` (build sách), `forge-backup.timer` (sao lưu 03:20 mỗi ngày) |
| Lệnh quản trị | `forge …` (đã cài sẵn vào `/usr/local/bin/forge`) |

---

## 0. Yêu cầu

- VM Ubuntu 24.04, tối thiểu 2 vCPU, 4 GB RAM, 20 GB đĩa trống. User thường của anh có quyền `sudo`.
- **Tailscale** đã cài và đăng nhập trên VM và trên máy công ty:

  ```bash
  curl -fsSL https://tailscale.com/install.sh | sh
  ```
  ```bash
  sudo tailscale up
  ```
  ```bash
  tailscale ip -4
  ```

  Ghi lại IP dạng `100.x.y.z`. Giao diện web sẽ chỉ nghe trên IP này.

---

## 1. Clone repo private (một lần)

### Cách A — `gh auth login` (dễ nhất)

```bash
sudo apt-get install -y gh
```
```bash
gh auth login
```

Lần lượt chọn: `GitHub.com` → `HTTPS` → `Yes` → `Login with a web browser`. Mở https://github.com/login/device trên máy công ty, dán mã 8 ký tự rồi bấm Authorize.

```bash
gh repo clone thailytran/puzzle-forge ~/puzzle-forge
```

### Cách B — Deploy key (chỉ đọc, chỉ cho repo này)

```bash
ssh-keygen -t ed25519 -C "puzzle-forge-vm" -f ~/.ssh/puzzle_forge_deploy -N ""
```
```bash
cat ~/.ssh/puzzle_forge_deploy.pub
```

Trên GitHub: repo → **Settings → Deploy keys → Add deploy key**. Dán nội dung file `.pub`, **không** tick "Allow write access".

```bash
cat >> ~/.ssh/config <<'CFG'
Host github-puzzle-forge
  HostName github.com
  User git
  IdentityFile ~/.ssh/puzzle_forge_deploy
  IdentitiesOnly yes
CFG
chmod 600 ~/.ssh/config
```
```bash
git clone git@github-puzzle-forge:thailytran/puzzle-forge.git ~/puzzle-forge
```

> Thư mục `~/puzzle-forge` chỉ là **nguồn code**. Bộ cài lấy code theo **tag phiên bản** (`v0.2.0`…) từ đây, nên đừng xoá nó.

---

## 2. Cài đặt (một lệnh)

Chạy thử ở chế độ **test** trước (SKU giả `DEV-…`, Case Vault staging hoặc mock, ngân sách AI thấp):

```bash
cd ~/puzzle-forge && sudo bash scripts/install.sh --env test
```

Script làm 9 bước, chạy lại bao nhiêu lần cũng được:
1. Cài gói hệ thống (git, sqlite3, rclone…).
2. Tạo user hệ thống `forge` và các thư mục.
3. Tạo `/etc/puzzle-forge/forge.env`.
4. Cài uv, Python 3.12 và Typst đúng phiên bản đã ghim.
5. Lấy code theo tag mới nhất.
6. Cài thư viện Python.
7. Migrate database và chạy `forge doctor`.
8. Bật bản mới, cài các dịch vụ systemd.
9. In ra hướng dẫn tiếp theo.

Muốn cài một tag cụ thể: thêm `--ref v0.2.0`.

---

## 3. Đặt mật khẩu và mở giao diện web

```bash
sudo forge web set-password
```
```bash
sudo systemctl enable --now forge-web
```

Trên máy công ty (đã bật Tailscale), mở: `http://100.x.y.z:8710` → đăng nhập bằng mật khẩu vừa đặt.

Giao diện web **không bao giờ** nghe trên IP public. `forge web` từ chối mọi địa chỉ không phải localhost hoặc Tailscale.

---

## 4. Nhập khoá AI (Anthropic / OpenAI / Gemini)

Cách 1 (khuyên dùng) — trên web:
1. Vào **Cài đặt → AI Providers**, dán key rồi bấm **Lưu**.
   - Key được mã hoá vào `/etc/puzzle-forge/secrets.enc`.
   - Màn hình chỉ hiện 4 ký tự đầu và cuối của key.
2. Bấm **Test connection**.
3. Bấm **Tải model** để chọn model cho từng tác vụ.
4. Đặt **ngân sách** ngày / tháng / mỗi cuốn. Telegram cảnh báo khi chạm 80 %; tới 100 % thì dừng gọi AI.

Cách 2 — sửa file:
```bash
sudo nano /etc/puzzle-forge/forge.env
```
Sau đó khởi động lại:
```bash
sudo forge restart
```

Kiểm tra từ terminal:
```bash
sudo forge ai test
```
Thêm `--call` để gọi thử 1 lần thật (tốn vài xu):
```bash
sudo forge ai test --call
```

---

## 5. Chạy thử end-to-end (smoke test)

```bash
sudo forge smoke
```

Lệnh này làm 4 việc:
1. Chạy `forge doctor`.
2. Tạo một cuốn word search mẫu và một cuốn escape mẫu (chế độ test).
3. Chạy QA tới `QA_PASSED`, rồi đẩy lên Case Vault **staging** (hoặc mock).
4. Thử redeem trên staging.

Kết thúc phải in `Smoke test passed`.

Tạo sách thật trên web: **Tạo sách** → điền form (hoặc upload CSV) → sách vào hàng đợi. Worker build xong sẽ báo Telegram. Mở cuốn sách để xem báo cáo QA, tải PDF, bấm Duyệt hoặc Từ chối.

Chuyển sang **prod** khi đã sẵn sàng (xem `docs/GO_LIVE.md`):
```bash
cd ~/puzzle-forge && sudo bash scripts/install.sh --env prod
```

---

## 6. Cập nhật phiên bản

```bash
sudo forge update
```

Lệnh này lấy **tag mới nhất** trong `~/puzzle-forge`, rồi:
1. Cài vào `releases/<tag>`.
2. Migrate database.
3. Chạy `forge doctor`.
4. **Chỉ khi mọi bước đều ổn** mới chuyển `current` sang bản mới và restart dịch vụ. Lỗi ở bất kỳ bước nào thì bản cũ vẫn chạy.

Cập nhật lên một tag cụ thể (hoặc quay lại bản trước):
```bash
sudo forge update --ref v0.2.0
```

Xem phiên bản đang chạy:
```bash
forge --version
```

---

## 7. Sao lưu và khôi phục

Sao lưu tự động lúc 03:20 mỗi ngày (giữ 14 bản trong `/var/lib/puzzle-forge/backups/`). Chạy tay:

```bash
sudo forge backup
```

Mỗi lần tạo **hai** file:
- `forge-data-…tar.gz`: database và toàn bộ sách.
- `forge-config-…tar.gz`: cấu hình và **khoá mã hoá**. Hãy giữ file này kỹ.

### Đẩy bản sao lưu lên Google Drive (tuỳ chọn)

```bash
sudo -u forge rclone config
```

Tạo remote tên `gdrive`, kiểu `drive`, làm theo hướng dẫn đăng nhập. Sau đó vào web **Cài đặt** → `FORGE_BACKUP_REMOTE` = `gdrive:puzzle-forge-backups`.

Mặc định chỉ file **data** được đẩy lên. Muốn đẩy cả file config, phải dùng remote `crypt` của rclone và đặt `FORGE_BACKUP_INCLUDE_SECRETS=1`.

### Khôi phục

```bash
sudo forge restore --data /var/lib/puzzle-forge/backups/forge-data-YYYYMMDD-HHMMSS.tar.gz --config /var/lib/puzzle-forge/backups/forge-config-YYYYMMDD-HHMMSS.tar.gz
```

Lệnh tự dừng dịch vụ, khôi phục, rồi chạy lại dịch vụ.

---

## 8. Lệnh quản trị hay dùng

| Việc | Lệnh |
|---|---|
| Tình trạng dịch vụ | `forge status` |
| Xem log (web / worker / backup) | `forge logs`, `forge logs worker` |
| Khởi động lại | `sudo forge restart` |
| Tự kiểm tra máy | `sudo forge doctor` |
| Chi phí AI | `sudo forge ai usage --by book_id` |
| Hàng đợi Case Vault | `sudo forge vault status` |

---

## 9. Lỗi thường gặp

| Triệu chứng | Cách xử lý |
|---|---|
| Không mở được `http://100.x.y.z:8710` | Kiểm tra `tailscale status` trên cả hai máy, rồi `forge status`. Nếu `forge-web` chưa chạy: `sudo forge web set-password && sudo systemctl enable --now forge-web`. |
| `forge-web` khởi động lại liên tục | Tailscale chưa có IP lúc khởi động; dịch vụ tự thử lại sau 10 giây. Xem `forge logs web`. |
| `doctor failed – current release left unchanged` khi update | Bản mới có lỗi nên bản cũ vẫn chạy. Gửi log `forge logs` cho Claude Code. |
| `unknown ref vX.Y.Z` | Tag chưa có trong `~/puzzle-forge`: `cd ~/puzzle-forge && git fetch --tags`. |
| `AI budget … reached` | Hết ngân sách AI: tăng ngân sách trong **Cài đặt** hoặc chờ sang ngày/tháng mới. |
| `FORGE_ENV=prod refuses the dev SKU provider` | Ở prod phải dùng Hub thật: đặt `FORGE_SKU_PROVIDER=hub`, `HUB_URL` và `HUB_TOKEN`. |
| `Permission denied (publickey)` khi update | Deploy key / gh không còn hiệu lực trong `~/puzzle-forge`. Thử `ssh -T git@github-puzzle-forge` hoặc `gh auth status`. |
| `rclone … failed` | Chạy `sudo -u forge rclone lsd gdrive:` để kiểm tra đăng nhập Drive. |

Máy phát triển (không cài dịch vụ) vẫn dùng được `bash scripts/setup_vm.sh` trong checkout, như trước.
