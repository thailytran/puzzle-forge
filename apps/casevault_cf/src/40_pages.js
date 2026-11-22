// ---- public pages (spec §2, §9b) -------------------------------------------------------------------
const LINES = {
  mystery: { name: "Mystery", color: "#8E2A2A", icon: "🔍" },
  escape: { name: "Escape", color: "#2E8C8C", icon: "🔒" },
  adventure: { name: "Adventure", color: "#4F6B3A", icon: "🧭" },
  hidden: { name: "Hidden Object", color: "#5B4A8B", icon: "✨" },
};
const CSS = `
:root{--ink:#14171F;--ink2:#1D2230;--paper:#EFE6D2;--ivory:#F5F1E8;--brass:#C9A24A;--stamp:#B23A2E;--muted:#B9B2A3}
*{box-sizing:border-box}body{margin:0;background:var(--ink);color:var(--ivory);font:16px/1.55 Inter,system-ui,sans-serif}
a{color:var(--brass)}h1,h2,h3{font-family:"Playfair Display",Georgia,serif;line-height:1.2;margin:.2em 0 .5em}
.mono{font-family:"Special Elite","IBM Plex Mono",monospace;letter-spacing:.04em}
.wrap{max-width:1080px;margin:0 auto;padding:0 16px}
header.top{display:flex;justify-content:space-between;align-items:center;padding:14px 16px;max-width:1080px;margin:0 auto}
header.top .brand{font-family:"Playfair Display",serif;font-size:22px;color:var(--ivory);text-decoration:none;display:flex;align-items:center;gap:10px}
header.top .brand small{display:block;font:600 10px Inter,sans-serif;letter-spacing:.32em;color:var(--brass);line-height:1}
header.top .brand b{color:var(--brass)}header.top nav a{margin-left:16px;text-decoration:none;font-size:15px}
.hero{background:linear-gradient(90deg,rgba(20,23,31,.92),rgba(20,23,31,.55)),url(/assets/hero_bg.jpg) center/cover no-repeat;border-radius:16px;padding:28px;display:grid;grid-template-columns:1.2fr .8fr;gap:28px;align-items:center;margin:16px 0 8px}
.hero .deco{border:1px solid #2c3242;border-radius:14px;padding:22px;background:repeating-linear-gradient(135deg,#191d27 0 12px,#1b2029 12px 24px);min-height:250px;position:relative}
.deco .tag{position:absolute;top:16px;right:-8px;background:var(--stamp);color:#fff;padding:4px 14px;transform:rotate(6deg)}
.card{background:var(--paper);color:#22211d;border-radius:12px;padding:22px}
.card h2,.card h3{color:#1b1a17}label{display:block;font-weight:600;margin:12px 0 4px;font-size:15px}
select,input[type=text],input[type=email],input[type=password],input[type=number],textarea{width:100%;padding:12px;border:1px solid #9c9180;border-radius:8px;font:inherit;background:#fffdf8;color:#1b1a17}
input.code{font-size:26px;letter-spacing:.18em;text-transform:uppercase;font-family:"IBM Plex Mono",monospace;text-align:center}
.btn{display:inline-block;background:var(--brass);color:#14171F;border:0;border-radius:8px;padding:13px 22px;font:600 17px Inter,sans-serif;cursor:pointer;text-decoration:none}
.btn.ghost{background:transparent;color:var(--brass);border:1px solid var(--brass)}.btn.small{padding:8px 14px;font-size:14px}
.btn:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #ffd77a;outline-offset:2px}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.muted{color:var(--muted)}.card .muted{color:#6b6457}
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 18px}.tabs button{border:2px solid var(--c);background:transparent;color:var(--ivory);border-radius:20px;padding:7px 16px;font:600 14px Inter;cursor:pointer}
.tabs button.on{background:var(--c)}
.shelf{margin:8px 0 26px}.shelf .books{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:14px}
.book{background:var(--ink2);border-radius:10px;overflow:hidden;border-top:4px solid var(--c);text-decoration:none;color:var(--ivory);display:block}
.book img,.book .ph{width:100%;aspect-ratio:3/4;object-fit:cover;display:block;background:#262c3a}
.book .ph{display:flex;align-items:center;justify-content:center;font-size:40px}
.book .meta{padding:8px 10px;font-size:13px}.book .meta b{display:block;font-size:14px;margin-bottom:2px}
.label{display:inline-block;font-size:12px;padding:2px 8px;border-radius:10px;background:var(--c);color:#fff}
.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.steps div{background:var(--ink2);border-radius:10px;padding:16px}
.tiers{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.tiers div{border:1px solid #3a4152;border-radius:10px;padding:14px}
.ai-note{display:inline-block;margin:6px 0 8px;padding:4px 12px;border:1px solid #3a4152;border-radius:14px;font-size:12.5px;color:#d9cfb8}
section{padding:22px 0}footer{border-top:1px solid #2c3242;margin-top:30px;padding:20px 16px;text-align:center;font-size:14px;color:var(--muted)}
.result{max-width:640px;margin:30px auto}.stamp{display:inline-block;border:5px solid var(--stamp);color:var(--stamp);padding:6px 18px;font:700 34px "Special Elite",monospace;transform:rotate(-8deg);animation:stamp .5s ease-out}
@keyframes stamp{from{transform:scale(2.2) rotate(-8deg);opacity:0}to{transform:scale(1) rotate(-8deg);opacity:1}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
.ending{white-space:pre-wrap;font-family:Georgia,serif;font-size:17px;line-height:1.7}
.reward{border:2px dashed var(--brass);border-radius:10px;padding:14px;margin:16px 0;background:#fff8e6}
.err{background:#fbe5e1;color:#7a1f16;border-radius:8px;padding:10px 12px;margin:10px 0}.ok{background:#e4f1e1;color:#1e4d17;border-radius:8px;padding:10px 12px;margin:10px 0}
table.t{width:100%;border-collapse:collapse;font-size:14px}table.t td,table.t th{border-bottom:1px solid #d6ccb6;padding:6px;text-align:left}
.bar{height:10px;background:#d6ccb6;border-radius:6px;overflow:hidden}.bar i{display:block;height:100%;background:var(--brass)}
.files{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:10px}.file{border-radius:8px;padding:10px 10px 28px;background:#e6dcc5;font-size:13px;position:relative;min-height:70px}
.file.solved::after{content:"SOLVED";position:absolute;right:6px;bottom:6px;color:var(--stamp);border:2px solid var(--stamp);font:700 11px "Special Elite";padding:1px 5px;transform:rotate(-8deg)}
.file.open{opacity:.55}
@media (max-width:760px){.hero{grid-template-columns:1fr}.hero .deco{display:none}.steps,.tiers{grid-template-columns:1fr 1fr}header.top nav a{margin-left:10px}}
`;

