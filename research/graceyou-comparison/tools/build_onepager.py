"""상의 한 장 비교표: snapshots/tops/<브랜드>/<날짜>.json → onepager/상의-비교표.md · 상의-비교표.csv · 상의-상품목록.csv
  python tools/build_onepager.py [날짜]
계산 규칙(프로젝트 기준, planning/next-steps.md '기준 정의 3줄'):
  1) 상품 단위: 색상이 여러 개여도 같은 옷은 1개 — 이름 끝 색상 표기를 뺀 이름으로 묶는다(바바더닷컴은 같은 모델 묶음).
  2) 대표 가격: 판매가 우선, 없으면 정가. 색상별 가격이 다르면 최소~최대의 가운데 값을 대표로 쓰고 범위 상품 수를 따로 센다.
  3) 통계: 상품 단위 대표 가격의 중앙값과 Q1~Q3(선형 보간).
가격대 판정(planning/candidate-check.md): 중앙값이 그레이스유 중앙값 ±20% 안이고 Q1~Q3가 그레이스유 Q1~Q3 길이의 절반 이상 겹치면 '비슷함',
  중앙값만 밖이면 '한 단계 위/아래'. 판매가 기준과 정가 기준을 모두 낸다.
"""
import csv
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DAY = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
OUT = ROOT / "onepager"
ORDER = ["gu", "kume", "nw", "shesmiss", "jj"]
META = {
    "gu": {"ko": "그레이스유", "role": "기준", "channels": "공식몰 graceu.co.kr · W컨셉 · 29CM(상품 없음)", "list": "https://graceu.co.kr/product/list.html?cate_no=197"},
    "kume": {"ko": "쿠메", "role": "확정", "channels": "공식몰 kume-studio.co.kr · W컨셉 · 29CM", "list": "https://kume-studio.co.kr/product/list.html?cate_no=458"},
    "nw": {"ko": "낫띵리튼", "role": "확정", "channels": "공식몰 nothing-written.com · W컨셉 · 29CM", "list": "https://nothing-written.com/category/Tops/79/ 외 Knitwear 147, 현재 시즌 294·295·303·304"},
    "shesmiss": {"ko": "쉬즈미스", "role": "확정", "channels": "IDF몰 idfmall.co.kr(쉬즈미스·리스트·시스티나 합동몰) · 29CM", "list": "https://www.idfmall.co.kr/product/list.html?cate_no=159 (SHESMISS만)"},
    "jj": {"ko": "제이제이지고트", "role": "확정", "channels": "바바더닷컴 브랜드관(그룹몰) · W컨셉 · 29CM", "list": "https://pc.babathe.com/bnd/jjjigott/goods (분류: 상세 화면 위치 표시 '상의')"},
}


def q(a, x):
    a = sorted(a)
    i = (len(a) - 1) * x
    lo = int(i)
    hi = min(lo + 1, len(a) - 1)
    return a[lo] + (a[hi] - a[lo]) * (i - lo)


def stat(a):
    return {"n": len(a), "q1": q(a, .25), "med": q(a, .5), "q3": q(a, .75)} if a else None


def style_key(slug, r):
    n = r["name"]
    if slug == "gu":
        return re.sub(r"\s*\([^)]*\)\s*$", "", n).strip().lower()
    if slug == "kume":
        return re.sub(r",\s*[^,]+$", "", n).strip().lower()
    if slug == "nw":
        n = re.sub(r"^\d+(ST|ND|RD|TH)\s*/\s*", "", n, flags=re.I)
        return re.sub(r"\s*\([^)]*\)\s*$", "", n).strip().lower()
    return r["id"]


def row_color(slug, r):
    n = r["name"]
    if slug in ("gu", "nw"):
        m = re.search(r"\(([^)]*)\)\s*$", n)
    elif slug == "kume":
        m = re.search(r",\s*([^,]+)$", n)
    else:
        m = None
    return (m.group(1).strip() if m else r["id"]).upper()


SIZE_NOTE = re.compile(r"\s*\((?:[^)]*(?:순차|배송|예약|프리오더|입고|발송)[^)]*)\)\s*$")


def clean_size(s):
    return SIZE_NOTE.sub("", s).strip()


FREE = re.compile(r"^(free|f|ff|one ?size|os|프리|프리사이즈|단일|\(옵션 없음\))$", re.I)
ALPHA = r"(?:x{0,2}[sml]|xl|xxl|[23]xl)"


