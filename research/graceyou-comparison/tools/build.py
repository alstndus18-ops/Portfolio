"""그레이스유와 비교할 브랜드 DB를 만든다: data/*.json → brands.csv · brands.xlsx · ranking.md.

점수는 '비슷한 정도'를 여러 축으로 따로 잰 뒤 합친다. 상품 수·옷 카테고리는 점수에 쓰지 않는다.
  가격 위치  : 정가 환산 중앙값이 그레이스유와 얼마나 가까운가 (로그 거리)
  가격대 겹침: 정가 환산 IQR(Q1~Q3)이 그레이스유 IQR과 겹치는 정도
  무드·정체성: 소개문에서 붙인 태그의 겹침 (가중 자카드)
실행: python tools/build.py   (openpyxl 필요)
"""
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
W = {"price": 0.30, "band": 0.20, "mood": 0.50}

meta = json.loads((D / "brand_meta.json").read_text(encoding="utf-8"))
G = meta["graceu"]
GP = G["price_uniq_all"]
GT = set(G["tags"])

rows = []
for f in sorted(D.glob("29cm_snapshots_*.json")):
    snap = json.loads(f.read_text(encoding="utf-8"))
    for b in snap["brands"]:
        rows.append((b, snap["observed_at"], f.name))


def est_factor(b):
    """29CM 화면가는 할인이 반영된 값이라, 상품 절반 이상이 할인 중이면 중앙 할인율로 정가를 되돌려 본다."""
    d = b["disc"]
    if d["n"] and d["n"] >= b["n"] * 0.5 and d["med"]:
        return 1 / (1 - d["med"] / 100)
    return 1.0


def overlap(a1, a2, b1, b2):
    lo, hi = max(a1, b1), min(a2, b2)
    inter = max(0, math.log(hi) - math.log(lo)) if hi > lo else 0
    union = math.log(max(a2, b2)) - math.log(min(a1, b1))
    return inter / union if union else 0


def mood(tags):
    s = set(tags)
    return len(s & GT) / len(s | GT) if s else 0


out = []
for b, obs, src in rows:
    m = meta["brands"][str(b["id"])]
    k = est_factor(b)
    med, q1, q3 = (round(b["p"][x] * k) for x in ("med", "q1", "q3"))
    price = max(0, 1 - abs(math.log(med / GP["med"])) / math.log(2.5))
    band = overlap(q1, q3, GP["q1"], GP["q3"])
    md = mood(m["tags"])
    score = W["price"] * price + W["band"] * band + W["mood"] * md
    out.append({
        "id": b["id"], "ko": b["ko"], "en": b["en"], "tier": m["tier"], "tags": m["tags"],
        "est": b.get("est"), "heart": b["heart"], "sub": b["sub"], "intro": b["intro"],
        "n": b["n"], "p": b["p"], "k": round(k, 2), "list_q1": q1, "list_med": med, "list_q3": q3,
        "disc_share": round(b["disc"]["n"] / b["n"], 2) if b["n"] else 0, "disc_med": b["disc"]["med"], "disc_max": b["disc"]["max"],
        "likes_med": b["likes"]["med"], "rev_total": b["rev"]["total"], "rate": b["rate"],
        "ship": b.get("ship", ""), "promo": " / ".join(b.get("promo", [])), "names": " | ".join(b.get("names", [])),
        "note": b.get("note", ""), "nonapparel": bool(m.get("nonapparel")), "reviewed": m["reviewed"],
        "s_price": round(price * 100), "s_band": round(band * 100), "s_mood": round(md * 100), "score": round(score * 100),
        "obs": obs, "url": f"https://www.29cm.co.kr/store/brand/{b['id']}",
    })

out.sort(key=lambda r: -r["score"])
for i, r in enumerate(out, 1):
    r["rank"] = i


def rank_by(key):
    order = sorted(out, key=lambda r: -r[key])
    return {r["id"]: i for i, r in enumerate(order, 1)}


rp, rb, rm = rank_by("s_price"), rank_by("s_band"), rank_by("s_mood")
for r in out:
    r["rank_price"], r["rank_mood"] = rp[r["id"]], rm[r["id"]]
    # 한 축만 빼도 안 흔들리는지: 가격 순위와 무드 순위가 모두 상위 절반이면 '두 축 모두 가까움'
    half = len(out) / 2
    r["both_axes"] = "Y" if rp[r["id"]] <= half and rm[r["id"]] <= half else ""

