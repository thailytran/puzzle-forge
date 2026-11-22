// ---- owner admin (spec §8): password + TOTP, never shows answers or stored secrets --------------
const ADMIN_SECTIONS = [["overview", "Overview"], ["books", "Books"], ["series", "Series"], ["codes", "Book Codes"], ["etsy", "Etsy orders"],
  ["pool", "Etsy coupons"], ["accounts", "Accounts"], ["flags", "Alerts"], ["gifts", "Gifts"], ["rules", "Point rules"], ["settings", "Settings"], ["security", "Security"], ["outbox", "Outbox"]];

function adminLayout(title, inner, section) {
  return html(`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>${esc(title)} · Case Vault admin</title><style>${CSS}
body{background:#f4efe3;color:#1b1a17}.adm{display:grid;grid-template-columns:190px 1fr;min-height:100vh}.adm nav{background:var(--ink);padding:14px}.adm nav a{display:block;color:var(--ivory);padding:7px 10px;border-radius:6px;text-decoration:none;font-size:14px}
.adm nav a.on{background:var(--brass);color:var(--ink)}.adm main{padding:20px;max-width:1100px}.adm .card{margin-bottom:14px}textarea{min-height:120px;font-family:monospace;font-size:13px}
@media(max-width:760px){.adm{grid-template-columns:1fr}}</style></head><body>
${section ? `<div class="adm"><nav><div class="mono" style="color:var(--brass);margin:0 10px 10px">CASE VAULT · ADMIN</div>${ADMIN_SECTIONS.map(([k, l]) => `<a href="/admin?s=${k}"${k === section ? ' class="on"' : ""}>${l}</a>`).join("")}<a href="/admin/logout">Sign out</a></nav><main>${inner}</main></div>`
    : `<div class="wrap" style="max-width:480px;padding-top:40px">${inner}</div>`}</body></html>`);
}

async function adminSession(env, req) {
  const sid = cookies(req).cv_admin;
  if (!sid) return null;
  const s = await one(env, "SELECT * FROM admin_sessions WHERE sid_hash=? AND expires>?", await sha256(sid), nowIso());
  return s && s.ok2fa ? s : null;
}

async function adminEntry(env, req, url) {
  const pw = await getSetting(env, "admin_pw", "");
  const totp = await getSetting(env, "admin_totp", "");
  if (req.method === "POST") return adminAuthPost(env, req, pw, totp);
  if (!pw) return adminLayout("Setup", `<div class="card"><h2>First setup</h2><p>Create the owner password. The setup token is the <code>VAULT_ADMIN_TOKEN</code> secret you saved in Cloudflare.</p>
<form method="post"><input type="hidden" name="do" value="setup"><label>Setup token</label><input type="text" name="token" required autocomplete="off">
<label>New password (12+ characters)</label><input type="text" name="pw" required minlength="12" autocomplete="new-password" style="-webkit-text-security:disc">
<p><button class="btn">Continue</button></p></form></div>`);
  return adminLayout("Sign in", `<div class="card"><h2>Owner sign-in</h2><form method="post"><input type="hidden" name="do" value="login">
<label>Password</label><input type="text" name="pw" required autocomplete="current-password" style="-webkit-text-security:disc">
${totp ? `<label>6-digit code</label><input type="text" name="code" inputmode="numeric" maxlength="6" required>` : ""}<p><button class="btn">Sign in</button></p></form></div>`);
}

async function adminAuthPost(env, req, pw, totp) {
  const f = await readBody(req);
  const ip = clientIp(req);
  if ((await countAttempts(env, "scope='admin' AND ok=0 AND ip=?", [ip])) >= 8) return adminLayout("Locked", `<div class="err">Too many failed sign-ins. Try again in an hour.</div>`);
  const fail = async (m) => { await logAttempt(env, { ip, scope: "admin", ok: 0 }); return adminLayout("Sign in", `<div class="err">${m}</div><p><a href="/admin">Back</a></p>`); };
  const newSession = async (ok2fa) => {
    const sid = randomToken(32);
    await run(env, "INSERT INTO admin_sessions(sid_hash,expires,ok2fa) VALUES(?,?,?)", await sha256(sid), isoAt(Date.now() + 12 * 3600000), ok2fa ? 1 : 0);
    return redirect("/admin", { "set-cookie": setCookie("cv_admin", sid, 12 * 3600, "/admin") });
  };
  if (f.do === "setup" && !pw) {
    if (!env.VAULT_ADMIN_TOKEN || !timingSafeEq(String(f.token || ""), env.VAULT_ADMIN_TOKEN)) return fail("Wrong setup token.");
    if (String(f.pw || "").length < 12) return fail("Password must have at least 12 characters.");
    await setSetting(env, "admin_pw", await pwHash(f.pw));
    await audit(env, "owner", "admin_setup", {});
    return newSession(true);
  }
  if (f.do === "login") {
    if (!(await pwCheck(String(f.pw || ""), pw))) return fail("Wrong password or code.");
    if (totp && !(await totpOk(totp, f.code))) return fail("Wrong password or code.");
    return newSession(true);
  }
  return redirect("/admin");
}

const tbl = (rows, cols) => `<table class="t"><tr>${cols.map((c) => `<th>${esc(c[1])}</th>`).join("")}</tr>${rows.map((r) =>
  `<tr>${cols.map((c) => `<td>${typeof c[2] === "function" ? c[2](r) : esc(r[c[0]])}</td>`).join("")}</tr>`).join("")}</table>`;
