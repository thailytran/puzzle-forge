// ---- outside services: mail, Klaviyo, Shopify, Telegram, Turnstile (all via outbox + retry) ----
// `env.FETCH` lets tests replace the network; production uses the global fetch.
const net = (env) => env.FETCH || fetch;

async function enqueue(env, kind, payload) {
  await run(env, "INSERT INTO outbox(kind,payload,next_at) VALUES(?,?,?)", kind, JSON.stringify(payload), nowIso());
}

async function sendMail(env, to, subject, htmlBody) {
  const provider = (await getSetting(env, "mail_provider", "")).toLowerCase();
  const token = await getSetting(env, "mail_token", "");
  const from = await getSetting(env, "mail_from", "");
  const name = await getSetting(env, "mail_from_name", "Colorilax Case Vault");
  if (!provider || !token || !from) {
    if (env.ENV_NAME !== "production") return { ok: true, dev: true };
    throw new Error("mail not configured");
  }
  let r;
  if (provider === "zeptomail") {
    r = await net(env)("https://api.zeptomail.com/v1.1/email", {
      method: "POST",
      headers: { "content-type": "application/json", authorization: token.startsWith("Zoho") ? token : `Zoho-enczapikey ${token}` },
      body: JSON.stringify({ from: { address: from, name }, to: [{ email_address: { address: to } }], subject, htmlbody: htmlBody }),
    });
  } else if (provider === "resend") {
    r = await net(env)("https://api.resend.com/emails", {
      method: "POST", headers: { "content-type": "application/json", authorization: `Bearer ${token}` },
      body: JSON.stringify({ from: `${name} <${from}>`, to: [to], subject, html: htmlBody }),
    });
  } else throw new Error(`unknown mail provider ${provider}`);
  if (!r.ok) throw new Error(`mail HTTP ${r.status}`);
  return { ok: true };
}

const KLAVIYO_REV = "2024-10-15";
async function klaviyo(env, path, body) {
  const key = await getSetting(env, "klaviyo_key", "");
  if (!key) return { skipped: true };
  const r = await net(env)(`https://a.klaviyo.com/api/${path}`, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json", revision: KLAVIYO_REV, authorization: `Klaviyo-API-Key ${key}` },
    body: JSON.stringify(body),
  });
  if (!r.ok && r.status !== 409) throw new Error(`klaviyo ${path} HTTP ${r.status}`);
  return { ok: true };
}
function klaviyoEventBody(email, metric, props, profileProps) {
  return { data: { type: "event", attributes: {
    properties: props, unique_id: props.unique_id || undefined,
    metric: { data: { type: "metric", attributes: { name: metric } } },
    profile: { data: { type: "profile", attributes: { email, properties: profileProps || {} } } },
  } } };
}
async function klaviyoSubscription(env, email, subscribe) {
  const list = await getSetting(env, "klaviyo_list_id", "");
  if (!list) return { skipped: true };
  if (subscribe) {
    return klaviyo(env, "profile-subscription-bulk-create-jobs", { data: {
      type: "profile-subscription-bulk-create-job",
      attributes: { custom_source: "CaseVault", profiles: { data: [{ type: "profile", attributes: { email,
        subscriptions: { email: { marketing: { consent: "SUBSCRIBED" } } } } }] } },
      relationships: { list: { data: { type: "list", id: list } } } } });
  }
  return klaviyo(env, "profile-subscription-bulk-delete-jobs", { data: {
    type: "profile-subscription-bulk-delete-job",
    attributes: { profiles: { data: [{ type: "profile", attributes: { email } }] } },
    relationships: { list: { data: { type: "list", id: list } } } } });
}

