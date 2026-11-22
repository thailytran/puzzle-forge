// End-to-end tests of the CaseVault Worker against the acceptance list (spec §10), on a local D1/R2.
// Run: node apps/casevault_cf/build.mjs && node --test apps/casevault_cf/tests/
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import worker, { _test } from "../dist/worker.js";
import { d1, r2, fakeFetch } from "./shim.mjs";

const VEC = JSON.parse(readFileSync(new URL("./vectors.json", import.meta.url)));
const KEY = VEC.answer_key;

function makeEnv() {
  _test.resetSchemaFlag();
  const log = [];
  return { env: { DB: d1(), FILES: r2(), BOOKS: r2(), VAULT_ANSWER_KEY: KEY, VAULT_ADMIN_TOKEN: "admin-token-123456", ENV_NAME: "staging", SITE_URL: "https://cv.test", FETCH: fakeFetch(log) }, log };
}

class Client {
  constructor(env, ip = "203.0.113.5") { this.env = env; this.jar = {}; this.ip = ip; }
  async req(method, path, body, extra = {}) {
    const headers = { "cf-connecting-ip": this.ip, cookie: Object.entries(this.jar).map(([k, v]) => `${k}=${v}`).join("; "), ...extra };
    let payload;
    if (body instanceof FormData) payload = body;
    else if (body) { headers["content-type"] = "application/x-www-form-urlencoded"; payload = new URLSearchParams(body).toString(); }
    const res = await worker.fetch(new Request(`https://cv.test${path}`, { method, headers, body: payload, redirect: "manual" }), this.env, null);
    for (const c of res.headers.getSetCookie ? res.headers.getSetCookie() : []) {
      const [kv] = c.split(";");
      const i = kv.indexOf("=");
      this.jar[kv.slice(0, i)] = kv.slice(i + 1);
    }
    res.text_ = await res.text();
    return res;
  }
  get(p) { return this.req("GET", p); }
  post(p, b, h) { return this.req("POST", p, b, h); }
}

async function hashes(bookId, variants, kind = "culprit_name") {
  return Promise.all(variants.map((v) => _test.answerHash(KEY, bookId, kind, v)));
}
async function seed(env, { total = 3, release2 = null } = {}) {
  const books = [];
  for (let i = 1; i <= total; i++) {
    const id = `PF-CASE-00${i}`;
    books.push({ book_id: id, book_code_prefix: `CASE0${i}`, title: `Case ${i}`, skus: [`SKU-${i}`], etsy_listing_ids: [String(1000 + i)],
      shopify_product_id: String(500 + i), answer_hash: (await hashes(id, ["Captain Reed"]))[0], accepted_variants: await hashes(id, ["Reed"]),
      extended_ending: `Ending of case ${i}`, series_id: "S1", series_title: "Harbor Mysteries", series_order: i, series_total: total,
      next_book_id: i < total ? `PF-CASE-00${i + 1}` : null, next_series_id: "S2", release_date: i === 2 && release2 ? release2 : "2026-01-01", line: "mystery" });
  }
  books.push({ book_id: "PF-S2-001", book_code_prefix: "STWO01", title: "Series Two Book One", skus: ["SKU-S2"], answer_hash: (await hashes("PF-S2-001", ["x"]))[0],
    series_id: "S2", series_title: "Series Two", series_order: 1, series_total: 8, release_date: "2026-01-01", download_url: "https://get.colorilax.com/x" });
  const r = await worker.fetch(new Request("https://cv.test/api/admin/books", { method: "POST", headers: { authorization: `Bearer ${env.VAULT_ADMIN_TOKEN}`, "content-type": "application/json" }, body: JSON.stringify(books) }), env, null);
  assert.equal(r.status, 200, await r.clone().text());
  await _test.setSetting(env, "shopify_shop", "colorilax.myshopify.com");
  await _test.setSetting(env, "shopify_token", "shpat_test");
}
async function bookCode(env, bookId) {
  const r = await worker.fetch(new Request("https://cv.test/api/internal/bookcode", { method: "POST", headers: { authorization: `Bearer ${env.VAULT_ADMIN_TOKEN}` }, body: JSON.stringify({ book_id: bookId, order: "#1001" }) }), env, null);
  return (await r.json()).code;
}
async function solveAndSignIn(c, bookId, answer = "captain reed", signup = {}) {
  const r = await c.post("/check", { book: bookId, a_culprit_name: answer });
  assert.match(r.text_, /CASE SOLVED/);
  const claim = /\/claim\?s=([^"&]+)/.exec(r.text_)[1];
  if (!c.signedIn) {
    const l = await c.post("/login", { email: signup.email || "jane@example.com", terms: "1", next: `/claim?s=${claim}`, ...signup });
    const link = /href="https:\/\/cv\.test(\/auth\?t=[^"]+)"/.exec(l.text_)[1];
    const a = await c.get(link.replace(/&amp;/g, "&"));
    assert.equal(a.status, 303);
    c.signedIn = true;
  }
  return decodeURIComponent(claim);
}
const acc = (env, email = "jane@example.com") => env.DB.prepare("SELECT * FROM accounts WHERE email=?").bind(email).first();