function layout(title, body, o = {}) {
  const ts = o.turnstile ? `<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>` : "";
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(title)} · Colorilax Case Vault</title><meta name="description" content="Solved your Colorilax case? Enter the final code, read the extended ending and claim your reward.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Playfair+Display:wght@600;700&family=Special+Elite&family=IBM+Plex+Mono:wght@500&display=swap" rel="stylesheet">
<style>${CSS}</style>${ts}</head><body>
<header class="top"><a class="brand" href="/"><img src="/assets/emblem.png" alt="" width="40" height="40" onerror="this.remove()"><span><small>COLORILAX</small> Case <b>Vault</b></span></a><nav><a href="/cases">Case files</a><a href="${o.user ? "/account" : "/login"}">${o.user ? "Detective File" : "Sign in"}</a></nav></header>
<main>${body}</main>
<footer><a href="/rules">Reward rules</a> · <a href="/privacy">Privacy</a> · <a href="mailto:${esc(o.support || DEFAULT_RULES.support_email)}">Contact</a>
<p style="margin:10px 0 4px">© ${new Date().getUTCFullYear()} Colorilax · HaloSpark e-Commerce Inc. All rights reserved.</p>
<p class="ai-note">✦ All Colorilax books are created with the help of AI tools, then checked and finished by our team.</p><span class="mono" style="font-size:11px;opacity:.6">Case Vault v${VERSION}</span></footer>
</body></html>`;
}
const lineOf = (b) => LINES[b.line] || LINES.mystery;
function coverImg(b) {
  return b.cover_key ? `<img src="/cover/${encodeURIComponent(b.book_id)}" alt="Cover of ${esc(b.title)}" loading="lazy">`
    : `<div class="ph" aria-hidden="true">${lineOf(b).icon}</div>`;
}
function bookCard(b) {
  const l = lineOf(b);
  const pos = b.series_order && b.series_total ? `Book ${b.series_order} of ${b.series_total}` : "";
  return `<a class="book" style="--c:${l.color}" href="/case/${encodeURIComponent(b.book_id)}" data-line="${esc(b.line)}">${coverImg(b)}
<div class="meta"><b>${esc(b.title)}</b>${pos ? `<span class="mono">${pos}</span><br>` : ""}${b.status === "upcoming" || !released(b) ? `<span class="label" style="--c:#555">Opens ${esc(b.release_date || "soon")}</span>` : `<span class="label">${l.name}</span>`}</div></a>`;
}
function bookSelect(books, selected) {
  const groups = {};
  for (const b of books.filter(released)) (groups[b.series_title || "Single cases"] ||= []).push(b);
  return `<select name="book" id="book" required><option value="">Choose your book…</option>${Object.entries(groups).map(([g, bs]) =>
    `<optgroup label="${esc(g)}">${bs.map((b) => `<option value="${esc(b.book_id)}"${b.book_id === selected ? " selected" : ""}>${esc(b.title)}${b.series_order ? ` (Book ${b.series_order})` : ""}</option>`).join("")}</optgroup>`).join("")}</select>`;
}
function answerFields(book) {
  const a = jparse(book && book.answers, {});
  const kinds = Object.keys(a).length ? Object.keys(a) : ["culprit_name"];
  return kinds.map((k) => `<label for="a_${k}">${k === "unlock_code" ? "Final unlock code" : esc((book && book.answer_label) || "Final code")}</label>
<input class="code" type="text" id="a_${k}" name="a_${k}" autocomplete="off" autocapitalize="characters" spellcheck="false" required maxlength="60">`).join("");
}

async function homePage(env, ctx, url) {
  const books = await publicBooks(env);
  const selected = url.searchParams.get("book") || "";
  const sel = books.find((b) => b.book_id === selected);
  const site = await getSetting(env, "turnstile_site", "");
  const R = await rules(env);
  const series = {};
  for (const b of books) (series[b.series_id || `single-${b.line}`] ||= { title: b.series_title || "Single cases", line: b.line, books: [] }).books.push(b);
  const upcoming = books.filter((b) => !released(b)).slice(0, 6);
  const tierInfo = { Rookie: "15% off the next book after every case · extended endings", Detective: "New-case e-mails 48 hours early",
    Inspector: "A free short case every quarter · redeem points for books", "Chief Inspector": "Your name on a minor character in a new book (with your OK)" };
  const body = `<div class="wrap"><div class="hero"><div class="card">
<h1>Solved your case? Enter the final code</h1>
<form method="post" action="/check">${bookSelect(books, selected)}
<div id="answers">${answerFields(sel)}</div>
${site ? `<div class="cf-turnstile" data-sitekey="${esc(site)}" data-appearance="interaction-only"></div>` : ""}
<div class="row" style="margin-top:14px"><button class="btn" type="submit">Open the vault</button><a class="btn ghost" href="/cases">Browse the case files</a></div>
<p class="muted" style="font-size:14px;margin-bottom:0">Stuck? The full logical solution is printed at the back of your book. No account is needed to check an answer.</p></form></div>
<div class="deco"><span class="tag mono">CONFIDENTIAL</span><h2 class="mono" style="color:var(--brass)">CASE FILE</h2>
<p>Every Colorilax mystery ends with one final code. Type it here to open the extended ending, a few pages that are not in the book, and collect your reward.</p>
<p class="mono muted">#${String(books.length).padStart(3, "0")} cases on file</p></div></div>
<section><div class="tabs" role="tablist"><button class="on" style="--c:#C9A24A" data-f="">All</button>${Object.entries(LINES).map(([k, l]) => `<button style="--c:${l.color}" data-f="${k}">${l.icon} ${l.name}</button>`).join("")}</div>
${Object.values(series).map((s) => `<div class="shelf" data-line="${esc(s.line)}"><h3>${esc(s.title)}</h3><div class="books">${s.books.map(bookCard).join("")}</div></div>`).join("") || `<p class="muted">The first case files open soon.</p>`}</section>
${upcoming.length ? `<section><h2>Opening soon</h2><div class="shelf"><div class="books">${upcoming.map(bookCard).join("")}</div></div></section>` : ""}
<section><h2>How it works</h2><div class="steps"><div><b class="mono">01</b><h3>Solve in the book</h3>Every puzzle gives you a clue. The last one gives you the final code.</div>
<div><b class="mono">02</b><h3>Enter the code</h3>Pick your book, type the code, open the vault.</div><div><b class="mono">03</b><h3>Read the ending, get rewarded</h3>Extended ending for everyone. Points and ${R.coupon_pct}% off the next book for detectives with an account.</div></div></section>
<section><h2>Detective ranks</h2><div class="tiers">${R.tiers.map(([n, p]) => `<div><b>${esc(n)}</b><br><span class="mono muted">${p} pts</span><p style="margin:6px 0 0;font-size:14px">${esc(tierInfo[n] || "")}</p></div>`).join("")}</div></section>
<section><h2>Questions</h2><details><summary>Do I need an account?</summary><p>No, to check an answer and read the extended ending. Yes, to collect rewards: it takes under a minute and needs only your e-mail.</p></details>
<details><summary>Where is my Book Code?</summary><p>On the last page of your personal PDF (colorilax.com) or printed inside your paperback. Bought on Etsy? Use your Etsy order number instead.</p></details>
<details><summary>I typed the right answer but it says no.</summary><p>Check the spelling on the solution page at the back of the book. Upper/lower case, accents and spaces do not matter.</p></details>
<details><summary>Do you reward reviews?</summary><p>No. Reviews are never rewarded.</p></details></section></div>
<script>document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('on',x===b));const f=b.dataset.f;document.querySelectorAll('.shelf[data-line]').forEach(s=>s.style.display=!f||s.dataset.line===f?'':'none')});
document.getElementById('book').onchange=e=>{location.search='?book='+encodeURIComponent(e.target.value)}</script>`;
  return html(layout("Enter the final code", body, { user: ctx.user, turnstile: !!site, support: R.support_email }));
}

async function casesPage(env, ctx, url) {
  const books = await publicBooks(env);
  const f = { line: url.searchParams.get("line") || "", series: url.searchParams.get("series") || "", diff: url.searchParams.get("difficulty") || "", aud: url.searchParams.get("audience") || "" };
  const list = books.filter((b) => (!f.line || b.line === f.line) && (!f.series || b.series_id === f.series) && (!f.diff || String(b.difficulty) === f.diff) && (!f.aud || b.audience === f.aud));
  const seriesOpts = [...new Map(books.filter((b) => b.series_id).map((b) => [b.series_id, b.series_title])).entries()];
  const opt = (v, l, cur) => `<option value="${esc(v)}"${v === cur ? " selected" : ""}>${esc(l)}</option>`;
  const body = `<div class="wrap"><h1>Case files</h1><form class="row" method="get">