const actForm = (doName, fields, label, confirm) => `<form method="post" action="/admin/act" class="row"${confirm ? ` onsubmit="return confirm(${esc(JSON.stringify(confirm))})"` : ""}><input type="hidden" name="do" value="${doName}">${fields}<button class="btn small">${label}</button></form>`;

async function adminPage(env, req, url) {
  const s = url.searchParams.get("s") || "overview";
  const R = await rules(env);
  const msg = url.searchParams.get("m") ? `<div class="ok">${esc(url.searchParams.get("m"))}</div>` : "";
  let inner = "";
  if (s === "overview") {
    const since = url.searchParams.get("since") || isoAt(Date.now() - 30 * DAY).slice(0, 10);
    const c = async (sql, ...a) => (await one(env, sql, ...a)).n;
    const perBook = await all(env, `SELECT a.book_id, SUM(a.ok) AS ok, COUNT(*)-SUM(a.ok) AS bad FROM attempts a WHERE a.scope='answer' AND a.ts>=? GROUP BY a.book_id`, since);
    inner = `<h1>Overview</h1><form class="row" method="get"><input type="hidden" name="s" value="overview"><label>Since</label><input type="text" name="since" value="${esc(since)}" style="max-width:140px"><button class="btn small">Apply</button></form>
<div class="card">${tbl([{
      sub: await c("SELECT COUNT(*) AS n FROM attempts WHERE scope='answer' AND ts>=?", since),
      ok: await c("SELECT COUNT(*) AS n FROM attempts WHERE scope='answer' AND ok=1 AND ts>=?", since),
      ver: await c("SELECT COUNT(*) AS n FROM solves WHERE status='verified' AND verified_at>=?", since),
      pend: await c("SELECT COUNT(*) AS n FROM solves WHERE status='pending'"),
      acc: await c("SELECT COUNT(*) AS n FROM accounts"), nl: await c("SELECT COUNT(*) AS n FROM accounts WHERE newsletter=1"),
      cp: await c("SELECT COUNT(*) AS n FROM rewards WHERE kind='coupon' AND status='issued' AND issued_at>=?", since),
      gf: await c("SELECT COUNT(*) AS n FROM rewards WHERE kind<>'coupon' AND created>=?", since),
      ob: await c("SELECT COUNT(*) AS n FROM outbox WHERE done=0 AND attempts>0"), fl: await c("SELECT COUNT(*) AS n FROM flags WHERE status='open'"),
    }], [["sub", "Submissions"], ["ok", "Correct"], ["ver", "Verified solves"], ["pend", "Pending verification"], ["acc", "Accounts"], ["nl", "Newsletter opt-in"], ["cp", "Coupons issued"], ["gf", "Gift books"], ["ob", "Outbox retrying"], ["fl", "Open alerts"]])}</div>
<div class="card"><h3>Per book</h3>${tbl(perBook, [["book_id", "Book"], ["ok", "Correct"], ["bad", "Wrong"]])}</div>`;
  } else if (s === "books") {
    const books = await all(env, "SELECT book_id,prefix,title,line,series_id,series_order,next_book_id,skus,etsy_listing_ids,shopify_product_id,status,release_date,download_key FROM books ORDER BY series_id,series_order");
    inner = `<h1>Books</h1><div class="card"><h3>Import Puzzle Forge package (JSON)</h3><p class="muted">Answers arrive as hashes only; this page never shows them.</p>
<form method="post" action="/admin/act" enctype="multipart/form-data"><input type="hidden" name="do" value="import_books"><input type="file" name="file" accept=".json,application/json"><p>or paste:</p><textarea name="json"></textarea><p><button class="btn small">Import</button></p></form></div>
<div class="card">${tbl(books, [["book_id", "Book"], ["prefix", "Code prefix"], ["title", "Title"], ["line", "Line"], ["series_id", "Series", (b) => `${esc(b.series_id || "")} #${b.series_order || ""}`], ["next_book_id", "Next"],
      ["skus", "SKUs"], ["shopify_product_id", "Shopify product"], ["release_date", "Release"], ["status", "Status", (b) => actForm("book_status", `<input type="hidden" name="book" value="${esc(b.book_id)}"><select name="status">${["active", "upcoming", "hidden"].map((x) => `<option${x === b.status ? " selected" : ""}>${x}</option>`).join("")}</select>`, "Set")],
      ["x", "Edit", (b) => `<a href="/admin?s=book&id=${encodeURIComponent(b.book_id)}">edit</a>`]])}</div>`;
  } else if (s === "book") {
    const b = await getBook(env, url.searchParams.get("id"));
    if (!b) return redirect("/admin?s=books");
    const F = ["title", "line", "series_id", "series_order", "next_book_id", "skus", "etsy_listing_ids", "shopify_product_id", "etsy_url", "shop_url", "release_date", "difficulty", "pages", "solve_minutes", "audience", "blurb", "download_key", "download_url", "redeemable", "answer_label"];
    inner = `<h1>${esc(b.title)}</h1><div class="card"><form method="post" action="/admin/act"><input type="hidden" name="do" value="book_edit"><input type="hidden" name="book" value="${esc(b.book_id)}">
${F.map((k) => `<label>${k}</label><input type="text" name="${k}" value="${esc(b[k] ?? "")}">`).join("")}<p><button class="btn small">Save</button></p></form></div>`;
  } else if (s === "series") {
    const ss = await all(env, "SELECT * FROM series ORDER BY sort, series_id");
    inner = `<h1>Series</h1><div class="card">${tbl(ss, [["series_id", "ID"], ["title", "Title"], ["line", "Line"], ["total", "Books"], ["next_series_id", "Next series"], ["release_date", "Release"], ["sort", "Order"]])}</div>