test("normalisation and hashes match Puzzle Forge (shared vectors)", async () => {
  for (const c of VEC.cases) {
    assert.equal(_test.normalizeAnswer(c.kind, c.text), c.norm);
    assert.equal(await _test.answerHash(KEY, "PF-CASE-001", c.kind, c.text), c.hash);
  }
  for (const c of VEC.codes) assert.equal(await _test.bookCodeHash(KEY, c.book_id, c.code), c.hash);
});

test("book code format, csv parser, totp", async () => {
  const code = _test.newBookCode("CASE01");
  assert.ok(_test.codeLooksValid(code, "CASE01"));
  assert.ok(!/[01OIL]/.test(code.split("-")[1]));
  assert.ok(!_test.codeLooksValid("CASE01-ABCD0000", "CASE01"));
  const rows = _test.parseCsv('Sale Date,Order ID,SKU\n11/20/26,"3456789012",SKU-1\r\n');
  assert.deepEqual(rows, [{ "Sale Date": "11/20/26", "Order ID": "3456789012", SKU: "SKU-1" }]);
  // RFC 6238 test vector (SHA-1, T=59s) -> 94287082 -> last 6 digits
  const secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ";
  assert.equal(await _test.totpAt(secret, 1), "287082");
  assert.ok(await _test.pwCheck("correct horse battery", await _test.pwHash("correct horse battery")));
});

test("wrong answers: no answer leak, lockout after 5", async () => {
  const { env } = makeEnv();
  await seed(env);
  const c = new Client(env);
  const home = await c.get("/?book=PF-CASE-001");
  assert.doesNotMatch(home.text_, /captain|reed|[0-9a-f]{64}/i);
  for (let i = 0; i < 5; i++) {
    const r = await c.post("/check", { book: "PF-CASE-001", a_culprit_name: "Lady Grey" });
    assert.match(r.text_, /Not quite, detective/);
    assert.doesNotMatch(r.text_, /reed/i);
  }
  const r6 = await c.post("/check", { book: "PF-CASE-001", a_culprit_name: "captain reed" });
  assert.match(r6.text_, /Too many tries/);
});

test("case, accents and spaces still count; extended ending without account", async () => {
  const { env } = makeEnv();
  await seed(env);
  const r = await new Client(env).post("/check", { book: "PF-CASE-001", a_culprit_name: "  CAPTAIN  réed " });
  assert.match(r.text_, /CASE SOLVED/);
  assert.match(r.text_, /Ending of case 1/);
  const v = await new Client(env, "198.51.100.2").post("/check", { book: "PF-CASE-001", a_culprit_name: "reed" });
  assert.match(v.text_, /CASE SOLVED/);
});

test("Book Code claim: Shopify 15% code for the next book, 150 points, code reuse refused", async () => {
  const { env, log } = makeEnv();
  await seed(env);
  const c = new Client(env);
  const claim = await solveAndSignIn(c, "PF-CASE-001");
  const code = await bookCode(env, "PF-CASE-001");
  const r = await c.post("/claim", { s: claim, channel: "shop", code: code.toLowerCase() });
  assert.equal(r.status, 303, r.text_);
  const a = await acc(env);
  assert.equal(a.points_total, 20 + 100 + 30);
  const rw = await env.DB.prepare("SELECT * FROM rewards WHERE account_id=?").bind(a.id).first();
  assert.equal(rw.status, "issued");
  assert.equal(rw.book_id, "PF-CASE-002");
  assert.equal(rw.pct, 15);
  const shop = log.find((x) => x.url.includes("graphql"));
  assert.deepEqual(shop.body.variables.d.customerGets.items.products.productsToAdd, ["gid://shopify/Product/502"]);
  assert.equal(shop.body.variables.d.usageLimit, 1);
  // newsletter not ticked -> no marketing subscription queued
  const subs = await env.DB.prepare("SELECT COUNT(*) AS n FROM outbox WHERE kind='klaviyo_sub'").first();
  assert.equal(subs.n, 0);
  // same code again (another reader) is refused
  const c2 = new Client(env, "192.0.2.77");
  const claim2 = await solveAndSignIn(c2, "PF-CASE-001", "reed", { email: "bob@example.com" });
  const r2 = await c2.post("/claim", { s: claim2, channel: "print", code });
  assert.match(r2.text_, /already been used/);
  const b = await acc(env, "bob@example.com");
  assert.equal(b.points_total, 20);
});

