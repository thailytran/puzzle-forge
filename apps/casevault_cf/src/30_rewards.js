// ---- accounts, proof of purchase, points, tiers, coupons, gifts (spec §3, §4, §7) ---------------
function tierFor(total, R) {
  let t = R.tiers[0][0];
  for (const [name, min] of R.tiers) if (total >= min) t = name;
  return t;
}
const tierRank = (name, R) => R.tiers.findIndex((t) => t[0] === name);

async function addPoints(env, accId, dTotal, dAvail, reason, ref) {
  const r = await run(env, "INSERT OR IGNORE INTO points_ledger(account_id,d_total,d_avail,reason,ref,ts) VALUES(?,?,?,?,?,?)",
    accId, dTotal, dAvail, reason, ref == null ? "" : String(ref), nowIso());
  if (!(r.meta && r.meta.changes)) return false; // already granted once
  await run(env, "UPDATE accounts SET points_total=points_total+?, points_avail=MAX(0, points_avail+?), last_active=? WHERE id=?",
    dTotal, dAvail, nowIso(), accId);
  const acc = await one(env, "SELECT * FROM accounts WHERE id=?", accId);
  const R = await rules(env);
  const tier = tierFor(acc.points_total, R);
  if (dTotal || dAvail) await kEvent(env, acc, dAvail < 0 && !dTotal ? "Points Redeemed" : "Points Earned", { points: dAvail || dTotal, reason });
  if (tier !== acc.tier) {
    await run(env, "UPDATE accounts SET tier=? WHERE id=?", tier, accId);
    if (tierRank(tier, R) > tierRank(acc.tier, R)) await kEvent(env, { id: accId }, "Tier Reached", { tier });
  }
  return true;
}

async function findOrCreateAccount(env, f, ip) {
  const email = String(f.email || "").trim().toLowerCase();
  let acc = await one(env, "SELECT * FROM accounts WHERE email=?", email);
  if (acc) return { acc, created: false };
  const R = await rules(env);
  let ref = null;
  for (let i = 0; i < 5 && !ref; i++) {
    const c = randomFrom(CODE_ALPHABET, 7);
    if (!(await one(env, "SELECT 1 AS x FROM accounts WHERE ref_code=?", c))) ref = c;
  }
  const bm = parseInt(f.birth_month, 10);
  await run(env, `INSERT INTO accounts(email,email_norm,display_name,birth_month,ref_code,newsletter,signup_ip,created,last_active)
    VALUES(?,?,?,?,?,?,?,?,?)`, email, normEmail(email), String(f.display_name || "").slice(0, 60) || null,
    bm >= 1 && bm <= 12 ? bm : null, ref, f.newsletter ? 1 : 0, truncIp(ip), nowIso(), nowIso());
  acc = await one(env, "SELECT * FROM accounts WHERE email=?", email);
  await recordConsent(env, acc, !!f.newsletter, ip, "signup");
  if (f.newsletter) await enqueue(env, "klaviyo_sub", { email, subscribe: true });
  await kEvent(env, acc, "Account Created", {});
  await addPoints(env, acc.id, R.points.signup, R.points.signup, "signup", "");
  // referral (spec §7): same canonical e-mail or same network at signup -> owner review
  const referrer = f.referral ? await one(env, "SELECT * FROM accounts WHERE ref_code=?", String(f.referral).trim().toUpperCase()) : null;
  if (referrer && referrer.id !== acc.id) {
    const suspicious = referrer.email_norm === acc.email_norm || (referrer.signup_ip && referrer.signup_ip === acc.signup_ip);
    await run(env, "INSERT OR IGNORE INTO referrals(referrer_id,referee_id,status,reason,created) VALUES(?,?,?,?,?)",
      referrer.id, acc.id, suspicious ? "review" : "waiting", suspicious ? "same e-mail or network" : null, nowIso());
    await run(env, "UPDATE accounts SET referred_by=? WHERE id=?", referrer.id, acc.id);
    if (suspicious) await flag(env, "referral", { referrer: referrer.email, referee: email }, acc.id);
  }
  const sameIp = await one(env, "SELECT COUNT(*) AS n FROM accounts WHERE signup_ip=? AND created>=?", truncIp(ip), isoAt(Date.now() - DAY));
  if (sameIp && sameIp.n === 4) await flag(env, "ip_many_emails", { ip: truncIp(ip) }, acc.id);
  return { acc: await one(env, "SELECT * FROM accounts WHERE id=?", acc.id), created: true };
}