<div class="card"><h3>Create / update</h3><form method="post" action="/admin/act"><input type="hidden" name="do" value="series_save">
${["series_id", "title", "line", "total", "next_series_id", "release_date", "sort"].map((k) => `<label>${k}</label><input type="text" name="${k}">`).join("")}<p><button class="btn small">Save</button></p></form></div>`;
  } else if (s === "codes") {
    const counts = await all(env, "SELECT book_id, status, COUNT(*) AS n FROM book_codes GROUP BY book_id, status ORDER BY book_id");
    const books = await all(env, "SELECT book_id,title FROM books ORDER BY book_id");
    inner = `<h1>Book Codes</h1>${msg}<div class="card"><h3>New batch (print run or download system)</h3><p class="muted">The CSV downloads once; only hashes are kept here.</p>
<form method="post" action="/admin/act"><input type="hidden" name="do" value="codes_new"><label>Book</label><select name="book">${books.map((b) => `<option value="${esc(b.book_id)}">${esc(b.title)}</option>`).join("")}</select>
<label>How many</label><input type="number" name="n" value="100" min="1" max="5000"><label>Batch / print-run name</label><input type="text" name="ref" required><label>Channel</label><select name="channel"><option>print</option><option>shop</option></select><p><button class="btn small">Generate CSV</button></p></form></div>
<div class="card"><h3>Look up or lock a code</h3>${actForm("code_lookup", `<input type="text" name="code" required placeholder="CASE01-XXXXXXXX" style="max-width:240px">`, "Look up")}
${actForm("code_lock", `<textarea name="codes" placeholder="one code per line" style="min-height:60px"></textarea>`, "Lock these codes", "Lock every code listed?")}</div>
<div class="card">${tbl(counts, [["book_id", "Book"], ["status", "Status"], ["n", "Codes"]])}</div>`;
  } else if (s === "etsy") {
    const n = await one(env, "SELECT COUNT(DISTINCT order_id) AS n, MAX(sale_date) AS last FROM etsy_orders");
    const pend = await all(env, "SELECT s.id, s.book_id, s.proof, s.claimed_at, a.email FROM solves s JOIN accounts a ON a.id=s.account_id WHERE s.status='pending' ORDER BY s.id");
    inner = `<h1>Etsy orders</h1>${msg}<div class="card"><p>${n.n} orders on file (latest sale ${esc(n.last || "-")}). Upload Etsy's <b>Sold Order Items</b> CSV (Shop Manager → Settings → Options → Download Data). Only order number, SKU, listing and date are kept.</p>
<form method="post" action="/admin/act" enctype="multipart/form-data"><input type="hidden" name="do" value="etsy_csv"><input type="file" name="file" accept=".csv" required><p><button class="btn small">Upload and re-check</button></p></form></div>
<div class="card"><h3>Waiting for verification (${pend.length})</h3>${tbl(pend, [["book_id", "Book"], ["proof", "Order", (r) => esc(r.proof.split("|")[0])], ["email", "E-mail"], ["claimed_at", "Since"],
      ["x", "", (r) => actForm("pending_decide", `<input type="hidden" name="id" value="${r.id}"><select name="v"><option value="approve">approve</option><option value="reject">reject</option></select>`, "Apply")]])}</div>`;
  } else if (s === "pool") {
    const st = await all(env, "SELECT pct, status, COUNT(*) AS n FROM etsy_coupon_pool GROUP BY pct, status");
    inner = `<h1>Etsy coupon pool</h1>${msg}<div class="card">${tbl(st, [["pct", "%"], ["status", "Status"], ["n", "Codes"]])}<p class="muted">Alert below ${R.pool_warn} free codes.</p></div>
<div class="card"><h3>Add codes created in Etsy Shop Manager</h3><form method="post" action="/admin/act"><input type="hidden" name="do" value="pool_add"><label>Percent</label><select name="pct">${[R.coupon_pct, 10, 20, 30, 40].filter((v, i, a) => a.indexOf(v) === i).map((p) => `<option>${p}</option>`).join("")}</select><label>Codes (one per line)</label><textarea name="codes"></textarea><p><button class="btn small">Add</button></p></form></div>`;
  } else if (s === "accounts") {
    const em = (url.searchParams.get("email") || "").trim().toLowerCase();
    let detail = "";
    if (em) {
      const a = await one(env, "SELECT * FROM accounts WHERE email=? OR email_norm=?", em, normEmail(em));
      if (!a) detail = `<div class="err">No account.</div>`;
      else {
        const solves = await all(env, "SELECT id,book_id,status,channel,proof_kind,created,verified_at FROM solves WHERE account_id=? ORDER BY id DESC", a.id);
        const rw = await all(env, "SELECT id,kind,book_id,channel,code,pct,status,expires FROM rewards WHERE account_id=? ORDER BY id DESC", a.id);
        const led = await all(env, "SELECT * FROM points_ledger WHERE account_id=? ORDER BY id DESC LIMIT 50", a.id);
        const cons = await all(env, "SELECT value,text,source,ts FROM consents WHERE account_id=? ORDER BY id DESC", a.id);
        detail = `<div class="card"><h3>${esc(a.email)} · ${esc(a.tier)} · ${a.points_total} total / ${a.points_avail} available${a.locked ? " · LOCKED" : ""}</h3>
