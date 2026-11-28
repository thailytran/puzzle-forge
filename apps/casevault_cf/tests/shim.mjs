// Local stand-ins for Cloudflare D1 + R2 so the Worker runs under `node --test` (no wrangler needed).
import { DatabaseSync } from "node:sqlite";

const val = (v) => {
  if (v === undefined) throw new Error("D1: undefined bind value");
  return typeof v === "boolean" ? (v ? 1 : 0) : v;
};
class Stmt {
  constructor(db, sql, args = []) { this.db = db; this.sql = sql; this.args = args; }
  bind(...a) { return new Stmt(this.db, this.sql, a.map(val)); }
  _p() { return this.db.prepare(this.sql); }
  async first() { const r = this._p().get(...this.args); return r ? { ...r } : null; }
  async all() { return { results: this._p().all(...this.args).map((r) => ({ ...r })) }; }
  async run() { const r = this._p().run(...this.args); return { meta: { changes: Number(r.changes) } }; }
}
export function d1() {
  const db = new DatabaseSync(":memory:");
  return {
    prepare: (sql) => new Stmt(db, sql),
    async batch(stmts) {
      db.exec("BEGIN");
      try { const out = []; for (const s of stmts) out.push(await s.run()); db.exec("COMMIT"); return out; }
      catch (e) { db.exec("ROLLBACK"); throw e; }
    },
    raw: db,
  };
}
export function r2() {
  const m = new Map();
  return {
    m,
    async put(k, v, o = {}) { m.set(k, { body: typeof v === "string" ? v : v, httpMetadata: o.httpMetadata || {} }); },
    async get(k) { const o = m.get(k); return o ? { body: o.body, httpMetadata: o.httpMetadata } : null; },
    async list({ prefix }) { return { objects: [...m.keys()].filter((k) => k.startsWith(prefix)).map((key) => ({ key })) }; },
    async delete(k) { m.delete(k); },
  };
}
// Recorded fake network: every outside call is captured; Shopify/Klaviyo answer OK.
export function fakeFetch(log) {
  return async (url, init = {}) => {
    log.push({ url: String(url), body: init.body && typeof init.body === "string" ? JSON.parse(init.body) : null });
    if (String(url).includes("shopify")) return new Response(JSON.stringify({ data: { discountCodeBasicCreate: { userErrors: [] } } }), { status: 200 });
    return new Response("{}", { status: 202 });
  };
}