test("Etsy: known order -> pool coupon; unknown -> pending until CSV upload", async () => {
  const { env } = makeEnv();
  await seed(env);
  // admin: setup + 2FA + pool + CSV
  const admin = new Client(env, "10.0.0.9");
  await admin.post("/admin", { do: "setup", token: env.VAULT_ADMIN_TOKEN, pw: "a-long-owner-password" });
  await admin.get("/admin");
  const secret = await _test.getSetting(env, "admin_totp_pending");
  await admin.post("/admin", { do: "totp_enrol", code: await _test.totpAt(secret, Math.floor(Date.now() / 30000)) });
  const ov = await admin.get("/admin?s=overview");
  assert.match(ov.text_, /Submissions/);
  await admin.post("/admin/act", { do: "pool_add", pct: "15", codes: "ETSY15A\nETSY15B" });

  const c = new Client(env);
  const claim = await solveAndSignIn(c, "PF-CASE-001");
  const r = await c.post("/claim", { s: claim, channel: "etsy", order: "3456789012" });
  assert.equal(r.status, 303);
  let a = await acc(env);
  assert.equal(a.points_total, 20); // pending: nothing yet
  const s = await env.DB.prepare("SELECT status FROM solves WHERE account_id=?").bind(a.id).first();
  assert.equal(s.status, "pending");

  const fd = new FormData();
  fd.append("do", "etsy_csv");
  fd.append("file", new File(["Sale Date,Item Name,Buyer,Order ID,Listing ID,SKU\n11/20/2026,Case 1,Jane Doe,3456789012,1001,SKU-1\n"], "orders.csv", { type: "text/csv" }));
  const up = await admin.post("/admin/act", fd);
  assert.match(decodeURIComponent(up.headers.get("location")), /1 pending rewards released/);
  a = await acc(env);
  assert.equal(a.points_total, 150);
  const rw = await env.DB.prepare("SELECT * FROM rewards WHERE account_id=?").bind(a.id).first();
  assert.equal(rw.code, "ETSY15A");
  const stored = await env.DB.prepare("SELECT * FROM etsy_orders").all();
  assert.deepEqual(Object.keys(stored.results[0]).sort(), ["listing_id", "order_id", "sale_date", "sku"]); // no buyer name kept
});

test("series of 3: coupons for books 2-3, none after the finale, +200 and gift of next series", async () => {
  const { env } = makeEnv();
  await seed(env);
  const c = new Client(env);
  for (const id of ["PF-CASE-001", "PF-CASE-002", "PF-CASE-003"]) {
    const claim = await solveAndSignIn(c, id);
    const r = await c.post("/claim", { s: claim, channel: "print", code: await bookCode(env, id) });
    assert.equal(r.status, 303, r.text_);
  }
  const a = await acc(env);
  assert.equal(a.points_total, 20 + 3 * 130 + 200);
  const rws = (await env.DB.prepare("SELECT kind, book_id, status FROM rewards WHERE account_id=? ORDER BY id").bind(a.id).all()).results;
  assert.deepEqual(rws.map((r) => `${r.kind}:${r.book_id}`), ["coupon:PF-CASE-002", "coupon:PF-CASE-003", "gift:PF-S2-001"]);
  // solving book 1 again counts nothing
  const claim = await solveAndSignIn(c, "PF-CASE-001");
  await c.post("/claim", { s: claim, channel: "print", code: await bookCode(env, "PF-CASE-001") });
  assert.equal((await acc(env)).points_total, 20 + 3 * 130 + 200);
  const page = await c.get("/account");
  assert.match(page.text_, /Detective File|DETECTIVE FILE/);
  assert.match(page.text_, /Series Two Book One/);
  assert.match(page.text_, /3\/3/);
});

