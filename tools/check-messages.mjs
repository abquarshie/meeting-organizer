// Checks the message files: every English message parses, every Dangme message that is filled in parses and uses the
// same {placeholders} as its English, and the Dangme file has exactly the English keys. Run: npm run check:messages
import { readFileSync } from "node:fs";
import { parse, TYPE } from "@formatjs/icu-messageformat-parser";

const read = (f) => JSON.parse(readFileSync(new URL(`../messages/${f}.json`, import.meta.url), "utf8"));
const flat = (o, p = "", out = {}) => {
  for (const [k, v] of Object.entries(o)) {
    const q = p ? `${p}.${k}` : k;
    if (typeof v === "string") out[q] = v; else flat(v, q, out);
  }
  return out;
};
const names = (ast, out = new Set()) => {
  for (const el of ast) {
    if (el.type === TYPE.argument || el.type === TYPE.number || el.type === TYPE.date || el.type === TYPE.plural || el.type === TYPE.select) out.add(el.value);
    if (el.type === TYPE.tag) { out.add(`<${el.value}>`); names(el.children, out); }
    if (el.options) for (const o of Object.values(el.options)) names(o.value, out);
  }
  return out;
};

const en = flat(read("en"));
const ada = flat(read("ada"));
const problems = [];
const enNames = {};
for (const [k, v] of Object.entries(en)) {
  try { enNames[k] = names(parse(v)); } catch (e) { problems.push(`en ${k}: ${e.message}`); }
}
for (const k of Object.keys(en)) if (!(k in ada)) problems.push(`ada is missing ${k}`);
let filled = 0;
for (const [k, v] of Object.entries(ada)) {
  if (!(k in en)) { problems.push(`ada has ${k}, which English no longer has`); continue; }
  if (!v) continue;
  filled++;
  let got;
  try { got = names(parse(v)); } catch (e) { problems.push(`ada ${k}: ${e.message}`); continue; }
  const want = enNames[k] ?? new Set();
  const lost = [...want].filter((n) => !got.has(n));
  const extra = [...got].filter((n) => !want.has(n));
  if (lost.length) problems.push(`ada ${k}: leaves out ${lost.map((n) => `{${n}}`).join(", ")}`);
  if (extra.length) problems.push(`ada ${k}: has ${extra.map((n) => `{${n}}`).join(", ")}, which the English doesn't`);
}
console.log(`${Object.keys(en).length} messages, ${filled} translated into Dangme.`);
if (problems.length) { console.error(problems.join("\n")); process.exit(1); }
console.log("All messages are fine.");
