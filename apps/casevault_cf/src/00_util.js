// ---- util: time, crypto, normalisation, http helpers -------------------------------------------
const VERSION = "1.4.1";
const DAY = 86400000;
const enc = new TextEncoder();

const nowIso = () => new Date().toISOString().slice(0, 19) + "Z";
const isoAt = (ms) => new Date(ms).toISOString().slice(0, 19) + "Z";
const today = () => nowIso().slice(0, 10);
const plusDays = (d) => isoAt(Date.now() + d * DAY);

function hex(buf) {
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
async function sha256(text) {
  return hex(await crypto.subtle.digest("SHA-256", enc.encode(text)));
}
async function hmacHex(key, msg, algo = "SHA-256") {
  const k = await crypto.subtle.importKey("raw", typeof key === "string" ? enc.encode(key) : key,
    { name: "HMAC", hash: algo }, false, ["sign"]);
  return hex(await crypto.subtle.sign("HMAC", k, typeof msg === "string" ? enc.encode(msg) : msg));
}
function randomToken(n = 32) {
  const b = new Uint8Array(n);
  crypto.getRandomValues(b);
  return btoa(String.fromCharCode(...b)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function randomFrom(alphabet, n) {
  const out = [];
  const b = new Uint8Array(n * 2);
  crypto.getRandomValues(b);
  for (let i = 0; out.length < n; i++) {
    if (i >= b.length) { crypto.getRandomValues(b); i = 0; }
    const v = b[i];
    if (v < 256 - (256 % alphabet.length)) out.push(alphabet[v % alphabet.length]);
  }
  return out.join("");
}
function timingSafeEq(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}

// Answer normalisation: identical to forge/vault/answers.py (shared vectors in tests).
const ANSWER_KINDS = ["culprit_name", "unlock_code"];
function normalizeAnswer(kind, text) {
  text = String(text ?? "");
  if (kind === "unlock_code") return text.replace(/[\s\-]+/gu, "").toUpperCase();
  const t = text.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase();
  return [...t].filter((ch) => /[\p{L}\p{N}]/u.test(ch)).join("");
}
async function answerHash(key, bookId, kind, text) {
  return hmacHex(key, `${bookId}|${kind}|${normalizeAnswer(kind, text)}`);
}

// Book Codes: <PREFIX>-<8 chars>, alphabet without 0/O/1/I/L (spec §4).
const CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ";
function canonicalCode(text) {
  return String(text || "").toUpperCase().replace(/[\s_.]+/g, "").replace(/-+/g, "-").trim();
}
function newBookCode(prefix) {
  return `${prefix}-${randomFrom(CODE_ALPHABET, 8)}`;
}
// Hash kept in book_codes: same HMAC as forge/vault/answers.py code_hash (dashes/spaces removed).
async function bookCodeHash(key, bookId, code) {
  return hmacHex(key, `${bookId}|book_code|${canonicalCode(code).replace(/-/g, "")}`);
}
const LEGACY_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ";
function codeLooksValid(code, prefix) {
  const flat = code.replace(/-/g, "");
  if (flat.length === 12 && [...flat].every((c) => LEGACY_ALPHABET.includes(c)) && !code.startsWith(`${prefix}-`)) return true; // forge 12-char batches
  const m = /^([A-Z0-9]{2,12})-([A-Z0-9]{8})$/.exec(code);
  if (!m) return false;
  if (prefix && m[1] !== prefix) return false;
  return [...m[2]].every((c) => CODE_ALPHABET.includes(c));
}

// E-mail canonical form for counting (gmail dots and +tags removed).
function normEmail(e) {
  e = String(e || "").trim().toLowerCase();
  const [local, domain] = e.split("@");
  if (!domain) return e;
  let l = local.split("+")[0];
  if (domain === "gmail.com" || domain === "googlemail.com") l = l.replace(/\./g, "");
  return `${l}@${domain === "googlemail.com" ? "gmail.com" : domain}`;
}
const emailOk = (e) => /^[^\s@]{1,64}@[^\s@]{1,190}\.[a-z]{2,24}$/i.test(String(e || "").trim());
function truncIp(ip) {
  ip = String(ip || "");
  if (ip.includes(":")) return ip.split(":").slice(0, 3).join(":") + "::";
  return ip.split(".").slice(0, 3).join(".") + ".0";
}

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const jparse = (s, d) => { try { return s ? JSON.parse(s) : d; } catch { return d; } };

function cookies(req) {
  const out = {};
  for (const part of (req.headers.get("cookie") || "").split(";")) {
    const i = part.indexOf("=");
    if (i > 0) out[part.slice(0, i).trim()] = decodeURIComponent(part.slice(i + 1).trim());
  }
  return out;
}
function setCookie(name, value, maxAgeS, path = "/") {
  return `${name}=${encodeURIComponent(value)}; Path=${path}; Max-Age=${maxAgeS}; HttpOnly; Secure; SameSite=Lax`;
}
const SEC_HEADERS = {
  "x-content-type-options": "nosniff",
  "referrer-policy": "same-origin",
  "x-frame-options": "DENY",
  "strict-transport-security": "max-age=31536000",
};
function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...SEC_HEADERS, ...headers } });
}
function html(body, status = 200, headers = {}) {
  return new Response(body, {
    status, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store", ...SEC_HEADERS, ...headers } });
}
function redirect(to, headers = {}) {
  return new Response(null, { status: 303, headers: { location: to, ...headers } });
}
async function readBody(req) {
  const ct = req.headers.get("content-type") || "";
  if (ct.includes("application/json")) return (await req.json().catch(() => ({}))) || {};
  if (ct.includes("form")) {
    const f = await req.formData();
    const o = {};
    for (const [k, v] of f.entries()) o[k] = v;
    return o;
  }
  return {};
}
function clientIp(req) {
  return req.headers.get("cf-connecting-ip") || req.headers.get("x-forwarded-for") || "0.0.0.0";
}

// CSV (RFC 4180, quoted fields) -> array of objects keyed by header.
function parseCsv(text) {
  const rows = [];
  let row = [], field = "", q = false;
  text = String(text).replace(/^﻿/, "");
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"') { if (text[i + 1] === '"') { field += '"'; i++; } else q = false; }
      else field += c;
    } else if (c === '"') q = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field); field = "";
      if (row.some((x) => x !== "")) rows.push(row);
      row = [];
    } else field += c;
  }
  row.push(field);
  if (row.some((x) => x !== "")) rows.push(row);
  if (!rows.length) return [];
  const head = rows[0].map((h) => h.trim());
  return rows.slice(1).map((r) => Object.fromEntries(head.map((h, i) => [h, (r[i] ?? "").trim()])));
}
const csvCell = (v) => /[",\n]/.test(String(v ?? "")) ? `"${String(v).replace(/"/g, '""')}"` : String(v ?? "");

// TOTP (RFC 6238, SHA-1, 30 s, 6 digits) for the admin 2FA.
const B32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
function b32decode(s) {
  s = s.replace(/=+$/, "").replace(/\s/g, "").toUpperCase();
  let bits = "";
  for (const c of s) bits += B32.indexOf(c).toString(2).padStart(5, "0");
  const out = new Uint8Array(Math.floor(bits.length / 8));
  for (let i = 0; i < out.length; i++) out[i] = parseInt(bits.slice(i * 8, i * 8 + 8), 2);
  return out;
}
const newTotpSecret = () => randomFrom(B32, 32);
async function totpAt(secret, step) {
  const msg = new Uint8Array(8);
  let x = step;
  for (let i = 7; i >= 0; i--) { msg[i] = x & 0xff; x = Math.floor(x / 256); }
  const h = await hmacHex(b32decode(secret), msg, "SHA-1");
  const b = h.match(/../g).map((p) => parseInt(p, 16));
  const o = b[19] & 0xf;
  const n = ((b[o] & 0x7f) << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3];
  return String(n % 1000000).padStart(6, "0");
}
async function totpOk(secret, code, t = Date.now()) {
  const step = Math.floor(t / 30000);
  for (const d of [-1, 0, 1]) if (timingSafeEq(await totpAt(secret, step + d), String(code).trim())) return true;
  return false;
}

// Password hashing for the admin: PBKDF2-SHA256, 100k rounds (Workers WebCrypto limit).
async function pwHash(password, saltB64) {
  const salt = saltB64 || randomToken(16);
  const k = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt: enc.encode(salt), iterations: 100000 }, k, 256);
  return `pbkdf2$${salt}$${hex(bits)}`;
}
async function pwCheck(password, stored) {
  const [, salt] = String(stored || "").split("$");
  if (!salt) return false;
  return timingSafeEq(await pwHash(password, salt), stored);
}