COLS = [
    ("rank", "종합순위"), ("ko", "브랜드"), ("en", "영문명"), ("tier", "구분"), ("score", "종합점수"),
    ("s_price", "가격위치점수"), ("s_band", "가격대겹침점수"), ("s_mood", "무드점수"), ("rank_price", "가격순위"), ("rank_mood", "무드순위"), ("both_axes", "두축모두상위"),
    ("tags", "무드태그"), ("sub", "한줄소개"), ("intro", "소개문"), ("est", "설립연도"), ("heart", "29CM좋아요수"),
    ("list_q1", "정가환산Q1"), ("list_med", "정가환산중앙값"), ("list_q3", "정가환산Q3"), ("k", "정가환산배수"),
    ("disc_share", "할인상품비율"), ("disc_med", "중앙할인율%"), ("disc_max", "최대할인율%"),
    ("likes_med", "상품좋아요중앙"), ("rev_total", "표본리뷰합"), ("rate", "평점"), ("ship", "배송조건"), ("promo", "쿠폰표시"),
    ("names", "상품명예"), ("n", "표본상품수"), ("note", "비고"), ("reviewed", "검토상태"), ("obs", "확인일"), ("url", "근거URL"),
]
P_COLS = [("min", "최저"), ("q1", "Q1"), ("med", "중앙"), ("q3", "Q3"), ("p90", "P90"), ("max", "최고"), ("mean", "평균")]


def flat(r):
    d = {k: (" ".join(r[k]) if k == "tags" else r[k]) for k, _ in COLS}
    for k, _ in P_COLS:
        d["p_" + k] = r["p"][k]
    return d


header = [h for _, h in COLS] + ["29CM화면가_" + h for _, h in P_COLS]
keys = [k for k, _ in COLS] + ["p_" + k for k, _ in P_COLS]
with open(ROOT / "brands.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(header)
    for r in out:
        d = flat(r)
        w.writerow([d[k] for k in keys])

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "브랜드비교"
    ws.append(header)
    for r in out:
        d = flat(r)
        ws.append([d[k] for k in keys])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="333333")
        c.alignment = Alignment(wrap_text=True, vertical="center")
    widths = {"소개문": 60, "한줄소개": 40, "상품명예": 40, "무드태그": 28, "근거URL": 36, "구분": 18}
    for i, h in enumerate(header, 1):
        ws.column_dimensions[get_column_letter(i)].width = widths.get(h, 11)
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions

    wg = wb.create_sheet("그레이스유 기준")
    wg.append(["항목", "값"])
    for k, v in [("무드태그(추정)", " ".join(GT)), ("기준 근거", G["basis"]), ("가격 기준", G["price_note"])]:
        wg.append([k, v])
    for name, st in (("전체", G["price_uniq_all"]), ("상의", G["price_uniq_top"])):
        for k, v in st.items():
            wg.append([f"가격({name}) {k}", v])
    wg.column_dimensions["A"].width = 22
    wg.column_dimensions["B"].width = 100

    wa = wb.create_sheet("점수 산식")
    for row in [
        ["축", "산식", "가중"],
        ["가격 위치", "정가 환산 중앙값과 그레이스유 전체 중앙값(213,000원)의 로그 거리. 2.5배 차이면 0점", W["price"]],
        ["가격대 겹침", "정가 환산 Q1~Q3 구간과 그레이스유 Q1~Q3(137,500~298,000원)의 로그 구간 겹침 비율", W["band"]],
        ["무드·정체성", "소개문에서 붙인 태그와 그레이스유 태그의 자카드 비율", W["mood"]],
        ["정가 환산", "상품 절반 이상이 할인 중이면 화면가 ÷ (1-중앙할인율). 아니면 화면가 그대로", ""],
        ["쓰지 않는 값", "상품 수, 옷 카테고리, 좋아요·리뷰 수는 점수에 넣지 않는다(맥락 정보로만 보관)", ""],
    ]:
        wa.append(row)
    wa.column_dimensions["A"].width = 16
    wa.column_dimensions["B"].width = 100
    wb.save(ROOT / "brands.xlsx")
    print("xlsx ok")
except ImportError:
    print("openpyxl 없음: xlsx 건너뜀")

(ROOT / "data" / "scored.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
lines = ["| 순위 | 브랜드 | 구분 | 종합 | 가격 | 겹침 | 무드 | 정가환산 중앙값 | 할인 | 두축 |", "|---|---|---|---|---|---|---|---|---|---|"]
for r in out:
    disc = f"{round(r['disc_share']*100)}%·{r['disc_med']}%" if r["disc_med"] else "-"
    lines.append(f"| {r['rank']} | {r['ko']} | {r['tier']} | {r['score']} | {r['s_price']} | {r['s_band']} | {r['s_mood']} | {r['list_med']:,} | {disc} | {r['both_axes']} |")
(D / "ranking_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(len(out), "brands")
for r in out:
    print(r["rank"], r["ko"], r["score"], r["s_price"], r["s_band"], r["s_mood"], r["list_med"], r["both_axes"])
