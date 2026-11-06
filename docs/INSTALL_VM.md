# Cài Puzzle Forge trên VM Ubuntu 24.04 (cá nhân)

Hướng dẫn copy‑paste từng khối lệnh. Chạy bằng **user thường** (có quyền `sudo`), **không** chạy bằng root.
Thời gian: khoảng 5–10 phút.

---

## 0. Yêu cầu

- Ubuntu 24.04 (x86_64 hoặc arm64), có Internet.
- Đã đăng nhập vào VM (qua Tailscale: `ssh <user>@<tên-vm>`).
- Repo GitHub `thailytran/puzzle-forge` là **private**, nên phải xác thực trước khi clone (chọn **cách A** hoặc **cách B**).

```bash
sudo apt-get update && sudo apt-get install -y git curl
```

---

## 1. Clone repo private

### Cách A — `gh auth login` (dễ nhất)

```bash
sudo apt-get install -y gh
```

```bash
gh auth login
```

Chọn lần lượt: `GitHub.com` → `HTTPS` → `Yes` (authenticate Git) → `Login with a web browser`.
Lệnh sẽ in ra một mã 8 ký tự. Mở https://github.com/login/device trên máy công ty, dán mã vào rồi bấm Authorize.

```bash
gh repo clone thailytran/puzzle-forge ~/puzzle-forge
```

### Cách B — Deploy key (chỉ cho repo này, chỉ đọc)

1. Tạo key trên VM:

```bash
ssh-keygen -t ed25519 -C "puzzle-forge-vm" -f ~/.ssh/puzzle_forge_deploy -N ""
```

```bash
cat ~/.ssh/puzzle_forge_deploy.pub
```

2. Trên GitHub: repo → **Settings → Deploy keys → Add deploy key**. Title `vm`, dán nội dung file `.pub`,
   **không** tick "Allow write access", rồi bấm Add key.

3. Khai báo key cho SSH:

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

(Lần đầu SSH hỏi `Are you sure you want to continue connecting` thì gõ `yes`.)

---

## 2. Chọn branch

Trước khi PR được merge, code mới nằm trên branch đang làm (xem trong PR trên GitHub). Ví dụ:

```bash
cd ~/puzzle-forge && git fetch && git checkout claude/quirky-wright-imdimf
```

Khi PR đã merge vào `main`:

```bash
cd ~/puzzle-forge && git checkout main && git pull
```

---

## 3. Chạy script cài đặt (một lệnh)

```bash
cd ~/puzzle-forge && bash scripts/setup_vm.sh --with-tests
```

Script tự làm, và **chạy lại nhiều lần cũng an toàn**:

1. Cài gói apt: `curl ca-certificates git xz-utils sqlite3` (sẽ hỏi mật khẩu sudo).
2. Thêm `~/.local/bin` vào `PATH` (ghi một lần vào `~/.bashrc`).
3. Cài `uv` và Python 3.12 (do uv quản lý, không đụng vào Python của hệ thống).
4. Cài **Typst 0.14.2** (đúng phiên bản đã ghim) vào `~/.local/bin/typst`.
5. Kiểm tra font OFL có sẵn trong `assets/fonts/`.
6. `uv sync` (tạo `.venv`), tạo `.env` từ `.env.example` (quyền 600), tạo các thư mục `output/` và `data/`.
7. Chạy test (`--with-tests`) và `forge doctor`.

Sau khi xong, mở terminal mới (hoặc chạy `source ~/.bashrc`).

---

## 4. Kiểm tra

```bash
cd ~/puzzle-forge && uv run forge doctor
```

Kết quả mong đợi: mọi dòng **OK** (xanh). Riêng `API keys` có thể là **WARN** (vàng), vì chưa cần cho tới phase P2.
Có dòng **FAIL** (đỏ) thì lệnh trả mã lỗi 1; xem mục 7.

Tạo thử một PDF mẫu:

```bash
uv run forge layout demo --trim 8.5x11 --out output/layout_demo
```

File kết quả là `~/puzzle-forge/output/layout_demo/interior.pdf`.

---

## 5. Lấy PDF về máy công ty để xem

Chọn một trong các cách sau.

- **scp qua Tailscale** (chạy trên máy công ty):

  ```bash
  scp <user>@<tên-vm>:~/puzzle-forge/output/layout_demo/interior.pdf .
  ```

- **Tailscale Taildrop** (chạy trên VM):

  ```bash
  tailscale file cp ~/puzzle-forge/output/layout_demo/interior.pdf <tên-máy-công-ty>:
  ```

- **Web server tạm** chỉ nghe trên IP Tailscale (chạy trên VM, bấm Ctrl+C để tắt):

  ```bash
  cd ~/puzzle-forge/output && python3 -m http.server 8765 --bind "$(tailscale ip -4)"
  ```

  Sau đó mở trình duyệt trên máy công ty: `http://<ip-tailscale-của-vm>:8765/`

---

## 6. Cập nhật khi có code mới

```bash
cd ~/puzzle-forge && bash scripts/update.sh
```

Lệnh này làm: `git pull --ff-only` → `uv sync` → `pytest` → `forge doctor`.
Muốn chuyển sang branch khác: `bash scripts/update.sh <tên-branch>`.

---

## 7. Lỗi thường gặp

| Triệu chứng | Cách xử lý |
|---|---|
| `uv: command not found` | `source ~/.bashrc` hoặc mở terminal mới. |
| `Typst ... WARN CLI missing` | Tải typst bị lỗi; chạy lại `bash scripts/setup_vm.sh`. Trong lúc đó tool vẫn chạy được nhờ gói Python `typst` dự phòng. |
| `Typst ... WARN (pinned 0.14.2)` | Máy đang có typst bản khác trong `PATH`. Chạy lại script: script sẽ cài bản đã ghim vào `~/.local/bin` (thư mục này đứng đầu `PATH`). |
| `Output dir FAIL` | Kiểm tra quyền thư mục: `ls -ld ~/puzzle-forge/output` (thư mục phải thuộc user của bạn). |
| `Permission denied (publickey)` khi clone | Deploy key chưa được thêm, hoặc file `~/.ssh/config` sai. Thử `ssh -T git@github-puzzle-forge`. |
| `uv sync --locked` báo lock lỗi thời | Bạn đang ở commit cũ; chạy `git pull` rồi chạy lại. |

Khi báo lỗi cho Claude Code, dùng mẫu số 4 trong `docs/PROMPTS.md` (dán lệnh và log).
