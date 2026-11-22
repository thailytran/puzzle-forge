// ---- database helpers, settings (encrypted secrets), defaults ---------------------------------
let schemaReady = false;

async function ensureSchema(env) {
  if (schemaReady) return;
  const stmts = SCHEMA_SQL.split(";").map((s) => s.trim()).filter(Boolean);
  await env.DB.batch(stmts.map((s) => env.DB.prepare(s)));
  schemaReady = true;
}
const q = (env, sql, ...args) => env.DB.prepare(sql).bind(...args);
const one = (env, sql, ...args) => q(env, sql, ...args).first();
const all = async (env, sql, ...args) => (await q(env, sql, ...args).all()).results || [];
const run = (env, sql, ...args) => q(env, sql, ...args).run();

async function audit(env, actor, action, detail) {
  await run(env, "INSERT INTO audit_log(actor,action,detail,ts) VALUES(?,?,?,?)", actor, action,
    typeof detail === "string" ? detail : JSON.stringify(detail), nowIso());
}
async function flag(env, kind, detail, accountId = null) {
  await run(env, "INSERT INTO flags(kind,detail,account_id,ts) VALUES(?,?,?,?)", kind,
    typeof detail === "string" ? detail : JSON.stringify(detail), accountId, nowIso());
}

// Rules the owner can change in the admin (spec §3, §7). Changes apply from the moment of saving.
const DEFAULT_RULES = {
  points: { signup: 20, solve: 100, first_try: 30, series: 200, referral: 100, birthday: 50 },
  tiers: [["Rookie", 0], ["Detective", 300], ["Inspector", 800], ["Chief Inspector", 1500]],
  redeem_min_tier: "Inspector", redeem_cost: 1200, coupon_pct: 15, coupon_days: 90,
  points_expire_days: 730, wrong_per_hour: 5, ip_per_hour: 20, claim_hold_hours: 24,
  pending_days: 30, pool_warn: 10, solved_count_min: 100,
  support_email: "support@colorilax.com", shop_url: "https://colorilax.com", etsy_shop_url: "https://www.etsy.com/shop/ColorilaxBook",
};
// Keys whose values are secrets: stored AES-GCM encrypted, never shown back in the admin.
const SECRET_SETTINGS = ["shopify_token", "klaviyo_key", "turnstile_secret", "telegram_token", "mail_token"];
const PLAIN_SETTINGS = ["shopify_shop", "shopify_api_version", "klaviyo_list_id", "turnstile_site",
  "telegram_chat", "mail_provider", "mail_from", "mail_from_name", "rules", "terms_html", "privacy_html",
  "admin_pw", "admin_totp", "admin_totp_pending"];

async function settingsKey(env) {
  const base = env.MASTER_KEY || `cv-settings|${env.VAULT_ADMIN_TOKEN || ""}`;
  const raw = await crypto.subtle.digest("SHA-256", enc.encode(base));
  return crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["encrypt", "decrypt"]);
}
async function encryptStr(env, text) {
  const iv = new Uint8Array(12);
  crypto.getRandomValues(iv);
  const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, await settingsKey(env), enc.encode(text));
  const b = new Uint8Array(12 + ct.byteLength);
  b.set(iv); b.set(new Uint8Array(ct), 12);
  return btoa(String.fromCharCode(...b));
}
async function decryptStr(env, b64) {
  const b = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: b.slice(0, 12) }, await settingsKey(env), b.slice(12));
  return new TextDecoder().decode(pt);
}
async function getSetting(env, k, d = "") {
  const r = await one(env, "SELECT v, enc FROM settings WHERE k=?", k);
  if (!r) return d;
  if (!r.enc) return r.v;
  try { return await decryptStr(env, r.v); } catch { return d; }
}
async function setSetting(env, k, v) {
  if (v === null || v === undefined) return run(env, "DELETE FROM settings WHERE k=?", k);
  const secret = SECRET_SETTINGS.includes(k);
  const val = secret ? await encryptStr(env, String(v)) : String(v);
  await run(env, "INSERT INTO settings(k,v,enc) VALUES(?,?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v, enc=excluded.enc", k, val, secret ? 1 : 0);
}
async function rules(env) {
  const r = jparse(await getSetting(env, "rules", ""), {});
  return { ...DEFAULT_RULES, ...r, points: { ...DEFAULT_RULES.points, ...(r.points || {}) } };
}

// ---- rate limits ----------------------------------------------------------------------------
async function countAttempts(env, where, args, minutes = 60) {
  const since = isoAt(Date.now() - minutes * 60000);
  const r = await one(env, `SELECT COUNT(*) AS n FROM attempts WHERE ts >= ? AND ${where}`, since, ...args);
  return r ? r.n : 0;
}
async function logAttempt(env, a) {
  await run(env, "INSERT INTO attempts(book_id,ip,vid,account_id,scope,ok,ts) VALUES(?,?,?,?,?,?,?)",
    a.book_id || null, a.ip || null, a.vid || null, a.account_id || null, a.scope || "answer", a.ok ? 1 : 0, nowIso());
}

// ---- books & series ---------------------------------------------------------------------------
async function getBook(env, id) {
  return one(env, "SELECT * FROM books WHERE book_id=?", String(id || ""));
}
const released = (b) => !!b && b.status === "active" && (!b.release_date || b.release_date <= today());
async function publicBooks(env) {
  return all(env, `SELECT b.*, s.title AS series_title, s.total AS series_total, s.sort AS series_sort
    FROM books b LEFT JOIN series s ON s.series_id=b.series_id
    WHERE b.status IN ('active','upcoming') ORDER BY s.sort, b.series_id, b.series_order, b.title`);
}