<select name="line" style="max-width:200px">${opt("", "All lines", f.line)}${Object.entries(LINES).map(([k, l]) => opt(k, l.name, f.line)).join("")}</select>
<select name="series" style="max-width:240px">${opt("", "All series", f.series)}${seriesOpts.map(([k, t]) => opt(k, t, f.series)).join("")}</select>
<select name="difficulty" style="max-width:160px">${opt("", "Any difficulty", f.diff)}${[1, 2, 3, 4, 5].map((d) => opt(String(d), "🔍".repeat(d), f.diff)).join("")}</select>
<select name="audience" style="max-width:160px">${opt("", "Adults & family", f.aud)}${opt("adult", "Adults", f.aud)}${opt("family", "Family", f.aud)}</select>
<button class="btn small" type="submit">Filter</button></form>
<div class="shelf" style="margin-top:18px"><div class="books">${list.map(bookCard).join("") || `<p class="muted">No case files match.</p>`}</div></div></div>`;
  return html(layout("Case files", body, { user: ctx.user }));
}

function buyButtons(b, user, R) {
  const etsy = b.etsy_url ? `<a class="btn small" href="${esc(b.etsy_url)}" rel="noopener">Buy on Etsy</a>` : "";
  const shop = b.shop_url ? `<a class="btn small ghost" href="${esc(b.shop_url)}" rel="noopener">Buy on colorilax.com</a>` : "";
  return user && user.lastChannel === "etsy" ? etsy + shop : shop + etsy;
}

async function bookPage(env, ctx, id) {
  const b = await getBook(env, id);
  if (!b || b.status === "hidden") return notFound(ctx);
  const R = await rules(env);
  const l = lineOf(b);
  const prev = b.series_id ? await one(env, "SELECT book_id,title FROM books WHERE series_id=? AND series_order=? AND status<>'hidden'", b.series_id, (b.series_order || 0) - 1) : null;
  const next = b.series_id ? await one(env, "SELECT book_id,title FROM books WHERE series_id=? AND series_order=? AND status<>'hidden'", b.series_id, (b.series_order || 0) + 1) : null;
  const n = await one(env, "SELECT COUNT(DISTINCT account_id) AS n FROM solves WHERE book_id=? AND status='verified'", b.book_id);
  const body = `<div class="wrap" style="--c:${l.color}"><div class="hero"><div><span class="label">${l.icon} ${l.name}</span>
<h1>${esc(b.title)}</h1>${b.series_order ? `<p class="mono">Book ${b.series_order}${b.series_id ? "" : ""}</p>` : ""}
<p>${esc(b.blurb || "")}</p><p class="muted">${b.difficulty ? `Difficulty ${"🔍".repeat(b.difficulty)} · ` : ""}${b.pages ? `${b.pages} pages · ` : ""}${b.solve_minutes ? `about ${Math.round(b.solve_minutes / 60)} h to solve` : ""}</p>
${n && n.n >= R.solved_count_min ? `<p class="mono">${n.n.toLocaleString("en-US")} detectives have solved this case</p>` : ""}
${released(b) ? `<div class="row">${buyButtons(b, ctx.user, R)}<a class="btn small ghost" href="/?book=${encodeURIComponent(b.book_id)}">I solved it</a></div>`
    : `<form class="row" method="post" action="/notify"><input type="hidden" name="book" value="${esc(b.book_id)}"><input type="email" name="email" required placeholder="you@example.com" style="max-width:260px"><button class="btn small">Notify me</button></form><p class="muted">Opens ${esc(b.release_date || "soon")}.</p>`}
