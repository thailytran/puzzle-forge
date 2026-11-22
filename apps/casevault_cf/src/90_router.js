// ---- routing, cron ----------------------------------------------------------------------------------
async function userCtx(env, req, url) {
  const c = cookies(req);
  const ctx = { origin: env.SITE_URL || url.origin, vid: c.cv_vid || "", user: null, setVid: null };
  if (!ctx.vid) { ctx.vid = randomToken(12); ctx.setVid = setCookie("cv_vid", ctx.vid, 365 * 86400); }
  if (c.cv_sid) {
    const s = await one(env, "SELECT a.* FROM sessions s JOIN accounts a ON a.id=s.account_id WHERE s.sid_hash=? AND s.expires>?", await sha256(c.cv_sid), nowIso());
    if (s) {
      const ch = await one(env, "SELECT channel FROM solves WHERE account_id=? AND channel IS NOT NULL ORDER BY id DESC LIMIT 1", s.id);
      ctx.user = { ...s, lastChannel: ch ? ch.channel : null };
    }
  }
  return ctx;
}

async function route(req, env) {
  const url = new URL(req.url);
  const p = url.pathname.replace(/\/+$/, "") || "/";
  const m = req.method;
  if (p === "/robots.txt") return new Response("User-agent: *\nDisallow: /admin\nDisallow: /account\nDisallow: /claim\n", { headers: { "content-type": "text/plain" } });
  if (p === "/healthz") return json({ ok: true, version: VERSION });
  await ensureSchema(env);
  if (p.startsWith("/api/")) return internalApi(env, req, p);
  if (p === "/admin" || p.startsWith("/admin/")) {
    if (p === "/admin/logout") return redirect("/admin", { "set-cookie": setCookie("cv_admin", "", 0, "/admin") });
    const s = await adminSession(env, req);
    if (!s) return p === "/admin" ? adminEntry(env, req, url) : redirect("/admin");
    if (p === "/admin" && m === "GET") return adminPage(env, req, url);
    if (p === "/admin/act" && m === "POST") return adminAct(env, req);
    if (p === "/admin/export/consenting.csv") return exportConsenting(env);
    return redirect("/admin");
  }
  const ctx = await userCtx(env, req, url);
  let res;
  if (p === "/" && m === "GET") res = await homePage(env, ctx, url);
  else if (p === "/cases") res = await casesPage(env, ctx, url);
  else if (p.startsWith("/case/")) res = await bookPage(env, ctx, decodeURIComponent(p.slice(6)));
  else if (p === "/check" && m === "POST") res = await checkAnswer(env, ctx, req);
  else if (p === "/claim" && m === "GET") res = await claimPage(env, ctx, req, url);
  else if (p === "/claim" && m === "POST") res = await claimSubmit(env, ctx, req);
  else if (p === "/login" && m === "POST") res = await loginSubmit(env, ctx, req);
  else if (p === "/login") res = await loginPage(env, ctx, url);
  else if (p === "/forgot") res = await forgotPage(env, ctx, req, url);
  else if (p === "/auth/google") res = await googleStart(env, ctx, url);
  else if (p === "/auth/google/callback") res = await googleCallback(env, ctx, url, req);
  else if (p === "/account/password") res = await passwordPage(env, ctx, req, url);
  else if (p === "/auth") res = await authLink(env, ctx, url, req);
  else if (p === "/account" && m === "GET") res = await accountPage(env, ctx, url);
  else if (p.startsWith("/account/") && m === "POST") res = await accountAction(env, ctx, req, p.slice(9));
  else if (p === "/logout") {
    const sid = cookies(req).cv_sid;
    if (sid) await run(env, "DELETE FROM sessions WHERE sid_hash=?", await sha256(sid));
    res = redirect("/", { "set-cookie": setCookie("cv_sid", "", 0) });
  } else if (p.startsWith("/dl/")) res = await download(env, ctx, decodeURIComponent(p.slice(4)));
  else if (p === "/notify" && m === "POST") res = await notifyMe(env, ctx, req);
  else if (p.startsWith("/cover/")) {
    const b = await getBook(env, decodeURIComponent(p.slice(7)));
    const obj = b && b.cover_key && env.FILES ? await env.FILES.get(b.cover_key) : null;
    res = obj ? new Response(obj.body, { headers: { "content-type": "image/png", "cache-control": "public, max-age=86400" } }) : notFound(ctx);
  } else if (p === "/rules") {
    const R = await rules(env);
    res = infoPage(ctx, "Reward rules", (await getSetting(env, "terms_html", "")) || RULES_DEFAULT(R));
  } else if (p === "/privacy") {
    const R = await rules(env);
    res = infoPage(ctx, "Privacy", (await getSetting(env, "privacy_html", "")) || PRIVACY_DEFAULT(R));
  } else res = notFound(ctx);
  if (ctx.setVid && res.headers) {
    res = new Response(res.body, res);
    res.headers.append("set-cookie", ctx.setVid);
  }
  return res;
}

const DAILY_CRON = "17 4 * * *";

export default {
  async fetch(req, env, execCtx) {
    try {
      const res = await route(req, env);
      if (execCtx && execCtx.waitUntil) execCtx.waitUntil(processOutbox(env, 10).catch(() => null));
      return res;
    } catch (e) {
      console.log("error", String(e && e.stack || e).slice(0, 500));
      return html(`<h1>Something went wrong</h1><p>Please try again in a minute.</p>`, 500);
    }
  },
  async scheduled(event, env) {
    await ensureSchema(env);
    await processOutbox(env, 50);
    if (event.cron === DAILY_CRON) await dailyJobs(env);
  },
};

export const _test = { route, bookCodeHash, normalizeAnswer, answerHash, newBookCode, codeLooksValid, normEmail, parseCsv, totpAt, totpOk,
  pwHash, pwCheck, processOutbox, dailyJobs, releaseDue, recheckPending, importBooks, ensureSchema, setSetting, getSetting, tierFor,
  resetSchemaFlag: () => { schemaReady = false; } };
