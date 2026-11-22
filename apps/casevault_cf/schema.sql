-- CaseVault on Cloudflare D1 (spec: claude.ai/artifact/RyCfS8phh9et8C18ttBZ8E, §9).
-- The Worker also runs this file on first request (CREATE ... IF NOT EXISTS), so a fresh D1 works.
CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT NOT NULL, enc INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS series (
  series_id TEXT PRIMARY KEY, title TEXT NOT NULL, line TEXT NOT NULL DEFAULT 'mystery',
  total INTEGER NOT NULL DEFAULT 10, next_series_id TEXT, release_date TEXT, sort INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS books (
  book_id TEXT PRIMARY KEY, prefix TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
  line TEXT NOT NULL DEFAULT 'mystery', series_id TEXT, series_order INTEGER, next_book_id TEXT,
  skus TEXT NOT NULL DEFAULT '[]', etsy_listing_ids TEXT NOT NULL DEFAULT '[]',
  shopify_product_id TEXT, etsy_url TEXT, shop_url TEXT,
  answers TEXT NOT NULL DEFAULT '{}', answer_label TEXT DEFAULT 'Final code',
  ending_text TEXT, extended_ending TEXT, blurb TEXT,
  status TEXT NOT NULL DEFAULT 'active', language TEXT DEFAULT 'en', edition TEXT DEFAULT '1',
  release_date TEXT, difficulty INTEGER, pages INTEGER, solve_minutes INTEGER, audience TEXT,
  cover_key TEXT, download_key TEXT, download_url TEXT, redeemable INTEGER NOT NULL DEFAULT 1,
  created TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS book_codes (
  code_hash TEXT PRIMARY KEY, book_id TEXT NOT NULL, tail TEXT, status TEXT NOT NULL DEFAULT 'new',
  ref TEXT, channel TEXT, created TEXT, used_by INTEGER, used_at TEXT);
CREATE INDEX IF NOT EXISTS ix_codes_book ON book_codes(book_id, status);
CREATE TABLE IF NOT EXISTS etsy_orders (
  order_id TEXT NOT NULL, sku TEXT NOT NULL DEFAULT '', listing_id TEXT NOT NULL DEFAULT '',
  sale_date TEXT, PRIMARY KEY (order_id, sku, listing_id));
CREATE TABLE IF NOT EXISTS accounts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL UNIQUE, email_norm TEXT NOT NULL,
  display_name TEXT, birth_month INTEGER, ref_code TEXT UNIQUE, referred_by INTEGER,
  tier TEXT NOT NULL DEFAULT 'Rookie', points_total INTEGER NOT NULL DEFAULT 0,
  points_avail INTEGER NOT NULL DEFAULT 0, newsletter INTEGER NOT NULL DEFAULT 0,
  locked INTEGER NOT NULL DEFAULT 0, name_consent INTEGER NOT NULL DEFAULT 0, birthday_year INTEGER,
  signup_ip TEXT, password_hash TEXT, google_sub TEXT, created TEXT, last_active TEXT);
CREATE INDEX IF NOT EXISTS ix_acc_norm ON accounts(email_norm);
CREATE TABLE IF NOT EXISTS login_tokens (
  token_hash TEXT PRIMARY KEY, email TEXT NOT NULL, data TEXT, expires TEXT NOT NULL, used INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS sessions (sid_hash TEXT PRIMARY KEY, account_id INTEGER NOT NULL, expires TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS admin_sessions (sid_hash TEXT PRIMARY KEY, expires TEXT NOT NULL, ok2fa INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, book_id TEXT, ip TEXT, vid TEXT, account_id INTEGER,
  scope TEXT NOT NULL DEFAULT 'answer', ok INTEGER NOT NULL, ts TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_att ON attempts(scope, ip, ts);
CREATE TABLE IF NOT EXISTS solves (
  id INTEGER PRIMARY KEY AUTOINCREMENT, book_id TEXT NOT NULL, account_id INTEGER,
  claim_hash TEXT UNIQUE, first_try INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'open',
  channel TEXT, proof_kind TEXT, proof TEXT, ip TEXT, created TEXT, claimed_at TEXT, verified_at TEXT);
CREATE INDEX IF NOT EXISTS ix_solves_acc ON solves(account_id, status);
CREATE INDEX IF NOT EXISTS ix_solves_proof ON solves(proof_kind, proof);
CREATE TABLE IF NOT EXISTS points_ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT, account_id INTEGER NOT NULL, d_total INTEGER NOT NULL,
  d_avail INTEGER NOT NULL, reason TEXT NOT NULL, ref TEXT, ts TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ux_ledger_once ON points_ledger(account_id, reason, ref);
CREATE TABLE IF NOT EXISTS rewards (
  id INTEGER PRIMARY KEY AUTOINCREMENT, account_id INTEGER NOT NULL, kind TEXT NOT NULL,
  book_id TEXT, channel TEXT, code TEXT, pct INTEGER, status TEXT NOT NULL, expires TEXT,
  solve_id INTEGER, note TEXT, created TEXT, issued_at TEXT);
CREATE TABLE IF NOT EXISTS referrals (
  id INTEGER PRIMARY KEY AUTOINCREMENT, referrer_id INTEGER NOT NULL, referee_id INTEGER NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'waiting', reason TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS etsy_coupon_pool (
  code TEXT PRIMARY KEY, pct INTEGER NOT NULL DEFAULT 15, status TEXT NOT NULL DEFAULT 'free',
  account_id INTEGER, issued_at TEXT, expires TEXT);
CREATE TABLE IF NOT EXISTS consents (
  id INTEGER PRIMARY KEY AUTOINCREMENT, account_id INTEGER, email TEXT, value INTEGER NOT NULL,
  text TEXT NOT NULL, source TEXT NOT NULL, ip_trunc TEXT, ts TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notify (email TEXT NOT NULL, book_id TEXT NOT NULL, ts TEXT, PRIMARY KEY (email, book_id));
CREATE TABLE IF NOT EXISTS outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, payload TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0, next_at TEXT NOT NULL, last_error TEXT, done INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_outbox ON outbox(done, next_at);
CREATE TABLE IF NOT EXISTS flags (
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, detail TEXT, account_id INTEGER,
  status TEXT NOT NULL DEFAULT 'open', ts TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT, action TEXT, detail TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS free_books (
  handle TEXT PRIMARY KEY, title TEXT NOT NULL, file_key TEXT NOT NULL, catalog_no TEXT NOT NULL DEFAULT '',
  interest TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1, updated TEXT);
CREATE TABLE IF NOT EXISTS free_claims (
  id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL, email_norm TEXT NOT NULL UNIQUE, handle TEXT NOT NULL,
  catalog_no TEXT, title TEXT NOT NULL, file_key TEXT NOT NULL, source TEXT, consent INTEGER NOT NULL DEFAULT 0,
  ip_trunc TEXT, token TEXT NOT NULL UNIQUE, expires TEXT NOT NULL, created TEXT NOT NULL, downloads INTEGER NOT NULL DEFAULT 0, last_download TEXT);