<p>Newsletter: ${a.newsletter ? "yes" : "no"} · Referral code ${esc(a.ref_code)} · Birth month ${a.birth_month || "-"}</p>
${actForm("points_adjust", `<input type="hidden" name="id" value="${a.id}"><input type="number" name="delta" placeholder="+/- points" style="max-width:120px"><input type="text" name="reason" placeholder="reason" required style="max-width:240px"><label style="font-weight:400"><input type="checkbox" name="total" value="1"> also total</label>`, "Adjust")}
${actForm("account_lock", `<input type="hidden" name="id" value="${a.id}"><input type="hidden" name="v" value="${a.locked ? 0 : 1}">`, a.locked ? "Unlock" : "Lock account")}
${actForm("account_delete", `<input type="hidden" name="id" value="${a.id}">`, "Delete data", `Delete ${a.email} and all points/coupons? This cannot be undone.`)}</div>
<div class="card"><h3>Solves</h3>${tbl(solves, [["book_id", "Book"], ["status", "Status"], ["channel", "Channel"], ["proof_kind", "Proof"], ["created", "Solved"], ["verified_at", "Verified"]])}</div>
<div class="card"><h3>Rewards</h3>${tbl(rw, [["kind", "Kind"], ["book_id", "Book"], ["channel", "Channel"], ["code", "Code", (r) => esc(r.kind === "coupon" ? r.code || "" : "(download)")], ["status", "Status"], ["expires", "Expires"],
          ["x", "", (r) => actForm("reward_resend", `<input type="hidden" name="id" value="${r.id}">`, r.status === "issued" ? "Re-send" : "Issue now")]])}</div>
<div class="card"><h3>Points ledger</h3>${tbl(led, [["ts", "When"], ["reason", "Reason"], ["ref", "Ref"], ["d_total", "Total"], ["d_avail", "Available"]])}</div>
<div class="card"><h3>Consent log</h3>${tbl(cons, [["ts", "When"], ["value", "Opt-in"], ["source", "Source"], ["text", "Text"]])}</div>`;
      }
    }
    const recent = await all(env, "SELECT email,tier,points_total,newsletter,created FROM accounts ORDER BY id DESC LIMIT 30");
    inner = `<h1>Accounts</h1>${msg}<form class="row" method="get"><input type="hidden" name="s" value="accounts"><input type="email" name="email" value="${esc(em)}" placeholder="customer e-mail" style="max-width:320px"><button class="btn small">Find</button>
<a class="btn small ghost" href="/admin/export/consenting.csv">Export opted-in e-mails (CSV)</a></form>${detail}
<div class="card"><h3>Newest</h3>${tbl(recent, [["email", "E-mail", (r) => `<a href="/admin?s=accounts&email=${encodeURIComponent(r.email)}">${esc(r.email)}</a>`], ["tier", "Tier"], ["points_total", "Points"], ["newsletter", "Opt-in"], ["created", "Since"]])}</div>`;
  } else if (s === "flags") {
    const fl = await all(env, "SELECT * FROM flags WHERE status='open' ORDER BY id DESC LIMIT 200");
    const refs = await all(env, "SELECT r.id, a.email AS referrer, b.email AS referee, r.reason FROM referrals r JOIN accounts a ON a.id=r.referrer_id JOIN accounts b ON b.id=r.referee_id WHERE r.status='review'");
    inner = `<h1>Alerts</h1>${msg}<div class="card">${tbl(fl, [["ts", "When"], ["kind", "Kind"], ["detail", "Detail"], ["x", "", (r) => actForm("flag_close", `<input type="hidden" name="id" value="${r.id}">`, "Dismiss")]])}</div>
<div class="card"><h3>Referrals to review</h3>${tbl(refs, [["referrer", "Referrer"], ["referee", "Friend"], ["reason", "Why"], ["x", "", (r) => actForm("referral_decide", `<input type="hidden" name="id" value="${r.id}"><select name="v"><option value="waiting">allow</option><option value="rejected">reject</option></select>`, "Apply")]])}</div>`;
  } else if (s === "gifts") {
    const g = await all(env, "SELECT r.id, a.email, r.kind, r.book_id, r.status, r.note, r.created FROM rewards r JOIN accounts a ON a.id=r.account_id WHERE r.kind<>'coupon' OR r.status IN ('waiting_release','retry') ORDER BY r.id DESC LIMIT 300");
    const insp = await all(env, "SELECT email, display_name, tier, name_consent FROM accounts WHERE tier IN ('Inspector','Chief Inspector') ORDER BY points_total DESC");
    inner = `<h1>Gifts</h1>${msg}<div class="card"><h3>Gift books, redemptions, rewards waiting for release</h3>${tbl(g, [["created", "When"], ["email", "E-mail"], ["kind", "Kind"], ["book_id", "Book"], ["status", "Status"], ["note", "Note"],
      ["x", "", (r) => r.status === "issued" ? "" : actForm("reward_resend", `<input type="hidden" name="id" value="${r.id}">`, "Issue now")]])}</div>