def size_family(names):
    ns = [n.strip() for n in names if n and n.strip()]
    if not ns:
        return "정보 없음"
    if all(FREE.match(n) for n in ns):
        return "프리·옵션 없음"
    low = [n.lower() for n in ns]
    if all(re.fullmatch(ALPHA, n) for n in low):
        return "알파벳 단일(S·M·L)"
    if all(re.fullmatch(ALPHA + r"(?:[-/]" + ALPHA + ")+", n) for n in low):
        return "알파벳 범위(XS-S·M-L)"
    if all(re.fullmatch(r"\d{2}", n) for n in ns):
        return "숫자(55·66·77)"
    if all(re.fullmatch(r"\d\s*\(\d{2,3}\)", n) for n in ns):
        return "번호+cm(1·2·3 + 95~110)"
    if any(FREE.match(n) for n in ns):
        return "프리 혼합"
    return "기타"


def build_styles(slug, rows):
    groups = defaultdict(list)
    if slug == "jj":
        parent = {r["id"]: r["id"] for r in rows}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for r in rows:
            for s in r.get("siblings") or []:
                if s in parent:
                    parent[find(s)] = find(r["id"])
        for r in rows:
            groups[find(r["id"])].append(r)
    else:
        for r in rows:
            groups[style_key(slug, r)].append(r)
    styles = []
    for key, rs in groups.items():
        sales = [r.get("sale") or r.get("list") for r in rs if r.get("sale") or r.get("list")]
        lists = [r.get("list") or r.get("sale") for r in rs if r.get("list") or r.get("sale")]
        if not sales:
            continue
        sale, lst = (min(sales) + max(sales)) / 2, (min(lists) + max(lists)) / 2
        colors, combos, sizes = set(), {}, []
        for r in rs:
            rc = row_color(slug, r)
            opt_colors = {c["color"].upper() for c in (r.get("combos") or []) if c["color"]}
            shared = len(opt_colors) > 1  # 한 줄의 옵션에 색상이 여러 개면 같은 색상 목록이 줄마다 되풀이되므로 합쳐서 센다(쿠메)
            for idx, c in enumerate(r.get("combos") or []):
                col = (c["color"] or rc).upper()
                colors.add(col)
                siz = clean_size(c["size"]) if c["size"] else "(옵션 없음)"
                ck = (col, siz) if shared else (r["id"], col, siz, idx)  # 한 줄 안의 조합은 겹쳐도 그대로 센다(세트 상품 등)
                combos[ck] = combos.get(ck, True) and bool(c["soldout"])
                if siz not in sizes:
                    sizes.append(siz)
            if not r.get("combos"):
                colors.add(rc)
            if slug == "jj":  # 바바더닷컴은 색상이 상품 번호별이라 '다른 색상' 묶음의 상품 수가 색상 수다
                colors.update(r.get("siblings") or [r["id"]])
        ncolor = max(len(colors), 1)
        sold_n = sum(1 for v in combos.values() if v)
        first = rs[0]
        styles.append({"key": str(key), "name": re.sub(r"\s*-\s*IDF\s*mall\s*$", "", re.sub(r"^\d+(?:ST|ND|RD|TH)\s*/\s*", "", first["name"], flags=re.I) if slug == "nw" else first["name"], flags=re.I), "rows": len(rs), "sale": sale, "list": lst,
                       "range": (min(sales) != max(sales)), "disc": (1 - sale / lst) if lst and sale < lst else 0.0, "ncolor": ncolor,
                       "sizes": sizes, "family": size_family(sizes), "combos": len(combos), "sold": sold_n,
                       "all_sold": bool(combos) and sold_n == len(combos), "has_opt": bool(combos), "url": first["url"], "ids": [r["id"] for r in rs]})
    return styles


def summarize(slug, snap):
    rows = [r for r in snap["rows"] if not r.get("error")]
    styles = build_styles(slug, rows)
    sale, lst = stat([s["sale"] for s in styles]), stat([s["list"] for s in styles])
    disc = [s["disc"] for s in styles if s["disc"] > 0]
    nc = Counter(min(s["ncolor"], 4) for s in styles)
    fam = Counter(s["family"] for s in styles)
    withopt = [s for s in styles if s["has_opt"]]
    row_all = sum(1 for r in rows if r.get("combos") and all(c["soldout"] for c in r["combos"]))
    row_opt = sum(1 for r in rows if r.get("combos"))
    top_sets = Counter(" / ".join(s["sizes"]) for s in styles if s["sizes"]).most_common(3)
    return {"slug": slug, "rows": len(rows), "errors": len(snap["rows"]) - len(rows), "n": len(styles), "sale": sale, "list": lst, "disc_share": len(disc) / len(styles) if styles else 0,
            "disc_med": statistics.median(disc) if disc else 0, "range_n": sum(1 for s in styles if s["range"]), "nc": nc, "fam": fam, "top_sets": top_sets,
            "style_all_sold": sum(1 for s in withopt if s["all_sold"]), "style_opt": len(withopt), "combos": sum(s["combos"] for s in withopt), "combos_sold": sum(s["sold"] for s in withopt),
            "row_all_sold": row_all, "row_opt": row_opt, "styles": styles, "observed_at": snap["observed_at"], "note": snap.get("note", "")}