const CONSENT_TEXT = "Yes, send me new case releases and occasional offers from Colorilax. Unsubscribe anytime.";
async function recordConsent(env, acc, value, ip, source) {
  await run(env, "INSERT INTO consents(account_id,email,value,text,source,ip_trunc,ts) VALUES(?,?,?,?,?,?,?)",
    acc.id, acc.email, value ? 1 : 0, CONSENT_TEXT, `CaseVault ${source}`, truncIp(ip), nowIso());
}

// ---- proof of purchase --------------------------------------------------------------------------
async function etsyOrderHasBook(env, order, book) {
  const skus = jparse(book.skus, []).map(String);
  const lids = jparse(book.etsy_listing_ids, []).map(String);
  const rows = await all(env, "SELECT sku, listing_id FROM etsy_orders WHERE order_id=?", order);
  return { known: rows.length > 0, match: rows.some((r) => (r.sku && skus.includes(r.sku)) || (r.listing_id && lids.includes(r.listing_id))) };
}

// Returns {status: verified|pending|rejected, msg}
async function verifyProof(env, acc, solve, book, f) {
  const channel = ["etsy", "shop", "print"].includes(f.channel) ? f.channel : "";
  if (!channel) return { status: "rejected", msg: "Choose where you bought the book." };
  let proof, kind;
  if (channel === "etsy") {
    proof = String(f.order || "").replace(/[\s#]/g, "");
    if (!/^\d{6,12}$/.test(proof)) return { status: "rejected", msg: "An Etsy order number has 6 to 12 digits." };
    kind = "etsy";
  } else {
    const code = canonicalCode(f.code);
    if (!codeLooksValid(code, book.prefix)) return { status: "rejected", msg: `A Book Code for this book looks like ${book.prefix}-XXXXXXXX.` };
    proof = await bookCodeHash(env.VAULT_ANSWER_KEY || "", book.book_id, code);
    kind = "code";
    const c = await one(env, "SELECT * FROM book_codes WHERE code_hash=?", proof);
    if (!c || c.book_id !== book.book_id) return { status: "rejected", msg: "This Book Code was not found for this book." };
    if (c.status === "locked") return { status: "rejected", msg: "This Book Code is locked. Please contact support." };
    if (c.status === "used") return { status: "rejected", msg: "This Book Code has already been used for a reward." };
  }
  // one reward per proof (per order+book for Etsy)
  const ref = kind === "etsy" ? `${proof}|${book.book_id}` : proof;
  const used = await one(env, "SELECT account_id FROM solves WHERE proof_kind=? AND proof=? AND status IN ('verified','pending') AND id<>?", kind, ref, solve.id);
  if (used) {
    if (used.account_id !== acc.id) await flag(env, "proof_reuse", { kind, book: book.book_id, by: acc.email }, acc.id);
    return { status: "rejected", msg: "This order or code has already been used to claim this book's reward." };
  }
  if (kind === "etsy") {
    const other = await one(env, "SELECT COUNT(DISTINCT account_id) AS n FROM solves WHERE proof_kind='etsy' AND proof LIKE ? AND account_id<>?", `${proof}|%`, acc.id);
    if (other && other.n > 0) await flag(env, "etsy_order_many_emails", { order_tail: proof.slice(-4), by: acc.email }, acc.id);
  }
  await run(env, "UPDATE solves SET account_id=?, channel=?, proof_kind=?, proof=?, claimed_at=? WHERE id=?",
    acc.id, channel, kind, ref, nowIso(), solve.id);
  if (kind === "etsy") {
    const m = await etsyOrderHasBook(env, proof, book);
    if (m.known && !m.match) {
      await run(env, "UPDATE solves SET status='rejected' WHERE id=?", solve.id);
      return { status: "rejected", msg: "That Etsy order does not contain this book." };
    }
    if (!m.known) {
      await run(env, "UPDATE solves SET status='pending' WHERE id=?", solve.id);
      await kEvent(env, acc, "Reward Pending Verification", { book_id: book.book_id, book_title: book.title });
      return { status: "pending", msg: "We could not see this order yet. Your reward is saved and will be released as soon as the order appears (usually within a few days). We will e-mail you." };
    }
  } else {
    await run(env, "UPDATE book_codes SET status='used', used_by=?, used_at=? WHERE code_hash=?", acc.id, nowIso(), proof);
  }
  await grantSolve(env, solve.id);
  return { status: "verified", msg: "Verified! Your reward is ready." };
}

// ---- granting ------------------------------------------------------------------------------------
async function grantSolve(env, solveId) {
  const R = await rules(env);
  const solve = await one(env, "SELECT * FROM solves WHERE id=?", solveId);
  const acc = await one(env, "SELECT * FROM accounts WHERE id=?", solve.account_id);
  const book = await getBook(env, solve.book_id);
  // the same book was already rewarded for this person (same canonical e-mail): count nothing
  const dup = await one(env, `SELECT s.id FROM solves s JOIN accounts a ON a.id=s.account_id
    WHERE s.book_id=? AND s.status='verified' AND a.email_norm=? AND s.id<>?`, book.book_id, acc.email_norm, solve.id);
  if (dup) {
    await run(env, "UPDATE solves SET status='duplicate', verified_at=? WHERE id=?", nowIso(), solve.id);
    return { duplicate: true };
  }
  await run(env, "UPDATE solves SET status='verified', verified_at=? WHERE id=?", nowIso(), solve.id);
  await addPoints(env, acc.id, R.points.solve, R.points.solve, "solve", book.book_id);
  if (solve.first_try) await addPoints(env, acc.id, R.points.first_try, R.points.first_try, "first_try", book.book_id);
  let reward = null;
  if (book.next_book_id) reward = await createCoupon(env, acc, solve, book.next_book_id, solve.channel);
  await kEvent(env, acc, "Case Solved", { book_id: book.book_id, book_title: book.title,
    reward_level: reward ? `${reward.pct}% off next book` : "series finale",
    reward_code: reward && reward.status === "issued" ? reward.code : null, unique_id: `solve-${solve.id}` });
  if (book.series_id) await checkSeries(env, acc, book.series_id);
  // referral: the referee's first verified case rewards the referrer
  const refRow = await one(env, "SELECT * FROM referrals WHERE referee_id=? AND status='waiting'", acc.id);
  if (refRow) {
    await run(env, "UPDATE referrals SET status='awarded' WHERE id=?", refRow.id);
    await addPoints(env, refRow.referrer_id, R.points.referral, R.points.referral, "referral", acc.id);
  }
  return { reward };
}

async function createCoupon(env, acc, solve, targetBookId, channel) {
  const R = await rules(env);
  const target = await getBook(env, targetBookId);
  const now = nowIso();
  const ins = async (status, code, expires, note) => {
    await run(env, `INSERT INTO rewards(account_id,kind,book_id,channel,code,pct,status,expires,solve_id,note,created,issued_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?)`, acc.id, "coupon", targetBookId, channel, code, R.coupon_pct, status, expires,
      solve.id, note || null, now, status === "issued" ? now : null);
    return one(env, "SELECT * FROM rewards WHERE id=(SELECT MAX(id) FROM rewards WHERE account_id=?)", acc.id);
  };
  if (!released(target)) return ins("waiting_release", null, null, "issued on release day");
  const rw = await ins("retry", null, null);
  await issuePendingReward(env, rw.id).catch(async () => enqueue(env, "reward_issue", { reward_id: rw.id }));
  return one(env, "SELECT * FROM rewards WHERE id=?", rw.id);
}

// Issue a coupon reward in state retry/waiting_release (Shopify code or Etsy pool code).
async function issuePendingReward(env, rewardId) {
  const R = await rules(env);
  const rw = await one(env, "SELECT * FROM rewards WHERE id=?", rewardId);
  if (!rw || rw.status === "issued") return;
  const acc = await one(env, "SELECT * FROM accounts WHERE id=?", rw.account_id);
  const target = await getBook(env, rw.book_id);
  const expires = plusDays(R.coupon_days);
  let code;
  if (rw.kind === "gift" || rw.kind === "redeem") {
    code = randomToken(24);
  } else if (rw.channel === "etsy") {
    const c = await one(env, "SELECT code FROM etsy_coupon_pool WHERE status='free' AND pct=? ORDER BY rowid LIMIT 1", rw.pct || R.coupon_pct);
    if (!c) {
      await enqueue(env, "telegram", { text: `Etsy coupon pool (${rw.pct}%) is EMPTY - reward ${rw.id} waits` });
      throw new Error("etsy pool empty");
    }
    const upd = await run(env, "UPDATE etsy_coupon_pool SET status='used', account_id=?, issued_at=?, expires=? WHERE code=? AND status='free'", acc.id, nowIso(), expires, c.code);
    if (!(upd.meta && upd.meta.changes)) throw new Error("pool race, retry");
    code = c.code;
    const left = await one(env, "SELECT COUNT(*) AS n FROM etsy_coupon_pool WHERE status='free' AND pct=?", rw.pct || R.coupon_pct);
    if (left.n < R.pool_warn) await enqueue(env, "telegram", { text: `Etsy coupon pool ${rw.pct}%: only ${left.n} codes left` });
  } else {
    if (!target.shopify_product_id) throw new Error(`book ${target.book_id} has no Shopify product id`);
    code = `CV${rw.pct}-${randomFrom(CODE_ALPHABET, 8)}`;
    await shopifyDiscount(env, { code, productId: target.shopify_product_id, pct: rw.pct, days: R.coupon_days, title: `CaseVault ${rw.pct}% ${target.title}` });
  }
  await run(env, "UPDATE rewards SET status='issued', code=?, expires=?, issued_at=? WHERE id=?",
    code, rw.kind === "coupon" ? expires : null, nowIso(), rw.id);
  if (rw.note === "issued on release day") await kEvent(env, acc, "Next Book Released", { book_id: target.book_id, book_title: target.title });
  if (rw.kind === "coupon") await kEvent(env, acc, "Reward Released", { book_id: target.book_id, reward_code: code, pct: rw.pct, expires: expires.slice(0, 10), channel: rw.channel, unique_id: `reward-${rw.id}` });
  else await kEvent(env, acc, rw.kind === "gift" ? "Gift Book Ready" : "Points Redeemed Book", { book_id: target.book_id, book_title: target.title, download_url: `${env.SITE_URL || ""}/dl/${code}`, unique_id: `reward-${rw.id}` });
}

async function checkSeries(env, acc, seriesId) {
  const R = await rules(env);
  const s = await one(env, "SELECT * FROM series WHERE series_id=?", seriesId);
  if (!s) return;
  const n = await one(env, `SELECT COUNT(DISTINCT s.book_id) AS n FROM solves s JOIN books b ON b.book_id=s.book_id
    WHERE s.account_id=? AND s.status='verified' AND b.series_id=?`, acc.id, seriesId);
  if (n.n < s.total) return;
  const first = await addPoints(env, acc.id, R.points.series, R.points.series, "series", seriesId);
  if (!first) return;
  let gift = null;
  if (s.next_series_id) {
    gift = await one(env, "SELECT * FROM books WHERE series_id=? ORDER BY series_order LIMIT 1", s.next_series_id);
    if (gift) await createGift(env, acc, gift.book_id, "gift", `series ${seriesId} complete`);
  }
  await kEvent(env, acc, "Series Completed", { series_id: seriesId, series_title: s.title, gift_book_id: gift ? gift.book_id : null });
}

async function createGift(env, acc, bookId, kind, note) {
  const book = await getBook(env, bookId);
  await run(env, `INSERT INTO rewards(account_id,kind,book_id,channel,status,note,created) VALUES(?,?,?,?,?,?,?)`,
    acc.id, kind, bookId, "digital", released(book) ? "retry" : "waiting_release", note, nowIso());
  const rw = await one(env, "SELECT * FROM rewards WHERE id=(SELECT MAX(id) FROM rewards WHERE account_id=?)", acc.id);
  if (rw.status === "retry") await issuePendingReward(env, rw.id);
  return rw;
}

async function redeemPoints(env, acc, bookId) {
  const R = await rules(env);
  if (tierRank(acc.tier, R) < tierRank(R.redeem_min_tier, R)) return { ok: false, msg: `Redeeming opens at ${R.redeem_min_tier}.` };
  if (acc.points_avail < R.redeem_cost) return { ok: false, msg: `You need ${R.redeem_cost} available points.` };
  const book = await getBook(env, bookId);
  if (!book || !book.redeemable || !released(book)) return { ok: false, msg: "This book cannot be chosen." };
  const ok = await addPoints(env, acc.id, 0, -R.redeem_cost, "redeem", `${bookId}|${nowIso()}`);
  if (!ok) return { ok: false, msg: "Please try again." };
  await createGift(env, acc, bookId, "redeem", `${R.redeem_cost} points`);
  return { ok: true, msg: `Done! ${book.title} is in your Detective File.` };
}

// ---- daily jobs --------------------------------------------------------------------------------
async function releaseDue(env) {
  const rows = await all(env, `SELECT r.id FROM rewards r JOIN books b ON b.book_id=r.book_id
    WHERE r.status='waiting_release' AND b.status='active' AND (b.release_date IS NULL OR b.release_date<=?)`, today());
  for (const r of rows) {
    await run(env, "UPDATE rewards SET status='retry' WHERE id=?", r.id);
    await issuePendingReward(env, r.id).catch(() => enqueue(env, "reward_issue", { reward_id: r.id }));
  }
  return rows.length;
}

async function recheckPending(env) {
  const R = await rules(env);
  const rows = await all(env, "SELECT * FROM solves WHERE status='pending' AND proof_kind='etsy'");
  let released_ = 0;
  for (const s of rows) {
    const [order] = s.proof.split("|");
    const book = await getBook(env, s.book_id);
    const m = await etsyOrderHasBook(env, order, book);
    if (m.match) { await grantSolve(env, s.id); released_++; }
    else if (m.known && !m.match) await run(env, "UPDATE solves SET status='rejected' WHERE id=?", s.id);
    else if (s.claimed_at < isoAt(Date.now() - R.pending_days * DAY)) {
      await run(env, "UPDATE solves SET status='expired' WHERE id=?", s.id);
      const acc = await one(env, "SELECT * FROM accounts WHERE id=?", s.account_id);
      await enqueue(env, "mail", { to: acc.email, subject: "About your Case Vault reward",
        html: mailFrame(`<p>We still cannot match your Etsy order for <b>${esc(book.title)}</b>. Please reply to <a href="mailto:${esc(R.support_email)}">${esc(R.support_email)}</a> with a screenshot of your order and we will sort it out.</p>`) });
    }
  }
  return released_;
}

async function dailyJobs(env) {
  const R = await rules(env);
  const month = new Date().getUTCMonth() + 1, year = new Date().getUTCFullYear();
  for (const a of await all(env, "SELECT id FROM accounts WHERE birth_month=? AND (birthday_year IS NULL OR birthday_year<?) AND locked=0", month, year)) {
    await run(env, "UPDATE accounts SET birthday_year=? WHERE id=?", year, a.id);
    await addPoints(env, a.id, R.points.birthday, R.points.birthday, "birthday", String(year));
  }
  const cutoff = isoAt(Date.now() - R.points_expire_days * DAY);
  for (const a of await all(env, "SELECT id, points_avail FROM accounts WHERE points_avail>0 AND last_active<?", cutoff)) {
    await addPoints(env, a.id, 0, -a.points_avail, "expired", today());
  }
  await releaseDue(env);
  await recheckPending(env);
  await run(env, "UPDATE rewards SET status='expired' WHERE kind='coupon' AND status='issued' AND expires<?", nowIso());
  await run(env, "DELETE FROM attempts WHERE ts<?", isoAt(Date.now() - 7 * DAY));
  await run(env, "DELETE FROM login_tokens WHERE expires<?", nowIso());
  await run(env, "DELETE FROM sessions WHERE expires<?", nowIso());
  await backup(env);
}

const BACKUP_TABLES = ["settings", "series", "books", "book_codes", "etsy_orders", "accounts", "solves", "points_ledger",
  "rewards", "referrals", "etsy_coupon_pool", "consents", "notify", "flags", "audit_log"];
async function backup(env) {
  if (!env.FILES) return null;
  const dump = { version: VERSION, at: nowIso(), tables: {} };
  for (const t of BACKUP_TABLES) dump.tables[t] = await all(env, `SELECT * FROM ${t}`);
  const key = `casevault/${env.ENV_NAME || "dev"}/backup/${today()}.json`;
  await env.FILES.put(key, JSON.stringify(dump));
  const old = await env.FILES.list({ prefix: `casevault/${env.ENV_NAME || "dev"}/backup/` });
  const limit = isoAt(Date.now() - 30 * DAY).slice(0, 10);
  for (const o of old.objects || []) if (o.key.slice(-15, -5) < limit) await env.FILES.delete(o.key);
  return key;
}
