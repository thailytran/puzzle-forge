// Concatenate src/*.js (in name order) into dist/worker.js and inline schema.sql as SCHEMA_SQL.
// No bundler, no dependencies: the output is one ES module that can be pasted into the Cloudflare
// dashboard editor or uploaded with the Workers API / wrangler.
import { readFileSync, readdirSync, writeFileSync, mkdirSync } from "node:fs";
const here = new URL(".", import.meta.url).pathname;
const schema = readFileSync(here + "schema.sql", "utf8").split("\n").filter((l) => !l.startsWith("--")).join("\n");
const parts = readdirSync(here + "src").filter((f) => f.endsWith(".js")).sort().map((f) => readFileSync(here + "src/" + f, "utf8"));
const out = `// CaseVault Worker — built by apps/casevault_cf/build.mjs. Do not edit; edit src/ instead.\nconst SCHEMA_SQL = ${JSON.stringify(schema)};\n${parts.join("\n")}`;
mkdirSync(here + "dist", { recursive: true });
writeFileSync(here + "dist/worker.js", out);
console.log(`dist/worker.js ${out.length} bytes`);