test("next book not released: coupon waits and is issued on release day", async () => {
  const { env } = makeEnv();
  await seed(env, { release2: "2099-01-01" });
  const c = new Client(env);
  const claim = await solveAndSignIn(c, "PF-CASE-001");
  await c.post("/claim", { s: claim, channel: "print", code: await bookCode(env, "PF-CASE-001") });
  let rw = await env.DB.prepare("SELECT * FROM rewards").first();
  assert.equal(rw.status, "waiting_release");
  await env.DB.prepare("UPDATE books SET release_date='2026-01-01' WHERE book_id='PF-CASE-002'").run();
  await _test.releaseDue(env);
  rw = await env.DB.prepare("SELECT * FROM rewards").first();
  assert.equal(rw.status, "issued");
  const ev = (await env.DB.prepare("SELECT payload FROM outbox WHERE kind='klaviyo_event'").all()).results.map((r) => JSON.parse(r.payload).metric);
  assert.ok(ev.includes("Next Book Released"));
});

test("Inspector redeems 1,200 points: available drops, tier stays", async () => {
  const { env } = makeEnv();
  await seed(env);
  const c = new Client(env);
  await solveAndSignIn(c, "PF-CASE-001");
  const a = await acc(env);
  await env.DB.prepare("UPDATE accounts SET points_total=1300, points_avail=1300, tier='Inspector' WHERE id=?").bind(a.id).run();
  const r = await c.post("/account/redeem", { book: "PF-S2-001" });
  assert.match(decodeURIComponent(r.headers.get("location")), /Done!/);
  const b = await acc(env);
  assert.equal(b.points_avail, 100);
  assert.equal(b.points_total, 1300);
  assert.equal(b.tier, "Inspector");
});

test("newsletter tick -> subscription queued + consent stored; login link single use", async () => {
  const { env } = makeEnv();
  await seed(env);
  const c = new Client(env);
  const l = await c.post("/login", { email: "Ann@Example.com", terms: "1", newsletter: "1", next: "/account" });
  const link = /href="https:\/\/cv\.test(\/auth\?t=[^"]+)"/.exec(l.text_)[1];
  assert.equal((await c.get(link)).status, 303);
  const again = await new Client(env).get(link);
  assert.match(again.text_, /expired|already used/);
  const sub = await env.DB.prepare("SELECT payload FROM outbox WHERE kind='klaviyo_sub'").first();
  assert.deepEqual(JSON.parse(sub.payload), { email: "ann@example.com", subscribe: true });
  const cons = await env.DB.prepare("SELECT * FROM consents").first();
  assert.equal(cons.value, 1);
  assert.match(cons.text, /Unsubscribe anytime/);
  // outbox delivers to Klaviyo through the fake network when a key is set
  await _test.setSetting(env, "klaviyo_key", "pk_test");
  await _test.setSetting(env, "klaviyo_list_id", "LIST1");
  const sent = await _test.processOutbox(env);
  assert.ok(sent >= 2);
  // the stored key is encrypted at rest
  const raw = await env.DB.prepare("SELECT v, enc FROM settings WHERE k='klaviyo_key'").first();
  assert.equal(raw.enc, 1);
  assert.notEqual(raw.v, "pk_test");
});

test("admin requires password + TOTP; internal API requires bearer", async () => {
  const { env } = makeEnv();
  const anon = new Client(env);
  const a = await anon.get("/admin?s=accounts");
  assert.match(a.text_, /First setup/);
  const bad = await anon.post("/admin", { do: "setup", token: "nope", pw: "a-long-owner-password" });
  assert.match(bad.text_, /Wrong setup token/);
  const api = await worker.fetch(new Request("https://cv.test/api/admin/books", { method: "POST", body: "[]" }), env, null);
  assert.equal(api.status, 401);
  // plaintext answers are refused at import
  const r = await worker.fetch(new Request("https://cv.test/api/admin/books", { method: "POST", headers: { authorization: `Bearer ${env.VAULT_ADMIN_TOKEN}` },
    body: JSON.stringify({ book_id: "X", title: "X", answers: { culprit_name: ["Captain Reed"] } }) }), env, null);
  assert.equal(r.status, 400);
});

test("daily jobs: birthday points once a year, backup to R2", async () => {
  const { env } = makeEnv();
  await seed(env);
  const c = new Client(env);
  await c.post("/login", { email: "bday@example.com", terms: "1", birth_month: String(new Date().getUTCMonth() + 1), next: "/account" }).then(async (l) => c.get(/href="https:\/\/cv\.test(\/auth\?t=[^"]+)"/.exec(l.text_)[1]));
  await _test.dailyJobs(env);
  await _test.dailyJobs(env);
  assert.equal((await acc(env, "bday@example.com")).points_total, 20 + 50);
  assert.ok([...env.FILES.m.keys()].some((k) => k.startsWith("casevault/staging/backup/")));
});