<p>${prev ? `← <a href="/case/${encodeURIComponent(prev.book_id)}">${esc(prev.title)}</a>` : ""} ${next ? ` · <a href="/case/${encodeURIComponent(next.book_id)}">${esc(next.title)}</a> →` : ""}</p></div>
<div class="book" style="max-width:300px">${coverImg(b)}</div></div></div>`;
  return html(layout(b.title, body, { user: ctx.user }));
}

function notFound(ctx) {
  return html(layout("Not found", `<div class="wrap result"><h1>Case not found</h1><p><a href="/">Back to the vault</a></p></div>`, { user: ctx && ctx.user }), 404);
}
function infoPage(ctx, title, inner) {
  return html(layout(title, `<div class="wrap result"><div class="card">${inner}</div></div>`, { user: ctx.user }));
}

// POST /check — the answer check. Never reveals the right answer; never says "close".
async function checkAnswer(env, ctx, req) {
  const f = await readBody(req);
  const R = await rules(env);
  const ip = clientIp(req);
  const book = await getBook(env, f.book);
  if (!book || !released(book)) return infoPage(ctx, "Choose a book", `<h2>Please choose your book</h2><p><a href="/">Back</a></p>`);
  if (!(await turnstileOk(env, f["cf-turnstile-response"], ip))) return infoPage(ctx, "Check", `<div class="err">We could not confirm you are human. Please try again.</div><p><a href="/?book=${encodeURIComponent(book.book_id)}">Back</a></p>`);
  const ipCount = await countAttempts(env, "scope='answer' AND ip=?", [ip]);
  if (ipCount >= R.ip_per_hour) return infoPage(ctx, "Slow down", `<h2>Lots of tries from your network</h2><p>Please wait a little and try again.</p>`);
  // Owner rule 2026-11-21: wrong answers may be retried until right. After 5 misses in 10 minutes a
  // short pause (anti-bot) applies; no hourly lock-out.
  const recentWrong = await countAttempts(env, "scope='answer' AND ok=0 AND book_id=? AND (ip=? OR vid=?)", [book.book_id, ip, ctx.vid], 10);
  const last = await one(env, "SELECT ts FROM attempts WHERE scope='answer' AND ok=0 AND book_id=? AND (ip=? OR vid=?) ORDER BY id DESC LIMIT 1", book.book_id, ip, ctx.vid);
  if (recentWrong >= R.wrong_before_pause && last && Date.parse(last.ts) > Date.now() - R.pause_seconds * 1000) {
    return infoPage(ctx, "Take a breath", `<h2>Take a breath, detective</h2><p>Please wait ${R.pause_seconds} seconds before the next try. Re-read your clues: the full logical solution is printed at the back of your book.</p><p><a class="btn" href="/?book=${encodeURIComponent(book.book_id)}">Try again</a></p>`);
  }
  const stored = jparse(book.answers, {});
  let correct = Object.keys(stored).length > 0;
  for (const kind of Object.keys(stored)) {
    if (!ANSWER_KINDS.includes(kind)) { correct = false; break; }
    const h = await answerHash(env.VAULT_ANSWER_KEY || "", book.book_id, kind, f[`a_${kind}`] || "");
    if (!stored[kind].some((x) => timingSafeEq(x, h))) correct = false;
  }
  const everWrong = await one(env, "SELECT COUNT(*) AS n FROM attempts WHERE scope='answer' AND ok=0 AND book_id=? AND (vid=? OR (account_id IS NOT NULL AND account_id=?))", book.book_id, ctx.vid, ctx.user ? ctx.user.id : -1);
  await logAttempt(env, { book_id: book.book_id, ip, vid: ctx.vid, account_id: ctx.user && ctx.user.id, scope: "answer", ok: correct });
  if (!correct) {
    return infoPage(ctx, "Not quite", `<h2>Not quite, detective. Check your clues.</h2><p>You can try again as often as you like. Spelling tip: upper/lower case, accents and spaces do not matter. The full logical solution is printed at the back of your book.</p>
<p><a class="btn" href="/?book=${encodeURIComponent(book.book_id)}">Try again</a></p>`);
  }
  const claim = randomToken(24);
  await run(env, "INSERT INTO solves(book_id,account_id,claim_hash,first_try,status,ip,created) VALUES(?,?,?,?,?,?,?)",
    book.book_id, ctx.user ? ctx.user.id : null, await sha256(claim), everWrong.n === 0 ? 1 : 0, "open", truncIp(ip), nowIso());
  const next = book.next_book_id ? await getBook(env, book.next_book_id) : null;
  const pts = R.points.solve + (everWrong.n === 0 ? R.points.first_try : 0);
  const body = `<div class="wrap result"><div class="card" style="text-align:center"><span class="stamp">CASE SOLVED</span>
<h1 style="margin-top:18px">${esc(book.title)}</h1></div>
<div class="card" style="margin-top:14px"><h2>The extended ending</h2><div class="ending">${esc(book.extended_ending || book.ending_text || "")}</div>
<div class="reward"><b>Your reward:</b> +${pts} Case Points${next ? `, ${R.coupon_pct}% off ${esc(next.title)}` : ""}${!next && book.series_id ? ", and you are one step closer to a free book for finishing the series" : ""}.
<br><span class="muted" style="font-size:14px">Claim it within ${R.claim_hold_hours} hours with your order number or Book Code.</span></div>
<div class="row"><a class="btn" href="/claim?s=${encodeURIComponent(claim)}">Claim your reward</a>${next ? `<a class="btn ghost" href="/case/${encodeURIComponent(next.book_id)}">See ${esc(next.title)}</a>` : ""}</div></div></div>`;
  return html(layout("Case solved", body, { user: ctx.user }), 200, { "set-cookie": setCookie("cv_claim", claim, R.claim_hold_hours * 3600) });
}

async function solveByClaim(env, claim, R) {
  if (!claim) return null;
  const s = await one(env, "SELECT * FROM solves WHERE claim_hash=?", await sha256(claim));
  if (!s || s.status !== "open" || s.created < isoAt(Date.now() - R.claim_hold_hours * 3600000)) return null;
  return s;
}

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
// Sign in / create account: e-mail + password, or Google (when the owner has set the Google client in /admin).
function signupForm(next, msg, google, mode = "signin") {
  const g = google ? `<p><a class="btn ghost" style="width:100%;text-align:center" href="/auth/google?next=${encodeURIComponent(next)}">Continue with Google</a></p>
<p class="muted" style="font-size:13px;text-align:center">By continuing with Google you agree to the <a href="/rules">reward rules</a> and <a href="/privacy">privacy policy</a>.</p><p style="text-align:center" class="muted">or</p>` : "";
  const signin = `<form method="post" action="/login"><input type="hidden" name="next" value="${esc(next)}"><input type="hidden" name="mode" value="signin">
<label for="em">E-mail</label><input type="email" id="em" name="email" required autocomplete="email">
<label for="pw">Password</label><input type="password" id="pw" name="password" required autocomplete="current-password">
<p class="row"><button class="btn" type="submit">Sign in</button><a href="/forgot?next=${encodeURIComponent(next)}">Forgot password?</a></p></form>
<p>New here? <a href="?mode=signup&next=${encodeURIComponent(next)}" onclick="document.getElementById('su').hidden=false;document.getElementById('si').hidden=true;return false">Create your detective account</a> (under a minute).</p>`;
  const signup = `<form method="post" action="/login"><input type="hidden" name="next" value="${esc(next)}"><input type="hidden" name="mode" value="signup">
<label for="em2">E-mail</label><input type="email" id="em2" name="email" required autocomplete="email">
<label for="pw2">Password (8+ characters)</label><input type="password" id="pw2" name="password" required minlength="8" autocomplete="new-password">
<label for="dn">Display name <span class="muted">(optional)</span></label><input type="text" id="dn" name="display_name" maxlength="60">
<label for="bm">Birth month <span class="muted">(optional, month only: birthday points)</span></label><select id="bm" name="birth_month"><option value="">—</option>${MONTHS.map((m, i) => `<option value="${i + 1}">${m}</option>`).join("")}</select>
<label for="rf">Referral code <span class="muted">(optional)</span></label><input type="text" id="rf" name="referral" maxlength="12">
<label style="font-weight:400"><input type="checkbox" name="newsletter" value="1"> ${esc(CONSENT_TEXT)}</label>
<label style="font-weight:400"><input type="checkbox" name="terms" value="1" required> I agree to the <a href="/rules" target="_blank">reward rules</a> and <a href="/privacy" target="_blank">privacy policy</a>.</label>
<p><button class="btn" type="submit">Create account</button></p></form>
<p>Already a detective? <a href="?next=${encodeURIComponent(next)}" onclick="document.getElementById('su').hidden=true;document.getElementById('si').hidden=false;return false">Sign in</a></p>`;
  return `<h2>${next.startsWith("/claim") ? "Claim your reward" : "Your Detective File"}</h2>${msg || ""}${g}