<div class="card"><h3>Inspector+ (quarterly short case) · Chief Inspectors (character-name consent)</h3>${tbl(insp, [["email", "E-mail"], ["display_name", "Name"], ["tier", "Tier"], ["name_consent", "Name OK"]])}</div>`;
  } else if (s === "rules") {
    inner = `<h1>Point rules</h1>${msg}<div class="card"><p class="muted">Changes apply from the moment you save (no back-dating).</p><form method="post" action="/admin/act"><input type="hidden" name="do" value="rules_save"><textarea name="rules" style="min-height:360px">${esc(JSON.stringify(R, null, 1))}</textarea><p><button class="btn small">Save</button></p></form></div>`;
  } else if (s === "settings") {
    const rowsS = [];
    for (const k of SECRET_SETTINGS) rowsS.push(`<label>${k} ${(await getSetting(env, k, "")) ? "<span class='label' style='--c:#3a7'>set</span>" : "<span class='label' style='--c:#a33'>empty</span>"}</label><input type="text" name="${k}" placeholder="leave empty to keep" autocomplete="off" style="-webkit-text-security:disc">`);
    for (const k of ["shopify_shop", "shopify_api_version", "klaviyo_list_id", "turnstile_site", "telegram_chat", "mail_provider", "mail_from", "mail_from_name", "google_client_id"])
      rowsS.push(`<label>${k}</label><input type="text" name="${k}" value="${esc(await getSetting(env, k, ""))}">`);
    inner = `<h1>Settings</h1>${msg}<div class="card"><p class="muted">Keys are stored encrypted and never shown again. mail_provider: zeptomail or resend. Shopify token needs read_orders + write_discounts only. Google sign-in: create an OAuth client (Web) in Google Cloud with redirect URI <code>${esc((env.SITE_URL || "") + "/auth/google/callback")}</code>.</p>
<form method="post" action="/admin/act"><input type="hidden" name="do" value="settings_save">${rowsS.join("")}
<label>Reward rules page (HTML, optional)</label><textarea name="terms_html">${esc(await getSetting(env, "terms_html", ""))}</textarea>
<label>Privacy page (HTML, optional)</label><textarea name="privacy_html">${esc(await getSetting(env, "privacy_html", ""))}</textarea><p><button class="btn small">Save</button></p></form>
${actForm("test_services", "", "Send test (mail to me, Telegram, Klaviyo)")}</div>`;
  } else if (s === "security") {
    const totp = await getSetting(env, "admin_totp", "");
    let pending = await getSetting(env, "admin_totp_pending", "");
    if (!totp && !pending) { pending = newTotpSecret(); await setSetting(env, "admin_totp_pending", pending); }
    inner = `<h1>Security</h1>${msg}<div class="card"><h3>Owner password</h3>${actForm("pw_change", `<input type="password" name="old" placeholder="current password" required style="max-width:220px"><input type="password" name="pw" placeholder="new password (12+)" minlength="12" required style="max-width:220px">`, "Change password")}
<p class="muted">Sign-in is locked for an hour after 8 failed tries from one network.</p></div>
<div class="card"><h3>Two-step sign-in (optional)</h3>${totp ? `<p>On. Sign-in asks for the 6-digit code from your authenticator app.</p>${actForm("totp_off", `<input type="text" name="code" placeholder="current 6-digit code" maxlength="6" required style="max-width:200px">`, "Turn off")}`
      : `<p>Off. Optional extra lock: an authenticator app (Google Authenticator, Authy, 1Password) shows a new 6-digit code every 30 seconds. No SMS needed. Add this key in the app:</p><p><code class="mono" style="font-size:18px">${pending.match(/.{1,4}/g).join(" ")}</code></p>${actForm("totp_on", `<input type="text" name="code" placeholder="6-digit code from the app" maxlength="6" required style="max-width:220px">`, "Turn on")}`}</div>`;
  } else if (s === "outbox") {
    const ob = await all(env, "SELECT id,kind,attempts,next_at,last_error,done FROM outbox WHERE done<>1 ORDER BY id DESC LIMIT 200");
    inner = `<h1>Outbox</h1>${msg}<div class="card">${actForm("outbox_run", "", "Run now")}${tbl(ob, [["id", "#"], ["kind", "Kind"], ["attempts", "Tries"], ["next_at", "Next"], ["last_error", "Error"], ["done", "State", (r) => r.done === 2 ? "gave up" : "retrying"]])}</div>
