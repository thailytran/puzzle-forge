# GO-LIVE checklist (tiếng Việt)

Đánh dấu `[x]` khi xong. Chỉ chuyển Puzzle Forge sang `FORGE_ENV=prod` và mở Case Vault prod cho khách khi **mọi** mục bắt buộc (★) đã đạt.

## A. Puzzle Forge (VM ở nhà)

- [ ] ★ Đã cài bằng tag phát hành: `forge --version` hiện `puzzle-forge X.Y.Z (sha) env=…`.
- [ ] ★ `sudo forge doctor` **xanh hết**. Riêng `API keys` được phép WARN nếu chưa dùng AI.
- [ ] ★ Smoke test ở chế độ test đạt: `sudo forge smoke` in `Smoke test passed`, kèm "Case solved" trên staging.
- [ ] ★ Web chỉ mở được qua Tailscale: `http://100.x.y.z:8710` vào được; IP LAN/public **không** vào được.
- [ ] ★ Đã đặt mật khẩu web (≥ 12 ký tự). Đăng nhập sai 5 lần thì bị khoá 15 phút.
- [ ] ★ Khoá AI thật đã nhập (Cài đặt → AI Providers) và `sudo forge ai test --call` OK.
- [ ] ★ **Ngân sách AI** đã đặt cho prod (ngày / tháng / mỗi cuốn). Telegram nhận được cảnh báo thử khi chạm 80 %.
- [ ] Định tuyến AI: đã chọn model cho từng tác vụ; `playtest_reader_A` và `_B` dùng **hai provider khác nhau**.
- [ ] ★ SKU prod: `FORGE_SKU_PROVIDER=hub`, `HUB_URL`, `HUB_TOKEN` thật. `forge doctor` không báo "prod must not use DEV SKUs".
- [ ] ★ Brand thật: tên, website, logo (Cài đặt → Brand); `configs/brand.yaml` đã hết `placeholder: true`.
- [ ] ★ **Backup chạy được**: `sudo forge backup` tạo 2 file; đã thử `sudo forge restore` trên một bản test.
- [ ] Backup ra ngoài: `FORGE_BACKUP_REMOTE` (rclone Google Drive) đã thử `rclone lsd`.
- [ ] Đã ghi `forge-config-*.tar.gz` (chứa khoá mã hoá) ra một nơi an toàn ngoài VM.
- [ ] Telegram: `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`, đã nhận tin "Job … done" từ worker.
- [ ] ★ Đổi sang prod: `cd ~/puzzle-forge && sudo bash scripts/install.sh --env prod`, rồi `sudo forge doctor`.

## B. Case Vault (Oracle Cloud)

- [ ] ★ DNS: `casevault.halosparkinc.com` và `staging.casevault.halosparkinc.com` trỏ đúng IP (`dig +short`).
- [ ] ★ HTTPS hợp lệ cho cả hai tên miền (ổ khoá xanh; securityheaders.com đạt A).
- [ ] ★ `https://casevault.halosparkinc.com/healthz` trả `"missing_config": []`.
- [ ] ★ Admin prod đã tạo, có **2FA**; đã thử đăng nhập và đăng xuất.
- [ ] ★ Key **thật** trong `/opt/casevault/prod/.env`: Turnstile, Klaviyo, Shopify (Etsy nếu có). Staging dùng key **test**.
- [ ] ★ `VAULT_ADMIN_TOKEN` và `VAULT_ANSWER_KEY` của prod khớp với Puzzle Forge prod, của staging khớp với Forge test.
- [ ] ★ Backup Postgres: `ls /opt/casevault/prod/backups` có file của hôm nay; đã thử `casevault restore` trên **staging**.
- [ ] Backup ra ngoài (Object Storage / Google Drive): `casevault upload on`, đã thấy file trên remote.
- [ ] ★ Cổng chỉ mở 22/80/443 (Security List + iptables). fail2ban đang chạy: `sudo fail2ban-client status sshd`.
- [ ] Telegram nhận được tin "suspicious activity" khi thử dùng lại một Book Code bằng email khác trên staging.

## C. Form, consent và luật thưởng

- [ ] ★ Câu chữ newsletter và Terms / Privacy đã được **rà soát pháp lý** (CAN-SPAM / CASL / GDPR). Đã sửa `config/casevault.yaml` và tăng `form_version`.
- [ ] ★ Ô newsletter **không tick sẵn**: khách US/CA bắt buộc tick, khách EU/UK không bắt buộc. Đã thử cả hai trên staging.
- [ ] ★ Trang Terms và Privacy có nội dung cuối (không còn dòng "Draft text").
- [ ] Luật thưởng: 10/20/30/40 % → sách tặng ở mốc 5, lặp vòng, coupon 90 ngày. Đã chốt các con số trong `casevault.yaml`.
- [ ] Không có câu nào xin hoặc thưởng cho review.

## D. Kho coupon và Shopify / Etsy

- [ ] ★ **Kho coupon Etsy**: mỗi mức 10/20/30/40 % có ≥ 50 mã đã import (trang admin → Coupon stock). Ngưỡng cảnh báo = 20.
- [ ] ★ Shopify app có quyền `read_orders` (+ `read_all_orders`) và `write_discounts`. Đã tạo thử 1 mã trên staging (development store).
- [ ] Quà mốc 5: mỗi sách digital có `shopify_product_ids` trong `vault.yaml` (để tạo mã 100 %).
- [ ] Etsy: nếu chưa có API, đã thử import CSV "Order Items" và thấy đơn *pending* được duyệt tự động.

## E. Klaviyo

- [ ] ★ List "Case Vault Newsletter" đã tạo; `KLAVIYO_LIST_ID` đúng.
- [ ] ★ Các Flow đã **Live** cho: Case Solved (nhánh tier 1–4 + quà), Verification Pending, Verification Approved, Verification Rejected, Gift Ready, Login Link.
- [ ] ★ Email thưởng là **transactional** (Klaviyo đã duyệt) và vẫn đến khách đã hủy newsletter.
- [ ] Mẫu email có logo brand, link chứng nhận, mã coupon, hạn dùng, tiến độ "x/5", link unsubscribe ở email marketing.
- [ ] Đã giải thử 1 vụ trên prod bằng email của anh: nhận đúng email, mã dùng được 1 lần trên shop.

## F. Sách đầu tiên lên prod

- [ ] ★ Sách đạt **QA_PASSED** và đã duyệt **APPROVED** trên web Forge.
- [ ] ★ `forge vault status` báo `sent`, và cuốn sách hiện trên `https://casevault.halosparkinc.com`.
- [ ] ★ Quét QR trang cuối bằng điện thoại thì mở đúng trang của cuốn sách.
- [ ] Book Code in kèm sách in (nếu bán bản in): `forge vault codes … --count N`, đã in thử 1 trang mã.