<div id="si"${mode === "signup" ? " hidden" : ""}>${signin}</div><div id="su"${mode === "signup" ? "" : " hidden"}>${signup}</div>`;
}

async function claimPage(env, ctx, req, url) {
  const R = await rules(env);
  const claim = url.searchParams.get("s") || cookies(req).cv_claim || "";
  const s = await solveByClaim(env, claim, R);
  if (!s) return infoPage(ctx, "Claim", `<h2>Nothing to claim here</h2><p>This claim link has expired or was already used. Enter your final code again on the <a href="/">home page</a>.</p>`);
  const book = await getBook(env, s.book_id);
  if (!ctx.user) return infoPage(ctx, "Claim", signupForm(`/claim?s=${claim}`, `<p>Sign in or create a free account to collect your reward. Your solved case is saved for ${R.claim_hold_hours} hours.</p>`, await googleOn(env)));
  return infoPage(ctx, "Claim", claimForm(book, claim, ""));
}
function claimForm(book, claim, msg) {
  return `<h2>Claim your reward</h2><p><b>${esc(book.title)}</b></p>${msg}
<form method="post" action="/claim"><input type="hidden" name="s" value="${esc(claim)}">
<label>Where did you buy it?</label>
<label style="font-weight:400"><input type="radio" name="channel" value="etsy" required> Etsy (digital)</label>
<label style="font-weight:400"><input type="radio" name="channel" value="shop"> colorilax.com (digital)</label>
<label style="font-weight:400"><input type="radio" name="channel" value="print"> Printed book</label>
<div id="w_order"><label for="order">Etsy order number <span class="muted">(in your Etsy receipt e-mail)</span></label><input type="text" id="order" name="order" inputmode="numeric" maxlength="14"></div>
<div id="w_code"><label for="code">Book Code <span class="muted">(last page of your PDF or inside your printed book)</span></label><input type="text" id="code" name="code" maxlength="24" placeholder="${esc(book.prefix)}-XXXXXXXX" style="text-transform:uppercase"></div>
<p><button class="btn" type="submit">Verify and claim</button></p></form>
<script>(()=>{const o=document.getElementById('w_order'),c=document.getElementById('w_code');o.hidden=c.hidden=true;document.querySelectorAll('input[name=channel]').forEach(r=>r.onchange=()=>{o.hidden=r.value!=='etsy';c.hidden=r.value==='etsy'})})()</script>`;
}

async function claimSubmit(env, ctx, req) {
  const R = await rules(env);
  const f = await readBody(req);
  if (!ctx.user) return redirect(`/claim?s=${encodeURIComponent(f.s || "")}`);
  if (ctx.user.locked) return infoPage(ctx, "Claim", `<div class="err">This account is on hold. Please contact support.</div>`);
  const s = await solveByClaim(env, f.s, R);
  if (!s) return infoPage(ctx, "Claim", `<h2>Nothing to claim here</h2><p>This claim has expired or was already used.</p>`);
  const book = await getBook(env, s.book_id);
  const ip = clientIp(req);
  if ((await countAttempts(env, "scope='proof' AND (ip=? OR account_id=?)", [ip, ctx.user.id])) >= R.wrong_per_hour)
    return infoPage(ctx, "Claim", `<div class="err">Too many tries for now. Please wait an hour.</div>`);
  const res = await verifyProof(env, ctx.user, s, book, f);
  await logAttempt(env, { book_id: book.book_id, ip, account_id: ctx.user.id, scope: "proof", ok: res.status !== "rejected" });
  if (res.status === "rejected") return infoPage(ctx, "Claim", claimForm(book, f.s, `<div class="err">${esc(res.msg)}</div>`));
  return redirect(`/account?m=${encodeURIComponent(res.msg)}`, { "set-cookie": setCookie("cv_claim", "", 0) });
}

// ---- accounts: password sign-in, Google sign-in, reset by e-mail link (15 min, single use) -----------
async function startSession(env, accId, next) {
  const sid = randomToken(32);
  await run(env, "INSERT INTO sessions(sid_hash,account_id,expires) VALUES(?,?,?)", await sha256(sid), accId, plusDays(30));
  await run(env, "UPDATE accounts SET last_active=? WHERE id=?", nowIso(), accId);
  const to = String(next || "/account");
  return redirect(to.startsWith("/") && !to.startsWith("//") ? to : "/account", { "set-cookie": setCookie("cv_sid", sid, 30 * 86400) });
}
const googleOn = async (env) => !!(await getSetting(env, "google_client_id", "")) && !!(await getSetting(env, "google_client_secret", ""));

async function loginPage(env, ctx, url) {
  if (ctx.user) return redirect(url.searchParams.get("next") || "/account");
  const next = url.searchParams.get("next") || "/account";
  return infoPage(ctx, "Sign in", signupForm(next, "", await googleOn(env), url.searchParams.get("mode") || "signin"));
}

async function loginSubmit(env, ctx, req) {
  const f = await readBody(req);
  const ip = clientIp(req);
  const next = String(f.next || "/account").startsWith("/") ? String(f.next || "/account") : "/account";
  const g = await googleOn(env);
  const again = (m, mode) => infoPage(ctx, "Sign in", signupForm(next, `<div class="err">${m}</div>`, g, mode));
  if (!emailOk(f.email)) return again("Please enter a valid e-mail.", f.mode);
  if ((await countAttempts(env, "scope='login' AND ok=0 AND ip=?", [ip])) >= 10) return again("Too many failed sign-ins. Please wait an hour or reset your password.", f.mode);
  const email = String(f.email).trim().toLowerCase();
  const acc = await one(env, "SELECT * FROM accounts WHERE email=?", email);
  if (f.mode === "signup") {
    if (acc) return again("An account with this e-mail already exists. Sign in, or reset your password.", "signin");
    if (String(f.password || "").length < 8) return again("Please choose a password with at least 8 characters.", "signup");
    if (!f.terms) return again("Please accept the reward rules to create your account.", "signup");
    const { acc: created } = await findOrCreateAccount(env, { ...f, email }, ip);
    await run(env, "UPDATE accounts SET password_hash=? WHERE id=?", await pwHash(String(f.password)), created.id);
    await logAttempt(env, { ip, scope: "login", ok: 1 });
    return startSession(env, created.id, next);
  }
  if (!acc || !acc.password_hash || !(await pwCheck(String(f.password || ""), acc.password_hash))) {
    await logAttempt(env, { ip, scope: "login", ok: 0 });
    return again(acc && !acc.password_hash ? "This account signs in with Google, or set a password with “Forgot password?”." : "E-mail or password is not right.", "signin");
  }
  if (acc.locked) return again("This account is on hold. Please contact support.", "signin");
  await logAttempt(env, { ip, scope: "login", ok: 1 });
  return startSession(env, acc.id, next);
}

async function forgotPage(env, ctx, req, url) {
  if (req.method === "GET") return infoPage(ctx, "Reset password", `<h2>Reset your password</h2><form method="post" action="/forgot"><input type="hidden" name="next" value="${esc(url.searchParams.get("next") || "/account")}">