<div class="card"><h3>Audit log</h3>${tbl(await all(env, "SELECT ts,actor,action,detail FROM audit_log ORDER BY id DESC LIMIT 60"), [["ts", "When"], ["actor", "Who"], ["action", "Action"], ["detail", "Detail"]])}</div>`;
  }
  return adminLayout(s, (s === "overview" || s === "books" || s === "series" || s === "book" ? msg : "") + inner, s === "book" ? "books" : s);
}

// ---- book package import (Puzzle Forge → CaseVault), also used by the internal API -----------------
async function importBooks(env, data, actor) {
  const list = Array.isArray(data) ? data : data.books || [data];
  const done = [];
  for (const p of list) {
    if (!p || !p.book_id || !p.title) throw new Error("each package needs book_id and title");
    let answers = p.answers || {};
    if (p.answer_hash) answers = { [p.answer_kind || "culprit_name"]: [p.answer_hash, ...(p.accepted_variants || [])] };
    for (const [k, v] of Object.entries(answers)) {
      if (!ANSWER_KINDS.includes(k) || !Array.isArray(v) || !v.every((h) => /^[0-9a-f]{64}$/.test(h))) throw new Error(`answers.${k}: hashes only (64 hex)`);
    }
    const old = await getBook(env, p.book_id);
    const skus = Array.isArray(p.skus) ? p.skus : Object.values(p.skus || {}).flat();
    if (p.sku && !skus.includes(p.sku)) skus.push(p.sku);
    const shopify = p.shopify_product_id || (p.shopify_product_ids || [])[0] || (old && old.shopify_product_id) || null;
    const prefix = String(p.book_code_prefix || (old && old.prefix) || p.book_id.replace(/[^A-Z0-9]/gi, "").slice(-8)).toUpperCase();
    const row = {
      book_id: p.book_id, prefix, title: p.title, line: p.line || (old && old.line) || "mystery", series_id: p.series_id || null,
      series_order: p.series_order || null, next_book_id: p.next_book_id || null, skus: JSON.stringify(skus.map(String)),
      etsy_listing_ids: JSON.stringify((p.etsy_listing_ids || []).map(String)), shopify_product_id: shopify,
      etsy_url: p.etsy_url || (old && old.etsy_url) || null, shop_url: p.shop_url || (old && old.shop_url) || null,
      answers: JSON.stringify(answers), answer_label: p.answer_label || "Final code", ending_text: p.ending_text || null,
      extended_ending: p.extended_ending || null, blurb: p.blurb || null, status: p.status || (old && old.status) || "active",
      language: p.language || "en", edition: String(p.edition || "1"), release_date: p.release_date || null,
      difficulty: p.difficulty || null, pages: p.pages || null, solve_minutes: p.solve_minutes || null, audience: p.audience || null,
      download_key: p.download_key || (old && old.download_key) || null, download_url: p.download_url || (old && old.download_url) || null,
      cover_key: old && old.cover_key, updated: nowIso(), created: (old && old.created) || nowIso(),
    };
    if (p.cover_png_b64 && env.FILES) {
      const key = `casevault/covers/${p.book_id}.png`;
      await env.FILES.put(key, Uint8Array.from(atob(p.cover_png_b64), (c) => c.charCodeAt(0)), { httpMetadata: { contentType: "image/png" } });
      row.cover_key = key;
    }
    const cols = Object.keys(row);
    await run(env, `INSERT INTO books(${cols.join(",")}) VALUES(${cols.map(() => "?").join(",")})
      ON CONFLICT(book_id) DO UPDATE SET ${cols.filter((c) => c !== "book_id" && c !== "created").map((c) => `${c}=excluded.${c}`).join(",")}`, ...cols.map((c) => row[c]));
    if (p.series_id) {
      await run(env, `INSERT INTO series(series_id,title,line,total,release_date) VALUES(?,?,?,?,?)
        ON CONFLICT(series_id) DO UPDATE SET title=COALESCE(excluded.title,series.title), total=COALESCE(excluded.total,series.total), line=excluded.line`,
      p.series_id, p.series_title || p.series_id, row.line, p.series_total || 10, p.series_release_date || null);
      if (p.next_series_id) await run(env, "UPDATE series SET next_series_id=? WHERE series_id=?", p.next_series_id, p.series_id);
    }
    for (const batch of p.book_code_batches || []) {
      for (const h of batch.code_hashes || []) await run(env, "INSERT OR IGNORE INTO book_codes(code_hash,book_id,status,ref,channel,created) VALUES(?,?,?,?,?,?)", h, p.book_id, "assigned", batch.batch_id, batch.channel, nowIso());
    }
    done.push(p.book_id);
  }
  await audit(env, actor, "import_books", done);
  if (done.length) await releaseDue(env);
  return done;
}

async function adminAct(env, req) {
  const f = await readBody(req);
  const back = (s, m) => redirect(`/admin?s=${s}${m ? `&m=${encodeURIComponent(m)}` : ""}`);
  const d = f.do;
  try {
    if (d === "import_books") {
      const text = f.file && typeof f.file === "object" && f.file.size ? await f.file.text() : f.json;
      const ids = await importBooks(env, JSON.parse(text || "{}"), "owner");
      return back("books", `Imported ${ids.join(", ")}`);
    }
    if (d === "book_status") { await run(env, "UPDATE books SET status=?, updated=? WHERE book_id=?", f.status, nowIso(), f.book); await audit(env, "owner", "book_status", f); if (f.status === "active") await releaseDue(env); return back("books", "Saved"); }
    if (d === "book_edit") {
      const F = ["title", "line", "series_id", "series_order", "next_book_id", "skus", "etsy_listing_ids", "shopify_product_id", "etsy_url", "shop_url", "release_date", "difficulty", "pages", "solve_minutes", "audience", "blurb", "download_key", "download_url", "redeemable", "answer_label"];
      for (const k of ["skus", "etsy_listing_ids"]) { const v = jparse(f[k], null); f[k] = JSON.stringify(Array.isArray(v) ? v.map(String) : String(f[k] || "").split(/[,\s]+/).filter(Boolean)); }
      await run(env, `UPDATE books SET ${F.map((k) => `${k}=?`).join(",")}, updated=? WHERE book_id=?`, ...F.map((k) => (f[k] === "" ? null : f[k])), nowIso(), f.book);
      await audit(env, "owner", "book_edit", f.book);
      return back("books", "Saved");
    }
    if (d === "series_save") {
      await run(env, `INSERT INTO series(series_id,title,line,total,next_series_id,release_date,sort) VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(series_id) DO UPDATE SET title=excluded.title,line=excluded.line,total=excluded.total,next_series_id=excluded.next_series_id,release_date=excluded.release_date,sort=excluded.sort`,
      f.series_id, f.title || f.series_id, f.line || "mystery", parseInt(f.total, 10) || 10, f.next_series_id || null, f.release_date || null, parseInt(f.sort, 10) || 0);
      return back("series", "Saved");
    }
    if (d === "codes_new") {
      const book = await getBook(env, f.book);
      const n = Math.min(5000, Math.max(1, parseInt(f.n, 10) || 0));
      const lines = ["book_id,code,batch"];
      for (let i = 0; i < n; i++) {
        const code = newBookCode(book.prefix);
        await run(env, "INSERT INTO book_codes(code_hash,book_id,tail,status,ref,channel,created) VALUES(?,?,?,?,?,?,?)", await bookCodeHash(env.VAULT_ANSWER_KEY || "", book.book_id, code), book.book_id, code.slice(-3), "assigned", f.ref, f.channel, nowIso());
        lines.push([book.book_id, code, f.ref].map(csvCell).join(","));
      }
      await audit(env, "owner", "codes_new", { book: book.book_id, n, ref: f.ref });
      return new Response(lines.join("\n") + "\n", { headers: { "content-type": "text/csv", "content-disposition": `attachment; filename="bookcodes-${book.book_id}-${f.ref}.csv"`, "cache-control": "no-store" } });
    }
    if (d === "code_lookup") {
      const c = await one(env, "SELECT * FROM book_codes WHERE code_hash=?", await codeHashAnyBook(env, f.code));
      return back("codes", c ? `${c.book_id} · ${c.status} · batch ${c.ref || "-"}${c.used_at ? ` · used ${c.used_at}` : ""}` : "Code not found");
    }
    if (d === "code_lock") {
      const codes = String(f.codes || "").split(/\s+/).filter(Boolean);
      for (const c of codes) await run(env, "UPDATE book_codes SET status='locked' WHERE code_hash=?", await codeHashAnyBook(env, c));
      await audit(env, "owner", "code_lock", { n: codes.length });
      return back("codes", `Locked ${codes.length}`);
    }
    if (d === "etsy_csv") {
      const rows = parseCsv(await f.file.text());
      let n = 0;
      const pick = (r, names) => { for (const k of names) if (r[k] !== undefined && r[k] !== "") return r[k]; return ""; };
      const stmts = [];
      for (const r of rows) {
        const order = pick(r, ["Order ID", "Order Id", "Receipt ID", "order_id"]).replace(/\D/g, "");
        if (!order) continue;
        stmts.push(env.DB.prepare("INSERT OR IGNORE INTO etsy_orders(order_id,sku,listing_id,sale_date) VALUES(?,?,?,?)").bind(order,
          pick(r, ["SKU", "sku"]), pick(r, ["Listing ID", "Listing Id", "listing_id"]).replace(/\D/g, ""), pick(r, ["Sale Date", "Order Date", "Date Paid"])));
        n++;
      }
      for (let i = 0; i < stmts.length; i += 100) await env.DB.batch(stmts.slice(i, i + 100));
      const rel = await recheckPending(env);
      await audit(env, "owner", "etsy_csv", { rows: n, released: rel });
      return back("etsy", `${n} lines read, ${rel} pending rewards released`);
    }
    if (d === "pending_decide") {
      const s = await one(env, "SELECT * FROM solves WHERE id=? AND status='pending'", f.id);
      if (s && f.v === "approve") await grantSolve(env, s.id);
      if (s && f.v === "reject") await run(env, "UPDATE solves SET status='rejected' WHERE id=?", s.id);
      await audit(env, "owner", "pending_decide", f);
      return back("etsy", "Done");
    }
    if (d === "pool_add") {
      const codes = String(f.codes || "").split(/\s+/).map((c) => c.trim()).filter(Boolean);
      for (const c of codes) await run(env, "INSERT OR IGNORE INTO etsy_coupon_pool(code,pct) VALUES(?,?)", c, parseInt(f.pct, 10) || 15);
      await releaseDue(env);
      for (const r of await all(env, "SELECT id FROM rewards WHERE status='retry' AND channel='etsy'")) await issuePendingReward(env, r.id).catch(() => null);
      return back("pool", `Added ${codes.length}`);
    }
    if (d === "points_adjust") {
      const delta = parseInt(f.delta, 10) || 0;
      await addPoints(env, parseInt(f.id, 10), f.total ? delta : 0, delta, `admin: ${String(f.reason).slice(0, 80)}`, nowIso());
      await audit(env, "owner", "points_adjust", f);
      return back("accounts", "Adjusted");
    }
    if (d === "account_lock") { await run(env, "UPDATE accounts SET locked=? WHERE id=?", f.v === "1" ? 1 : 0, f.id); await audit(env, "owner", "account_lock", f); return back("accounts", "Saved"); }
    if (d === "account_delete") { await deleteAccount(env, parseInt(f.id, 10), "owner"); return back("accounts", "Deleted"); }
    if (d === "reward_resend") {
      const rw = await one(env, "SELECT * FROM rewards WHERE id=?", f.id);
      if (rw && rw.status !== "issued") { await run(env, "UPDATE rewards SET status='retry' WHERE id=?", rw.id); await issuePendingReward(env, rw.id); }
      else if (rw) await kEvent(env, { id: rw.account_id }, rw.kind === "coupon" ? "Reward Released" : "Gift Book Ready", { book_id: rw.book_id, reward_code: rw.kind === "coupon" ? rw.code : null, download_url: rw.kind !== "coupon" ? `${env.SITE_URL || ""}/dl/${rw.code}` : null, resend: true });
      await audit(env, "owner", "reward_resend", f.id);
      return back("gifts", "Done");
    }
    if (d === "flag_close") { await run(env, "UPDATE flags SET status='closed' WHERE id=?", f.id); return back("flags", "Dismissed"); }
    if (d === "referral_decide") { await run(env, "UPDATE referrals SET status=? WHERE id=? AND status='review'", f.v === "waiting" ? "waiting" : "rejected", f.id); return back("flags", "Saved"); }
    if (d === "rules_save") { const r = JSON.parse(f.rules); await setSetting(env, "rules", JSON.stringify(r)); await audit(env, "owner", "rules_save", r); return back("rules", "Saved"); }
    if (d === "settings_save") {
      for (const k of SECRET_SETTINGS) if (f[k]) await setSetting(env, k, String(f[k]).trim());
      for (const k of ["shopify_shop", "shopify_api_version", "klaviyo_list_id", "turnstile_site", "telegram_chat", "mail_provider", "mail_from", "mail_from_name", "google_client_id", "terms_html", "privacy_html"])
        if (f[k] !== undefined) await setSetting(env, k, String(f[k]).trim());
      await audit(env, "owner", "settings_save", Object.keys(f).filter((k) => f[k] && k !== "do"));
      return back("settings", "Saved");
    }
    if (d === "test_services") {
      const out = [];
      const R = await rules(env);
      try { await sendMail(env, R.support_email, "Case Vault test", mailFrame("<p>Mail works.</p>")); out.push("mail ok"); } catch (e) { out.push(`mail: ${e.message}`); }
      try { const r = await telegram(env, "test message"); out.push(r.skipped ? "telegram not set" : "telegram ok"); } catch (e) { out.push(`telegram: ${e.message}`); }
      try { const r = await klaviyo(env, "events", klaviyoEventBody(R.support_email, "CaseVault Test", {}, {})); out.push(r.skipped ? "klaviyo not set" : "klaviyo ok"); } catch (e) { out.push(`klaviyo: ${e.message}`); }
      return back("settings", out.join(" · "));
    }
    if (d === "pw_change") {
      if (!(await pwCheck(String(f.old || ""), await getSetting(env, "admin_pw", "")))) return back("security", "Current password is wrong");
      if (String(f.pw || "").length < 12) return back("security", "At least 12 characters");
      await setSetting(env, "admin_pw", await pwHash(f.pw)); await audit(env, "owner", "pw_change", {});
      return back("security", "Password changed");
    }
    if (d === "totp_on") {
      const pending = await getSetting(env, "admin_totp_pending", "");
      if (!pending || !(await totpOk(pending, f.code))) return back("security", "That code did not match");
      await setSetting(env, "admin_totp", pending); await setSetting(env, "admin_totp_pending", null); await audit(env, "owner", "totp_on", {});
      return back("security", "Two-step sign-in is on");
    }
    if (d === "totp_off") {
      if (!(await totpOk(await getSetting(env, "admin_totp", ""), f.code))) return back("security", "That code did not match");
      await setSetting(env, "admin_totp", null); await audit(env, "owner", "totp_off", {});
      return back("security", "Two-step sign-in is off");
    }
    if (d === "outbox_run") { const n = await processOutbox(env, 100); return back("outbox", `${n} sent`); }
  } catch (e) {
    return back("overview", `Error: ${String(e.message || e).slice(0, 200)}`);
  }
  return back("overview", "Unknown action");
}

// Admin lookup by plain code: the prefix names the book (legacy 12-char codes: try every book).
async function codeHashAnyBook(env, code) {
  const c = canonicalCode(code);
  const pre = c.includes("-") ? c.split("-")[0] : "";
  const books = pre ? await all(env, "SELECT book_id FROM books WHERE prefix=?", pre) : await all(env, "SELECT book_id FROM books");
  for (const b of books) {
    const h = await bookCodeHash(env.VAULT_ANSWER_KEY || "", b.book_id, c);
    if (await one(env, "SELECT 1 AS x FROM book_codes WHERE code_hash=?", h)) return h;
  }
  return "-";
}

async function exportConsenting(env) {
  const rows = await all(env, "SELECT email, display_name, created FROM accounts WHERE newsletter=1 ORDER BY id");
  await audit(env, "owner", "export_consenting", { n: rows.length });
  return new Response(["email,name,since", ...rows.map((r) => [r.email, r.display_name, r.created].map(csvCell).join(","))].join("\n"),
    { headers: { "content-type": "text/csv", "content-disposition": 'attachment; filename="casevault-optin.csv"', "cache-control": "no-store" } });
}

// ---- internal API (Bearer VAULT_ADMIN_TOKEN): Puzzle Forge registration, download-page Book Codes ----
function bearerOk(env, req) {
  const h = req.headers.get("authorization") || "";
  return !!env.VAULT_ADMIN_TOKEN && timingSafeEq(h.replace(/^Bearer\s+/i, ""), env.VAULT_ADMIN_TOKEN);
}
async function internalApi(env, req, path) {
  if (!bearerOk(env, req)) return json({ error: "unauthorized" }, 401);
  if (path === "/api/admin/books" && req.method === "POST") {
    try { return json({ ok: true, books: await importBooks(env, await req.json(), "forge") }); }
    catch (e) { return json({ ok: false, error: String(e.message || e) }, 400); }
  }
  if (path === "/api/internal/bookcode" && req.method === "POST") {
    // The download system asks for one fresh Book Code per Shopify order and prints it on the last page.
    const f = await req.json().catch(() => ({}));
    const book = await getBook(env, f.book_id);
    if (!book) return json({ error: "unknown book" }, 404);
    const ref = `shop:${String(f.order || "").slice(0, 40)}`;
    const code = newBookCode(book.prefix);
    await run(env, "INSERT INTO book_codes(code_hash,book_id,tail,status,ref,channel,created) VALUES(?,?,?,?,?,?,?)", await bookCodeHash(env.VAULT_ANSWER_KEY || "", book.book_id, code), book.book_id, code.slice(-3), "assigned", ref, "shop", nowIso());
    return json({ ok: true, code, url: `${env.SITE_URL || ""}/?book=${encodeURIComponent(book.book_id)}` });
  }
  if (path === "/api/internal/health") return json({ ok: true, version: VERSION, env: env.ENV_NAME || "dev" });
  return json({ error: "not found" }, 404);
}
