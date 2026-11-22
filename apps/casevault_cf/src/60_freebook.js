// ---- Free Book: one free book per e-mail (spec "Luồng Free Book trên Shopify" §4) --------------------------------
// The theme page /pages/free-book posts {email, handle, source, consent} to POST /free-book/claim.
// The book list is read from Shopify (product type "Free Book", ACTIVE, metafield free_book.file_key) and cached in D1
// for 10 minutes, so a new Free Book works as soon as the owner publishes it. Files live in R2 (BOOKS binding) under free/.
const FB_LINK_DAYS = 7;
const FB_IP_PER_HOUR = 5;
const FB_ORIGINS = [/^https:\/\/(www\.)?colorilax\.com$/, /^https:\/\/[a-z0-9-]+\.myshopify\.com$/, /^https:\/\/[a-z0-9-]+\.shopifypreview\.com$/];
const FB_DISPOSABLE = ["mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com", "temp-mail.org", "yopmail.com",
  "trashmail.com", "sharklasers.com", "getnada.com", "dispostable.com", "maildrop.cc", "throwawaymail.com", "fakeinbox.com", "mintemail.com"];
const FB_SOURCES = ["freebook_web", "etsy_insert", "popup", "email"];

function fbCors(req) {
  const o = req.headers.get("origin") || "";
  if (!FB_ORIGINS.some((r) => r.test(o))) return {};
  return { "access-control-allow-origin": o, "access-control-allow-methods": "POST, OPTIONS", "access-control-allow-headers": "content-type",
    "access-control-max-age": "86400", vary: "origin" };
}

// Free Books on Shopify → D1 cache (handle, title, file_key, catalog_no, interest).
async function fbCatalog(env, force = false) {
  const t = await getSetting(env, "freebook_synced", "");
  if (!force && t && Date.now() - Date.parse(t) < 10 * 60000) return all(env, "SELECT * FROM free_books WHERE active=1");
  const shop = await getSetting(env, "shopify_shop", "");
  const token = await getSetting(env, "shopify_token", "");
  if (!shop || !token) return all(env, "SELECT * FROM free_books WHERE active=1");
  const ver = (await getSetting(env, "shopify_api_version", "")) || "2024-10";
  const query = `{ products(first: 100, query: "product_type:'Free Book' AND status:active") { nodes { handle title tags status
    fk: metafield(namespace: "free_book", key: "file_key") { value } cn: metafield(namespace: "free_book", key: "catalog_no") { value } } } }`;
  const r = await net(env)(`https://${shop.replace(/^https?:\/\//, "").replace(/\/$/, "")}/admin/api/${ver}/graphql.json`, {
    method: "POST", headers: { "content-type": "application/json", "x-shopify-access-token": token }, body: JSON.stringify({ query }) });
  if (!r.ok) return all(env, "SELECT * FROM free_books WHERE active=1");
  const nodes = (await r.json())?.data?.products?.nodes || [];
  await run(env, "UPDATE free_books SET active=0");
  for (const n of nodes) {
    const key = n.fk && n.fk.value;
    if (!key || !String(key).startsWith("free/")) continue;
    const interest = ((n.tags || []).find((x) => String(x).startsWith("interest:")) || "").slice(9);
    await run(env, `INSERT INTO free_books(handle,title,file_key,catalog_no,interest,active,updated) VALUES(?,?,?,?,?,1,?)
      ON CONFLICT(handle) DO UPDATE SET title=excluded.title, file_key=excluded.file_key, catalog_no=excluded.catalog_no,
      interest=excluded.interest, active=1, updated=excluded.updated`,
      n.handle, String(n.title || "").replace(/^Free:\s*/, ""), key, (n.cn && n.cn.value) || "", interest, nowIso());
  }
  await setSetting(env, "freebook_synced", nowIso());
  return all(env, "SELECT * FROM free_books WHERE active=1");
}

function fbMail(ctx, title, link, again) {
  return mailFrame(`<h2>${again ? "Here is your free book again" : "Your free book is ready"}</h2>
    <p>${again ? "You already claimed" : "Thank you for joining Colorilax. Here is"} <b>${esc(title)}</b>.</p>
    <p><a href="${esc(link)}" style="display:inline-block;background:#44524A;color:#fff;padding:12px 22px;border-radius:8px;text-decoration:none">Download your free book (PDF)</a></p>
    <p style="color:#666">The link works for ${FB_LINK_DAYS} days. Print on US Letter paper, one side per sheet. For personal use only.</p>`);
}