<label for="em">E-mail</label><input type="email" id="em" name="email" required><p><button class="btn">Send reset link</button></p></form>`);
  const f = await readBody(req);
  const ip = clientIp(req);
  const email = String(f.email || "").trim().toLowerCase();
  const acc = emailOk(email) ? await one(env, "SELECT id FROM accounts WHERE email=?", email) : null;
  let devLink = "";
  if (acc && (await countAttempts(env, "scope='reset' AND ip=?", [ip])) < 5) {
    await logAttempt(env, { ip, scope: "reset", ok: 1 });
    const token = randomToken(32);
    await run(env, "INSERT INTO login_tokens(token_hash,email,data,expires) VALUES(?,?,?,?)", await sha256(token), email, JSON.stringify({ next: f.next || "/account", reset: 1 }), isoAt(Date.now() + 15 * 60000));
    const link = `${ctx.origin}/auth?t=${encodeURIComponent(token)}`;
    const body = mailFrame(`<p>Click to choose a new password. The link works once, for 15 minutes.</p><p><a href="${link}" style="background:#C9A24A;color:#14171F;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:600">Choose a new password</a></p><p style="color:#777;font-size:13px">Did not ask for this? Just ignore this e-mail.</p>`);
    try { await sendMail(env, email, "Reset your Case Vault password", body); } catch { await enqueue(env, "mail", { to: email, subject: "Reset your Case Vault password", html: body }); }
    if (env.ENV_NAME !== "production" && !(await getSetting(env, "mail_token", ""))) devLink = `<p class="muted">Staging (no mail set up): <a href="${link}">open the reset link</a></p>`;
  }
  return infoPage(ctx, "Check your e-mail", `<h2>Check your e-mail</h2><p>If <b>${esc(email)}</b> has an account, a reset link is on its way. It works once, for 15 minutes.</p>${devLink}`);
}

async function authLink(env, ctx, url, req) {
  const t = url.searchParams.get("t") || "";
  const row = await one(env, "SELECT * FROM login_tokens WHERE token_hash=?", await sha256(t));
  if (!row || row.used || row.expires < nowIso()) return infoPage(ctx, "Link expired", `<h2>This link has expired</h2><p>Links work once, for 15 minutes. <a href="/forgot">Get a new one</a>.</p>`);
  const upd = await run(env, "UPDATE login_tokens SET used=1 WHERE token_hash=? AND used=0", row.token_hash);
  if (!(upd.meta && upd.meta.changes)) return infoPage(ctx, "Link used", `<h2>This link was already used</h2>`);
  const data = jparse(row.data, {});
  const acc = await one(env, "SELECT * FROM accounts WHERE email=?", row.email);
  if (!acc) return redirect("/login");
  const res = await startSession(env, acc.id, data.reset ? `/account/password?next=${encodeURIComponent(data.next || "/account")}` : data.next);
  return res;
}

async function passwordPage(env, ctx, req, url) {
  if (!ctx.user) return redirect("/login");
  if (req.method === "POST") {
    const f = await readBody(req);
    if (String(f.password || "").length < 8) return infoPage(ctx, "Password", `<div class="err">At least 8 characters, please.</div><p><a href="/account/password">Back</a></p>`);
    await run(env, "UPDATE accounts SET password_hash=? WHERE id=?", await pwHash(String(f.password)), ctx.user.id);
    const n = String(f.next || "/account");
    return redirect(n.startsWith("/") ? `${n}${n.includes("?") ? "&" : "?"}m=Password%20saved` : "/account");
  }
  return infoPage(ctx, "New password", `<h2>Choose a new password</h2><form method="post" action="/account/password"><input type="hidden" name="next" value="${esc(url.searchParams.get("next") || "/account")}">
<label for="pw">New password (8+ characters)</label><input type="password" id="pw" name="password" minlength="8" required autocomplete="new-password"><p><button class="btn">Save password</button></p></form>`);
}

// Google sign-in (OpenID Connect, authorization-code flow). The token comes straight from Google over TLS
// with our client secret, so the ID token payload can be read without a separate signature check.
async function googleStart(env, ctx, url) {
  if (!(await googleOn(env))) return redirect("/login");
  const state = randomToken(18);
  const next = url.searchParams.get("next") || "/account";
  const q = new URLSearchParams({ client_id: await getSetting(env, "google_client_id", ""), redirect_uri: `${ctx.origin}/auth/google/callback`,
    response_type: "code", scope: "openid email profile", state, prompt: "select_account" });
  return redirect(`https://accounts.google.com/o/oauth2/v2/auth?${q}`, { "set-cookie": setCookie("cv_gstate", `${state}|${next}`, 600) });
}
async function googleCallback(env, ctx, url, req) {
  const [state, next] = String(cookies(req).cv_gstate || "").split("|");
  if (!state || state !== url.searchParams.get("state")) return infoPage(ctx, "Google", `<div class="err">Google sign-in expired. Please try again.</div><p><a href="/login">Back</a></p>`);
  const r = await net(env)("https://oauth2.googleapis.com/token", { method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ code: url.searchParams.get("code") || "", client_id: await getSetting(env, "google_client_id", ""),
      client_secret: await getSetting(env, "google_client_secret", ""), redirect_uri: `${ctx.origin}/auth/google/callback`, grant_type: "authorization_code" }).toString() });
  const j = await r.json().catch(() => ({}));
  const part = String(j.id_token || "").split(".")[1] || "";
  const claims = jparse(part ? atob(part.replace(/-/g, "+").replace(/_/g, "/")) : "", {});
  if (!r.ok || !claims.email || !claims.email_verified) return infoPage(ctx, "Google", `<div class="err">Google did not confirm an e-mail address.</div><p><a href="/login">Back</a></p>`);
  const { acc } = await findOrCreateAccount(env, { email: claims.email, display_name: claims.given_name || claims.name, terms: 1 }, clientIp(req));
  if (acc.locked) return infoPage(ctx, "Google", `<div class="err">This account is on hold. Please contact support.</div>`);
  if (!acc.google_sub) await run(env, "UPDATE accounts SET google_sub=? WHERE id=?", String(claims.sub || ""), acc.id);
  const res = await startSession(env, acc.id, next || "/account");
  res.headers.append("set-cookie", setCookie("cv_gstate", "", 0));
  return res;
}

function mailFrame(inner) {
  return `<div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;padding:20px;background:#EFE6D2;color:#22211d;border-radius:10px"><h2 style="font-family:Georgia,serif;margin-top:0">Case Vault</h2>${inner}<p style="color:#777;font-size:12px">Colorilax · HaloSpark Inc.</p></div>`;
}