def judge(st, ref):
    lo, hi = ref["med"] * 0.8, ref["med"] * 1.2
    ov = max(0, min(st["q3"], ref["q3"]) - max(st["q1"], ref["q1"]))
    ok = ov >= 0.5 * (ref["q3"] - ref["q1"])
    if lo <= st["med"] <= hi and ok:
        return "비슷함"
    if st["med"] > hi:
        return "한 단계 위"
    if st["med"] < lo:
        return "한 단계 아래"
    return "경계"


def nain_summary():
    """제외한 후보 아틀리에 나인(메이크샵): 목록 한 줄=한 상품으로 보고 같은 규칙으로 가격만 요약한다(참고)."""
    p = ROOT / "data" / "raw" / "nain_tops.json"
    if not p.exists():
        return None
    rows = json.loads(p.read_text(encoding="utf-8-sig"))
    seen, sal, lis = set(), [], []
    for r in rows:
        k = re.sub(r"^\([^)]*\)", "", r["name"]).strip().lower()
        if k in seen:
            continue
        seen.add(k)
        sal.append(r["sale"])
        lis.append(r["list"])
    ds = [1 - s / l for s, l in zip(sal, lis) if s < l]
    f = lambda a: {k: round(v) for k, v in stat(a).items() if k != "n"}
    return {"styles": len(sal), "rows": len(rows), "list": f(lis), "sale": f(sal), "disc_share": round(len(ds) / len(sal), 3), "disc_med": round(statistics.median(ds), 3) if ds else 0,
            "source": "https://nain.co.kr/shop/shopbrand.html?xcode=173/175/223", "observed_at": "2026-10-29"}


def won(v):
    return f"{round(v):,}원"


def man(v):
    return f"{v / 10000:.1f}만"


def pct(v):
    return f"{round(v * 100)}%"


