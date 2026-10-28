// 옵션 색마다 어떤 사진을 근거로 보이는지(label → match → lineup → representative) 몰별로 센다.
// color_photos.py를 돌린 뒤(또는 돌리기 전 현재 data.js로) 실행한다. Python 없이 Node만 있으면 된다.
//   node tools/evidence_report.mjs
// 데이터의 ev 값이 사진 파일(img·lineup)과 맞지 않거나, 몰 규칙(data/color-photo-rules.json)의 evidence 목록에 없는
// 단계를 쓰고 있거나, 사진 파일이 없으면 알려 준다.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const text = fs.readFileSync(path.join(root, "data.js"), "utf8");
const data = JSON.parse(text.slice(text.indexOf("{"), text.lastIndexOf("}") + 1));
const rules = JSON.parse(fs.readFileSync(path.join(root, "data", "color-photo-rules.json"), "utf8")).malls;

const STEPS = ["label", "match", "lineup", "representative"];
// 화면(evOf)·color_photos.py(evidence_of)와 같다: 저장된 ev가 있으면 그 값, 없으면 사진 파일로 정한다.
const derive = (o, p) => o.ev || (o.img ? "label" : p.lineup ? "lineup" : "representative");
const rows = {};
const problems = [];
let hasEv = 0;

for (const p of data.products) {
  const allowed = rules[p.mall]?.evidence || STEPS;
  const r = (rows[p.mall] ||= { products: 0, options: 0, label: 0, match: 0, lineup: 0, representative: 0 });
  r.products++;
  for (const o of p.opts) {
    if (!o.pal) continue;
    const ev = derive(o, p);
    r.options++;
    r[ev]++;
    if (o.ev !== undefined) hasEv++;
    if (!STEPS.includes(ev)) problems.push(`${p.id}/${o.name}: 알 수 없는 단계 ${ev}`);
    if ((ev === "label" || ev === "match") && !o.img) problems.push(`${p.id}/${o.name}: ${ev}인데 사진 없음`);
    if (!allowed.includes(ev) && ev !== "representative") problems.push(`${p.id}/${o.name}: ${p.mall} 규칙에 없는 단계 ${ev}를 씀`);
    if (o.img && !fs.existsSync(path.join(root, o.img))) problems.push(`${p.id}/${o.name}: 사진 파일 없음 ${o.img}`);
  }
  if (p.lineup && !fs.existsSync(path.join(root, p.lineup))) problems.push(`${p.id}: 모음 사진 파일 없음 ${p.lineup}`);
}

const pct = (a, b) => (b ? `${Math.round((a / b) * 100)}%` : "-");
console.log(`data.js ${data.asOf} · ev 값이 적힌 옵션 ${hasEv}개${hasEv ? "" : " (아직 새 코드로 돌리지 않음, 사진 파일로 계산)"}`);
console.log("몰".padEnd(8), "상품", "옵션색", "label", "match", "lineup", "대표사진", "| 그 색 사진이 있는 비율(label+match)");
const tot = { options: 0, label: 0, match: 0, lineup: 0, representative: 0 };
for (const [m, r] of Object.entries(rows)) {
  console.log(m.padEnd(8), String(r.products).padStart(4), String(r.options).padStart(5), String(r.label).padStart(6), String(r.match).padStart(6), String(r.lineup).padStart(6), String(r.representative).padStart(7), "|", pct(r.label + r.match, r.options));
  for (const k of Object.keys(tot)) tot[k] += r[k];
}
console.log("합계".padEnd(8), "".padStart(4), String(tot.options).padStart(5), String(tot.label).padStart(6), String(tot.match).padStart(6), String(tot.lineup).padStart(6), String(tot.representative).padStart(7), "|", pct(tot.label + tot.match, tot.options));
if (problems.length) {
  console.log(`\n문제 ${problems.length}건`);
  problems.slice(0, 20).forEach((x) => console.log(" -", x));
  process.exitCode = 1;
} else console.log("\n문제 없음");