// ---- Detective File -----------------------------------------------------------------------------
async function accountPage(env, ctx, url) {
  if (!ctx.user) return infoPage(ctx, "Sign in", signupForm("/account", "", await googleOn(env)));
  const R = await rules(env);
  const a = ctx.user;
  const msg = url.searchParams.get("m");
  const rank = tierRank(a.tier, R);
  const nextTier = R.tiers[rank + 1];
  const pct = nextTier ? Math.min(100, Math.round((a.points_total / nextTier[1]) * 100)) : 100;
  const solves = await all(env, "SELECT s.*, b.title FROM solves s JOIN books b ON b.book_id=s.book_id WHERE s.account_id=? ORDER BY s.id DESC", a.id);
  const solvedIds = new Set(solves.filter((s) => s.status === "verified").map((s) => s.book_id));
  const seriesIds = [...new Set((await all(env, "SELECT b.series_id FROM solves s JOIN books b ON b.book_id=s.book_id WHERE s.account_id=? AND b.series_id IS NOT NULL", a.id)).map((r) => r.series_id))];
  let seriesHtml = "";
  for (const sid of seriesIds) {
    const s = await one(env, "SELECT * FROM series WHERE series_id=?", sid);
    const bs = await all(env, "SELECT * FROM books WHERE series_id=? AND status<>'hidden' ORDER BY series_order", sid);
    const done = bs.filter((b) => solvedIds.has(b.book_id)).length;
    seriesHtml += `<h3>${esc(s ? s.title : sid)} <span class="mono muted">${done}/${s ? s.total : bs.length}</span></h3><div class="files">${bs.map((b) => solvedIds.has(b.book_id)
      ? `<div class="file solved"><b>${b.series_order}.</b> ${esc(b.title)}</div>`
      : `<div class="file open"><b>${b.series_order}.</b> ${esc(b.title)}<br><a href="/case/${encodeURIComponent(b.book_id)}">Get it</a></div>`).join("")}</div>
${s && s.total - done > 0 && s.total - done <= 3 && s.next_series_id ? `<p class="mono">${s.total - done} ${s.total - done === 1 ? "case" : "cases"} left to unlock a free book</p>` : ""}`;
  }
  const rewards = await all(env, "SELECT r.*, b.title, b.etsy_url, b.shop_url FROM rewards r LEFT JOIN books b ON b.book_id=r.book_id WHERE r.account_id=? ORDER BY r.id DESC", a.id);
  const daysLeft = (e) => Math.max(0, Math.ceil((Date.parse(e) - Date.now()) / DAY));
  const coupons = rewards.filter((r) => r.kind === "coupon" && ["issued", "waiting_release", "retry"].includes(r.status)).map((r) => r.status === "issued"
    ? `<tr><td>${r.pct}% off <b>${esc(r.title)}</b><br><span class="muted">${r.channel === "etsy" ? "Use on Etsy" : "Use on colorilax.com"} · ${daysLeft(r.expires)} days left</span></td><td><code class="mono">${esc(r.code)}</code> <button class="btn small ghost" onclick="navigator.clipboard.writeText('${esc(r.code)}')">Copy</button></td><td><a href="${esc(r.channel === "etsy" ? r.etsy_url || R.etsy_shop_url : r.shop_url || R.shop_url)}">Shop</a></td></tr>`
    : `<tr><td>${r.pct}% off <b>${esc(r.title)}</b></td><td colspan="2" class="muted">${r.status === "waiting_release" ? "Your code arrives on release day" : "Being prepared…"}</td></tr>`).join("");
  const gifts = rewards.filter((r) => r.kind !== "coupon").map((r) => `<tr><td><b>${esc(r.title)}</b><br><span class="muted">${esc(r.note || r.kind)}</span></td><td>${r.status === "issued" ? `<a class="btn small" href="/dl/${encodeURIComponent(r.code)}">Download</a>` : `<span class="muted">${r.status === "waiting_release" ? "Reserved: sent on release day" : "Being prepared…"}</span>`}</td></tr>`).join("");
  const pending = solves.filter((s) => s.status === "pending").map((s) => `<li>${esc(s.title)}: waiting for your Etsy order to appear</li>`).join("");
  const ledger = await all(env, "SELECT * FROM points_ledger WHERE account_id=? ORDER BY id DESC LIMIT 30", a.id);
  const canRedeem = rank >= tierRank(R.redeem_min_tier, R);
  const redeemables = canRedeem ? (await all(env, "SELECT * FROM books WHERE redeemable=1 AND status='active' ORDER BY title")).filter(released) : [];
  const body = `<div class="wrap" style="max-width:860px">${msg ? `<div class="ok">${esc(msg)}</div>` : ""}
<div class="card"><div class="row" style="justify-content:space-between"><div><span class="mono muted">DETECTIVE FILE</span><h1 style="margin:0">${esc(a.display_name || a.email.split("@")[0])}</h1>
<span class="stamp" style="font-size:18px;animation:none;border-width:3px">${esc(a.tier.toUpperCase())}</span></div>
<div style="text-align:right"><span class="mono">${a.points_avail} pts available</span><br><span class="muted">${a.points_total} pts earned in total</span></div></div>
<div class="bar" style="margin-top:14px" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"><i style="width:${pct}%"></i></div>
<p class="muted">${nextTier ? `${nextTier[1] - a.points_total} points to ${esc(nextTier[0])}` : "Highest rank reached"}</p></div>
${pending ? `<div class="card" style="margin-top:14px"><h3>Waiting for verification</h3><ul>${pending}</ul></div>` : ""}
<div class="card" style="margin-top:14px"><h2>Coupon wallet</h2>${coupons ? `<table class="t">${coupons}</table>` : `<p class="muted">No coupons yet. Solve a case and claim it to get ${R.coupon_pct}% off the next book.</p>`}</div>
<div class="card" style="margin-top:14px"><h2>Cases by series</h2>${seriesHtml || `<p class="muted">No cases yet.</p>`}</div>
<div class="card" style="margin-top:14px"><h2>Gifts &amp; free books</h2>${gifts ? `<table class="t">${gifts}</table>` : `<p class="muted">Finish a whole series to get Book 1 of the next series free.</p>`}
${canRedeem ? `<form method="post" action="/account/redeem" class="row" style="margin-top:10px"><select name="book" style="max-width:320px">${redeemables.map((b) => `<option value="${esc(b.book_id)}">${esc(b.title)}</option>`).join("")}</select><button class="btn small"${a.points_avail < R.redeem_cost ? " disabled" : ""}>Redeem ${R.redeem_cost} pts</button></form>` : `<p class="muted">Redeeming points for books opens at ${esc(R.redeem_min_tier)}.</p>`}</div>
<div class="card" style="margin-top:14px"><h2>Invite a friend</h2><p>Your code: <code class="mono" style="font-size:20px">${esc(a.ref_code)}</code>. You get ${R.points.referral} points when a friend buys and solves their first case.</p></div>
<div class="card" style="margin-top:14px"><h2>Points history</h2><table class="t">${ledger.map((l) => `<tr><td>${l.ts.slice(0, 10)}</td><td>${esc(l.reason.replace("_", " "))}</td><td>${l.d_avail > 0 ? "+" : ""}${l.d_avail}</td></tr>`).join("")}</table></div>
<div class="card" style="margin-top:14px"><h2>Settings</h2><form method="post" action="/account/settings">
<label style="font-weight:400"><input type="checkbox" name="newsletter" value="1"${a.newsletter ? " checked" : ""}> ${esc(CONSENT_TEXT)}</label>
${a.tier === "Chief Inspector" ? `<label style="font-weight:400"><input type="checkbox" name="name_consent" value="1"${a.name_consent ? " checked" : ""}> You may use my display name for a minor character in a future book.</label>` : ""}
<p><button class="btn small">Save</button> <a class="btn small ghost" href="/account/password">Change password</a> <a class="btn small ghost" href="/logout">Sign out</a></p></form>
<details><summary>Delete my account</summary><form method="post" action="/account/delete"><p>This removes your e-mail, points and coupons from Case Vault. It cannot be undone.</p><label style="font-weight:400"><input type="checkbox" name="confirm" value="1" required> Yes, delete everything</label><p><button class="btn small" style="background:var(--stamp);color:#fff">Delete account</button></p></form></details></div></div>`;
  return html(layout("Detective File", body, { user: ctx.user }));
}