async function freebookClaim(env, req) {
  const cors = fbCors(req);
  const f = await readBody(req);
  const email = String(f.email || "").trim();
  const handle = String(f.handle || f.product_handle || f.book || "").trim().toLowerCase().replace(/^#/, "");
  const source = FB_SOURCES.includes(f.source) ? f.source : "freebook_web";
  const consent = ["1", "true", "on", "yes", true, 1].includes(f.consent ?? f.accepts_marketing ?? f.newsletter);
  const ip = truncIp(clientIp(req));
  const bad = (status, error, extra = {}) => json({ ok: false, error, ...extra }, status, cors);
  if (!emailOk(email)) return bad(400, "Please enter a valid e-mail address.");
  const dom = email.toLowerCase().split("@")[1];
  if (FB_DISPOSABLE.includes(dom)) return bad(400, "Please use your regular e-mail address.");
  if (await countAttempts(env, "scope='freebook' AND ip=?", [ip], 60) >= FB_IP_PER_HOUR) return bad(429, "Too many requests. Please try again in an hour.");
  await logAttempt(env, { scope: "freebook", ip, ok: true });
  const norm = normEmail(email);
  const origin = env.SITE_URL || new URL(req.url).origin;
  const prev = await one(env, "SELECT * FROM free_claims WHERE email_norm=?", norm);
  if (prev) {                                     // one Free Book per e-mail: never a second book, but the old link again
    const token = randomToken(24);
    await run(env, "UPDATE free_claims SET token=?, expires=? WHERE id=?", token, plusDays(FB_LINK_DAYS), prev.id);
    const link = `${origin}/free-book/dl/${token}`;
    await enqueue(env, "mail", { to: email, subject: `Your free book: ${prev.title}`, html: fbMail({}, prev.title, link, true) });
    return json({ ok: false, already: true, title: prev.title, handle: prev.handle, download_url: link,
      error: `You've already claimed your free book (${prev.title}). We sent the link to your inbox again.` }, 200, cors);
  }
  if (!handle) return bad(400, "Please choose a book.");
  const books = await fbCatalog(env);
  const book = books.find((b) => b.handle === handle || b.handle === `free-${handle}` || b.catalog_no.toLowerCase() === handle);
  if (!book) return bad(404, "This book is not available right now.");
  const token = randomToken(24);
  await run(env, `INSERT INTO free_claims(email,email_norm,handle,catalog_no,title,file_key,source,consent,ip_trunc,token,expires,created,downloads)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0)`, email, norm, book.handle, book.catalog_no, book.title, book.file_key, source, consent ? 1 : 0, ip, token,
    plusDays(FB_LINK_DAYS), nowIso());
  const link = `${origin}/free-book/dl/${token}`;
  await enqueue(env, "mail", { to: email, subject: `Your free book is ready: ${book.title}`, html: fbMail({}, book.title, link, false) });
  const profile = { freebook_choice: book.title, freebook_catalog_no: book.catalog_no, interest: book.interest || null, source };
  await enqueue(env, "klaviyo_event", { email, metric: "Claimed Free Book", props: { ...profile, handle: book.handle, unique_id: `freebook-${norm}` }, profile });
  await run(env, "INSERT INTO consents(email,value,text,source,ip_trunc,ts) VALUES(?,?,?,?,?,?)", email, consent ? 1 : 0, FB_CONSENT_TEXT, `freebook:${source}`, ip, nowIso());
  if (consent) await enqueue(env, "klaviyo_sub", { email, subscribe: true });
  return json({ ok: true, title: book.title, handle: book.handle, download_url: link, expires_days: FB_LINK_DAYS }, 200, cors);
}
const FB_CONSENT_TEXT = "Yes, send me new free pages, releases and occasional offers from Colorilax. Unsubscribe anytime.";

async function freebookDownload(env, ctx, token) {
  const c = await one(env, "SELECT * FROM free_claims WHERE token=?", token);
  if (!c) return notFound(ctx);
  if (c.expires < nowIso()) return infoPage(ctx, "Link expired", `<h2>This download link has expired</h2>
    <p>Links work for ${FB_LINK_DAYS} days. Enter the same e-mail on <a href="https://colorilax.com/pages/free-book">colorilax.com/pages/free-book</a> and we will send you a new link to the same book.</p>`);
  const obj = env.BOOKS ? await env.BOOKS.get(c.file_key) : null;
  if (!obj) return infoPage(ctx, "Download", `<h2>Your book is being prepared</h2><p>Please try again in a few minutes.</p>`);
  await run(env, "UPDATE free_claims SET downloads=downloads+1, last_download=? WHERE id=?", nowIso(), c.id);
  return new Response(obj.body, { headers: { "content-type": "application/pdf",
    "content-disposition": `attachment; filename="${c.file_key.split("/").pop()}"`, "cache-control": "private, no-store" } });
}

async function freebookList(env, req) {
  const books = await fbCatalog(env);
  return json({ ok: true, books: books.map((b) => ({ handle: b.handle, title: b.title, catalog_no: b.catalog_no, interest: b.interest })) }, 200, fbCors(req));
}