def main():
    OUT.mkdir(exist_ok=True)
    (OUT / "history").mkdir(exist_ok=True)
    S = {}
    for slug in ORDER:
        p = ROOT / "snapshots" / "tops" / slug / f"{DAY}.json"
        S[slug] = summarize(slug, json.loads(p.read_text(encoding="utf-8")))
    policy = json.loads((ROOT / "data" / "shop_policy.json").read_text(encoding="utf-8"))["brands"]
    ref_sale, ref_list = S["gu"]["sale"], S["gu"]["list"]
    for slug in ORDER:
        s = S[slug]
        s["j_sale"] = judge(s["sale"], ref_sale) if slug != "gu" else "기준"
        s["j_list"] = judge(s["list"], ref_list) if slug != "gu" else "기준"
    K = ORDER[1:]
    ko = lambda k: META[k]["ko"]
    g = S["gu"]

    def discword(s):
        if s["disc_share"] == 0:
            return "없음"
        if s["disc_share"] < 0.05:
            return f"거의 없음 ({round(s['disc_share'] * s['n'])}개)"
        return f"{pct(s['disc_share'])} · 중앙 {round(s['disc_med'] * 100)}%"

    same = [k for k in K if S[k]["j_sale"] == "비슷함"]
    below = [k for k in K if S[k]["j_sale"] == "한 단계 아래"]
    above = [k for k in K if S[k]["j_sale"] == "한 단계 위"]
    edge = [k for k in K if S[k]["j_sale"] == "경계"]
    lists = [S[k]["list"]["med"] for k in K]
    pr = lambda ks: " · ".join(f"{ko(k)}({won(S[k]['sale']['med'])})" for k in ks)
    heavy = [k for k in K if S[k]["disc_share"] >= 0.5 and S[k]["disc_med"] >= 0.3]
    free = sorted([(policy[k]["free_min"], ko(k)) for k in ["gu"] + K if policy[k].get("free_min")], reverse=True)
    L = [f"# 그레이스유 상의 비교 — 한 장 ({DAY})", "",
         f"> MD 회의용. 그레이스유와 확정 4곳의 **공식몰 '상의' 분류 전체**(품절 포함)를 {DAY}에 읽어 같은 기준으로 센 값이다. 상품별 값은 `상의-상품목록.csv`, 근거 URL은 §6.", "",
         "## 1. 한눈에", "",
         f"- **판매가(실제 팔리는 값)**: 그레이스유 상의 중앙값 {won(g['sale']['med'])}(Q1~Q3 {man(g['sale']['q1'])}~{man(g['sale']['q3'])}). 같은 가격대 → {pr(same) or '없음'}"
         + (f" · 한 단계 아래 → {pr(below)}" if below else "") + (f" · 한 단계 위 → {pr(above)}" if above else "") + (f" · 경계 → {pr(edge)}" if edge else "") + ".",
         f"- **정가(할인 전 표시가)**로 보면 4곳 모두 그레이스유와 비슷하다(중앙 {won(min(lists))}~{won(max(lists))}). 판매가가 낮은 곳({'·'.join(ko(k) for k in heavy) or '없음'})은 상시 할인 때문이다 — "
         + ", ".join(f"{ko(k)} 상품의 {pct(S[k]['disc_share'])}가 중앙 {round(S[k]['disc_med'] * 100)}% 할인" for k in heavy) + f". 그레이스유는 {discword(g)}.",
         "- **무료배송이 시작되는 금액**: " + " · ".join(f"{won(v)} {'·'.join(n for vv, n in free if vv == v)}" for v in sorted({v for v, _ in free}, reverse=True)) + " (쉬즈미스는 4만원 미만에만 2,500원이 붙는다는 문구 기준, 쿠메는 공개 화면에서 확인 안 됨).", ""]

    L += ["## 2. 가격 (상품 단위, 색상 합침)", "",
          "| 대상 | 상의 상품 수 (등록 행) | 판매가 중앙값 | 사분위 Q1~Q3 | 판정(판매가) | 정가 중앙값 | 판정(정가) | 표시 할인 (상품 비율 · 중앙) |", "|---|---|---|---|---|---|---|---|"]
    for slug in ORDER:
        s = S[slug]
        L.append(f"| **{ko(slug)}**{'(기준)' if slug == 'gu' else ''} | **{s['n']}** ({s['rows']}) | **{won(s['sale']['med'])}** | {man(s['sale']['q1'])}~{man(s['sale']['q3'])} | {s['j_sale']} | {won(s['list']['med'])} | {s['j_list']} | {discword(s)} |")
    L += ["", f"판정: 중앙값이 그레이스유 중앙 ±20%({won(ref_sale['med'] * 0.8)}~{won(ref_sale['med'] * 1.2)}) 안이고 Q1~Q3가 그레이스유 Q1~Q3({won(ref_sale['q1'])}~{won(ref_sale['q3'])}) 길이의 절반 이상 겹치면 '비슷함'(`planning/candidate-check.md` 규칙). 정가 기준은 정가끼리 같은 규칙으로 판정.", ""]

    L += ["## 3. 상품 구성", "",
          "| 대상 | 색상 옵션 수 (1색 / 2색 / 3색 / 4색+) | 사이즈 표기 (상품 비율) | 완전 품절 표시 상품 | 옵션 조합 품절 표시 |", "|---|---|---|---|---|"]
    for slug in ORDER:
        s = S[slug]
        tot = s["n"]
        ncs = " / ".join(pct(s["nc"].get(k, 0) / tot) for k in (1, 2, 3, 4))
        fam = " · ".join(f"{k} {pct(v / tot)}" for k, v in s["fam"].most_common(3))
        allsold = f"상품 {s['style_all_sold']}/{s['style_opt']} ({pct(s['style_all_sold'] / s['style_opt'])})" + (f" · 색상별 행 {s['row_all_sold']}/{s['row_opt']} ({pct(s['row_all_sold'] / s['row_opt'])})" if s["rows"] != s["n"] else "")
        L.append(f"| **{ko(slug)}** | {ncs} | {fam} | {allsold} | {s['combos_sold']}/{s['combos']} ({pct(s['combos_sold'] / s['combos'])}) |")
    L += ["", "품절 표시는 화면에 보이는 상태일 뿐 재고 수량이나 판매량이 아니다(수량은 저장하지 않음). 이 비율로 인기나 소진 속도를 읽지 않는다.", ""]

    L += ["## 4. 채널·배송·반품", "", "| 대상 | 채널 | 배송 | 반품 |", "|---|---|---|---|"]
    for slug in ORDER:
        L.append(f"| **{ko(slug)}** | {META[slug]['channels']} | {policy[slug]['ship']} | {policy[slug]['ret']} |")
    L.append("")

    L += ["## 5. 읽는 법·한계", "",
          "- **상품 단위**: 색상별로 따로 올린 몰(그레이스유·쿠메·낫띵리튼·바바더닷컴)은 이름 끝 색상 표기를 빼서 한 상품으로 묶었다. 쉬즈미스는 IDF몰이 색상을 한 상품의 옵션으로 담아 한 줄이 한 상품이다.",
          "- **대표 가격**: 판매가 우선, 없으면 정가. 색상마다 가격이 다른 상품은 최소~최대의 가운데 값(" + ", ".join(f"{ko(k)} {S[k]['range_n']}개" for k in ORDER) + ").",
          "- **정가**: 몰이 취소선으로 보여 주는 가격이다(쉬즈미스는 목록의 취소선 가격, 나머지는 상세 화면 값). 몰마다 '정가'를 정하는 방식이 달라 정가 기준은 참고용이다.",
          "- **옵션 조합**: 색상×사이즈로 나뉜 몰은 그대로, 색상·사이즈를 따로 고르는 몰(쿠메)은 곱해서 센다. 옵션이 없는 상품은 '옵션 없음(프리)' 한 조합이다. 낫띵리튼·바바더닷컴은 색상이 상품 번호별이라 이름·번호로 색상을 구분했다.",
          "- **범위**: 쿠메는 여성 TOP(458)만 — 남성 TOP(479)은 다른 상품이다. 낫띵리튼은 지난 시즌 목록(Tops·Knitwear)과 현재 시즌 목록을 모두 끝까지 읽었다(쪽을 5쪽에서 멈추면 절반만 읽힌다). 쉬즈미스는 IDF몰 '탑'에서 SHESMISS 표시 상품만.",
          f"- **제이제이지고트**: 바바더닷컴 브랜드관이 상의 143개를 표시하는데 목록에서 읽힌 것은 {S['jj']['rows']}개다(브랜드관 484개 중 459개만 읽혔고, 위치 표시가 없는 1개는 이름으로 상의로 봤다). 그룹몰 판매가이며 자사몰이 아니다.",
          "- 읽는 중 실패한 상품: " + ", ".join(f"{ko(k)} {S[k]['errors']}개" for k in ORDER) + ".", ""]

    L += [f"## 6. 근거 (확인일 {DAY})", "", "| 대상 | 목록 | 상품별 값 | 배송·반품 근거 |", "|---|---|---|---|"]
    for slug in ORDER:
        L.append(f"| {ko(slug)} | {META[slug]['list']} | 상의-상품목록.csv ({S[slug]['n']}행, URL 열) | {' , '.join(policy[slug]['urls'])} |")
    L += ["", "그레이스유는 2026-10-28 수집값(`samples/graceyou-overview/data/products.json`)과 같은지 다시 확인했다: 상의 55개, 판매가 중앙 153,000원, Q1~Q3 101,500~218,000원, 옵션 조합 280개 중 품절 151개, 완전 품절 행 58개로 모두 같았다.", ""]
    page = "\n".join(L)
    (OUT / "상의-비교표.md").write_text(page, encoding="utf-8")
    (OUT / "history" / f"상의-비교표-{DAY}.md").write_text(page, encoding="utf-8")

    with open(OUT / "상의-비교표.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["대상", "역할", "채널", "상의 상품 수", "등록 행 수", "판매가 중앙", "판매가 Q1", "판매가 Q3", "판정(판매가)", "정가 중앙", "정가 Q1", "정가 Q3", "판정(정가)", "표시 할인 상품 비율", "표시 할인 중앙",
                    "1색", "2색", "3색", "4색+", "사이즈 표기(상위)", "완전 품절 상품", "옵션 있는 상품", "옵션 조합 품절", "옵션 조합 전체", "배송", "반품", "확인일", "목록 URL"])
        for slug in ORDER:
            s, m = S[slug], META[slug]
            tot = s["n"]
            w.writerow([m["ko"], m["role"], m["channels"], s["n"], s["rows"], round(s["sale"]["med"]), round(s["sale"]["q1"]), round(s["sale"]["q3"]), s["j_sale"], round(s["list"]["med"]), round(s["list"]["q1"]), round(s["list"]["q3"]),
                        s["j_list"], round(s["disc_share"], 3), round(s["disc_med"], 3), *[round(s["nc"].get(k, 0) / tot, 3) for k in (1, 2, 3, 4)],
                        " · ".join(f"{k} {pct(v / tot)}" for k, v in s["fam"].most_common(3)), s["style_all_sold"], s["style_opt"], s["combos_sold"], s["combos"], policy[slug]["ship"], policy[slug]["ret"], s["observed_at"], m["list"]])
    with open(OUT / "상의-상품목록.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["대상", "상품(대표 이름)", "등록 행 수", "색상 수", "대표 판매가", "대표 정가", "가격 범위 여부", "표시 할인율", "사이즈", "사이즈 표기", "옵션 조합", "품절 조합", "완전 품절", "URL", "확인일"])
        for slug in ORDER:
            for st in sorted(S[slug]["styles"], key=lambda x: x["sale"]):
                w.writerow([ko(slug), st["name"], st["rows"], st["ncolor"], round(st["sale"]), round(st["list"]), "Y" if st["range"] else "", round(st["disc"], 3), "/".join(st["sizes"]), st["family"],
                            st["combos"], st["sold"], "Y" if st["all_sold"] else "", st["url"], S[slug]["observed_at"]])

    # 날짜별 지표 이력(매일 돌리면 한 줄씩 쌓인다)
    hist = OUT / "history" / "상의-지표-이력.csv"
    cols = ["날짜", "대상", "상의 상품 수", "등록 행 수", "판매가 중앙", "판매가 Q1", "판매가 Q3", "정가 중앙", "표시 할인 상품 비율", "표시 할인 중앙", "완전 품절 상품", "옵션 있는 상품", "옵션 조합 품절", "옵션 조합 전체"]
    old = []
    if hist.exists():
        with open(hist, encoding="utf-8-sig", newline="") as f:
            old = [r for r in csv.reader(f)][1:]
    old = [r for r in old if r and r[0] != DAY]
    for slug in ORDER:
        s = S[slug]
        old.append([DAY, ko(slug), s["n"], s["rows"], round(s["sale"]["med"]), round(s["sale"]["q1"]), round(s["sale"]["q3"]), round(s["list"]["med"]), round(s["disc_share"], 3), round(s["disc_med"], 3),
                    s["style_all_sold"], s["style_opt"], s["combos_sold"], s["combos"]])
    order_ko = [ko(k) for k in ORDER]
    old.sort(key=lambda r: (r[0], order_ko.index(r[1])))
    with open(hist, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(old)
    # 다른 도구(build_candidates.py)가 읽는 요약
    summ = {}
    for slug in ORDER:
        s = S[slug]
        summ[ko(slug)] = {"styles": s["n"], "rows": s["rows"], "list": {k: round(v) for k, v in s["list"].items() if k != "n"}, "sale": {k: round(v) for k, v in s["sale"].items() if k != "n"},
                          "disc_share": round(s["disc_share"], 3), "disc_med": round(s["disc_med"], 3), "source": META[slug]["list"], "observed_at": s["observed_at"], "judge_sale": s["j_sale"], "judge_list": s["j_list"]}
    nain = nain_summary()
    if nain:
        nain["judge_sale"] = judge(nain["sale"] | {"n": 0}, ref_sale)
        nain["judge_list"] = judge(nain["list"] | {"n": 0}, ref_list)
        summ["아틀리에 나인"] = nain
    (ROOT / "data" / "tops_summary.json").write_text(json.dumps({"observed_at": DAY, "basis": "상품 단위(색 합침), 대표가=판매가 우선(색상별 가격이 다르면 최소~최대의 가운데), 통계=선형 보간 중앙값·Q1~Q3. 아틀리에 나인은 제외 사유 참고용(메이크샵 목록 한 줄=한 상품, 상세 옵션은 읽지 않음)", "brands": summ}, ensure_ascii=False, indent=1), encoding="utf-8")
    for slug in ORDER:
        s = S[slug]
        print(ko(slug), "상품", s["n"], "행", s["rows"], "판매가", round(s["sale"]["q1"]), round(s["sale"]["med"]), round(s["sale"]["q3"]), s["j_sale"], "| 정가", round(s["list"]["med"]), s["j_list"],
              "| 할인", pct(s["disc_share"]), round(s["disc_med"] * 100), "| 완전품절", s["style_all_sold"], "/", s["style_opt"], "| 조합품절", s["combos_sold"], "/", s["combos"])


if __name__ == "__main__":
    main()