async function accountAction(env, ctx, req, action) {
  if (!ctx.user) return redirect("/account");
  const f = await readBody(req);
  const a = ctx.user;
  if (action === "settings") {
    const nl = f.newsletter ? 1 : 0;
    if (nl !== a.newsletter) {
      await recordConsent(env, a, !!nl, clientIp(req), "account settings");
      await enqueue(env, "klaviyo_sub", { email: a.email, subscribe: !!nl });
    }
    await run(env, "UPDATE accounts SET newsletter=?, name_consent=? WHERE id=?", nl, f.name_consent ? 1 : 0, a.id);
    return redirect("/account?m=Saved");
  }
  if (action === "redeem") {
    const r = await redeemPoints(env, a, f.book);
    return redirect(`/account?m=${encodeURIComponent(r.msg)}`);
  }
  if (action === "delete" && f.confirm) {
    await deleteAccount(env, a.id, "customer");
    return redirect("/", { "set-cookie": setCookie("cv_sid", "", 0) });
  }
  return redirect("/account");
}

async function deleteAccount(env, id, actor) {
  const a = await one(env, "SELECT email FROM accounts WHERE id=?", id);
  if (!a) return;
  if (a.email) await enqueue(env, "klaviyo_sub", { email: a.email, subscribe: false });
  for (const sql of ["DELETE FROM sessions WHERE account_id=?", "DELETE FROM points_ledger WHERE account_id=?", "DELETE FROM rewards WHERE account_id=?",
    "DELETE FROM referrals WHERE referrer_id=? OR referee_id=?", "UPDATE solves SET account_id=NULL, ip=NULL WHERE account_id=?",
    "UPDATE consents SET email=NULL WHERE account_id=?", "DELETE FROM accounts WHERE id=?"]) {
    const n = (sql.match(/\?/g) || []).length;
    await run(env, sql, ...Array(n).fill(id));
  }
  await audit(env, actor, "delete_account", { id });
}

async function download(env, ctx, token) {
  const rw = await one(env, "SELECT r.*, b.download_key, b.download_url, b.title FROM rewards r JOIN books b ON b.book_id=r.book_id WHERE r.code=? AND r.kind IN ('gift','redeem') AND r.status='issued'", token);
  if (!rw) return notFound(ctx);
  if (rw.download_key && env.BOOKS) {
    const obj = await env.BOOKS.get(rw.download_key);
    if (obj) return new Response(obj.body, { headers: { "content-type": obj.httpMetadata?.contentType || "application/octet-stream",
      "content-disposition": `attachment; filename="${rw.download_key.split("/").pop()}"`, "cache-control": "private, no-store" } });
  }
  if (rw.download_url) return redirect(rw.download_url);
  return infoPage(ctx, "Download", `<h2>Your download is being prepared</h2><p>We will e-mail you the link. Questions? Write to support.</p>`);
}

async function notifyMe(env, ctx, req) {
  const f = await readBody(req);
  const b = await getBook(env, f.book);
  if (b && emailOk(f.email)) await run(env, "INSERT OR IGNORE INTO notify(email,book_id,ts) VALUES(?,?,?)", String(f.email).trim().toLowerCase(), b.book_id, nowIso());
  return infoPage(ctx, "Noted", `<h2>Noted</h2><p>We will e-mail you once when this case opens. Nothing else.</p>`);
}

const RULES_DEFAULT = (R) => `<h1>Case Vault reward rules</h1>
<p>Rewards need a verified purchase: an Etsy order number (Etsy) or a Book Code (colorilax.com and printed books). Each order and book, and each Book Code, can be rewarded once. Solving the same book again does not count twice.</p>
<h3>After every case</h3><p>A single-use ${R.coupon_pct}% code for the next book in the same series, valid ${R.coupon_days} days from the day you receive it, not combinable with other codes. Etsy buyers receive an Etsy coupon. If the next book is not out yet, your code arrives on its release day. The last book of a series has no next book; finishing the whole series instead gives you Book 1 of the next series as a free digital book, plus ${R.points.series} points.</p>
<h3>Case Points</h3><table class="t"><tr><td>Create an account</td><td>${R.points.signup}</td></tr><tr><td>Solve a case (verified)</td><td>${R.points.solve}</td></tr><tr><td>Right on your first try</td><td>+${R.points.first_try}</td></tr><tr><td>Finish a series</td><td>+${R.points.series}</td></tr><tr><td>A friend you invited buys and solves their first case</td><td>${R.points.referral}</td></tr><tr><td>Birthday month</td><td>${R.points.birthday}</td></tr></table>
<p>Ranks use your total points and never go down: ${R.tiers.map((t) => `${t[0]} ${t[1]}`).join(" · ")}. From ${R.redeem_min_tier}, ${R.redeem_cost} available points can be exchanged for one digital book from the list we offer. Points have no cash value, cannot be transferred, and available points expire after 24 months without activity. We never give points or rewards for reviews.</p>
<p>We may cancel points or rewards obtained by abuse (shared answers without a purchase, several accounts, re-used codes). Questions: <a href="mailto:${esc(R.support_email)}">${esc(R.support_email)}</a>.</p>`;
const PRIVACY_DEFAULT = (R) => `<h1>Privacy</h1><p>Case Vault is run by HaloSpark Inc. (Colorilax). We keep only what the reward program needs: your e-mail, optional display name and birth month (month only), where you bought, your Etsy order number or Book Code, the books you solved, your points and codes, and your newsletter choice with the time it was given. From Etsy order files we keep only the order number, product and date: never names, addresses or payment details.</p>
<p>We send transactional e-mails (sign-in links, reward codes) to everyone who claims a reward. Marketing e-mails go only to people who ticked the newsletter box, and you can unsubscribe at any time. Our e-mail provider is Klaviyo. Answers you type are checked on our server and are not stored in readable form.</p>
<p>You can see your data in your Detective File and delete your account there, or ask us to send or erase your data at <a href="mailto:${esc(R.support_email)}">${esc(R.support_email)}</a>.</p>`;