// Shopify Admin token: a fixed token (legacy custom app) or, for a Dev Dashboard app, client_id + client_secret
// exchanged for a ~24 h token (client-credentials grant), cached encrypted in settings until 10 min before expiry.
function shopHost(shop) { return String(shop || "").replace(/^https?:\/\//, "").replace(/\/$/, ""); }
async function shopifyToken(env, force = false) {
  const fixed = await getSetting(env, "shopify_token", "");
  if (fixed) return fixed;
  const shop = shopHost(await getSetting(env, "shopify_shop", ""));
  const id = await getSetting(env, "shopify_client_id", "");
  const secret = await getSetting(env, "shopify_client_secret", "");
  if (!shop || !id || !secret) return "";
  const exp = Number(await getSetting(env, "shopify_cc_exp", "0")) || 0;
  if (!force && exp - Date.now() > 10 * 60000) { const t = await getSetting(env, "shopify_cc_token", ""); if (t) return t; }
  const r = await net(env)(`https://${shop}/admin/oauth/access_token`, { method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded", accept: "application/json" },
    body: new URLSearchParams({ grant_type: "client_credentials", client_id: id, client_secret: secret }).toString() });
  if (!r.ok) {
    const t = (await r.text().catch(() => "")).replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    let why = t; try { const e = JSON.parse(t); why = [e.error, e.error_description, e.errors].filter(Boolean).join(": "); } catch { /* not JSON */ }
    throw new Error(`shopify token HTTP ${r.status}${why ? ` (${String(why).slice(0, 160)})` : ""}`);
  }
  const j = await r.json();
  if (!j.access_token) throw new Error("shopify token: no access_token");
  await setSetting(env, "shopify_cc_token", j.access_token);
  await setSetting(env, "shopify_cc_exp", String(Date.now() + (Number(j.expires_in) || 3600) * 1000));
  return j.access_token;
}

// Shopify: single-use 15 % code limited to one product (the next book).
async function shopifyDiscount(env, { code, productId, pct, days, title }) {
  const shop = await getSetting(env, "shopify_shop", "");
  const token = await shopifyToken(env);
  if (!shop || !token) throw new Error("shopify not configured");
  const ver = (await getSetting(env, "shopify_api_version", "")) || "2024-10";
  const gid = String(productId).startsWith("gid://") ? productId : `gid://shopify/Product/${productId}`;
  const query = `mutation($d: DiscountCodeBasicInput!) { discountCodeBasicCreate(basicCodeDiscount: $d) {
    codeDiscountNode { id } userErrors { field message } } }`;
  const variables = { d: {
    title, code, startsAt: nowIso(), endsAt: plusDays(days), usageLimit: 1, appliesOncePerCustomer: true,
    customerSelection: { all: true },
    customerGets: { value: { percentage: pct / 100 }, items: { products: { productsToAdd: [gid] } } },
    combinesWith: { orderDiscounts: false, productDiscounts: false, shippingDiscounts: false },
  } };
  const r = await net(env)(`https://${shop.replace(/^https?:\/\//, "").replace(/\/$/, "")}/admin/api/${ver}/graphql.json`, {
    method: "POST", headers: { "content-type": "application/json", "x-shopify-access-token": token },
    body: JSON.stringify({ query, variables }),
  });
  if (!r.ok) throw new Error(`shopify HTTP ${r.status}`);
  const j = await r.json();
  const errs = j?.data?.discountCodeBasicCreate?.userErrors || j?.errors || [];
  if (errs.length) throw new Error(`shopify: ${JSON.stringify(errs).slice(0, 200)}`);
  return { ok: true };
}

async function telegram(env, text) {
  const token = await getSetting(env, "telegram_token", "");
  const chat = await getSetting(env, "telegram_chat", "");
  if (!token || !chat) return { skipped: true };
  const r = await net(env)(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ chat_id: chat, text: `[CaseVault ${env.ENV_NAME || "dev"}] ${text}` }),
  });
  if (!r.ok) throw new Error(`telegram HTTP ${r.status}`);
  return { ok: true };
}

async function turnstileOk(env, token, ip) {
  const secret = await getSetting(env, "turnstile_secret", "");
  if (!secret) return true; // not configured (staging / tests): server-side rate limits still apply
  if (!token) return false;
  const f = new FormData();
  f.append("secret", secret); f.append("response", token); f.append("remoteip", ip);
  const r = await net(env)("https://challenges.cloudflare.com/turnstile/v0/siteverify", { method: "POST", body: f });
  const j = await r.json().catch(() => ({}));
  return !!j.success;
}

// Outbox worker: one place for retries. Klaviyo failure never loses a reward (it is stored first).
async function processOutbox(env, limit = 25) {
  const rows = await all(env, "SELECT * FROM outbox WHERE done=0 AND next_at<=? ORDER BY id LIMIT ?", nowIso(), limit);
  let sent = 0;
  for (const row of rows) {
    const p = jparse(row.payload, {});
    try {
      if (row.kind === "mail") await sendMail(env, p.to, p.subject, p.html);
      else if (row.kind === "klaviyo_event") await klaviyo(env, "events", klaviyoEventBody(p.email, p.metric, p.props, p.profile));
      else if (row.kind === "klaviyo_sub") await klaviyoSubscription(env, p.email, p.subscribe);
      else if (row.kind === "telegram") await telegram(env, p.text);
      else if (row.kind === "reward_issue") await issuePendingReward(env, p.reward_id);
      await run(env, "UPDATE outbox SET done=1, attempts=attempts+1, last_error=NULL WHERE id=?", row.id);
      sent++;
    } catch (e) {
      const n = row.attempts + 1;
      const wait = Math.min(2 ** n, 360) * 60000;
      await run(env, "UPDATE outbox SET attempts=?, next_at=?, last_error=?, done=? WHERE id=?",
        n, isoAt(Date.now() + wait), String(e.message || e).slice(0, 300), n >= 30 ? 2 : 0, row.id);
      if (n === 5 && row.kind !== "telegram") await enqueue(env, "telegram", { text: `${row.kind} keeps failing: ${String(e.message || e).slice(0, 120)}` });
    }
  }
  return sent;
}

// Klaviyo profile properties (spec §6): tier, points, solved, series progress.
async function profileProps(env, acc) {
  const solved = await all(env, "SELECT DISTINCT s.book_id, b.series_id FROM solves s JOIN books b ON b.book_id=s.book_id WHERE s.account_id=? AND s.status='verified'", acc.id);
  const prog = {};
  for (const s of solved) if (s.series_id) prog[s.series_id] = (prog[s.series_id] || 0) + 1;
  const ch = await one(env, "SELECT channel FROM solves WHERE account_id=? AND channel IS NOT NULL ORDER BY id DESC LIMIT 1", acc.id);
  return { cv_tier: acc.tier, cv_points_total: acc.points_total, cv_points_available: acc.points_avail,
    cv_cases_solved: solved.length, cv_series_progress: prog, cv_purchase_channel: ch ? ch.channel : null };
}
async function kEvent(env, acc, metric, props = {}) {
  const fresh = await one(env, "SELECT * FROM accounts WHERE id=?", acc.id);
  await enqueue(env, "klaviyo_event", { email: fresh.email, metric, props, profile: await profileProps(env, fresh) });
}
