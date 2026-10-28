"""공식몰에서 읽은 상의 목록(data/raw)을 브랜드별 가격 분포로 요약한다 → data/official_tops.json.
  python tools/official_tops.py
같은 상품의 색 옵션이 따로 나열된 곳은 색을 뺀 이름으로 합쳐 '스타일' 수를 센다(그레이스유 기준과 같은 방식).
"""
import json
import re
import statistics
from pathlib import Path

D = Path(__file__).resolve().parent.parent / "data"
R = D / "raw"


def load(name):
    return json.loads((R / name).read_text(encoding="utf-8-sig"))


def q(a, x):
    a = sorted(a)
    i = (len(a) - 1) * x
    lo = int(i)
    hi = min(lo + 1, len(a) - 1)
    return round(a[lo] + (a[hi] - a[lo]) * (i - lo))


def stat(a):
    return {"n": len(a), "min": min(a), "q1": q(a, .25), "med": q(a, .5), "q3": q(a, .75), "p90": q(a, .9), "max": max(a), "mean": round(statistics.mean(a))}


def styles(items, keyf):
    """키가 같은 항목은 한 스타일로 본다(처음 나온 값)."""
    seen = {}
    for it in items:
        seen.setdefault(keyf(it), it)
    return list(seen.values())


def summarize(items, keyf):
    s = styles(items, keyf)
    lst = [i["list"] for i in s]
    sale = [i["sale"] for i in s]
    d = [round((1 - i["sale"] / i["list"]) * 100) for i in s if i["sale"] < i["list"]]
    return {"rows": len(items), "styles": len(s), "list": stat(lst), "sale": stat(sale), "disc_share": round(len(d) / len(s), 2),
            "disc_med": q(d, .5) if d else None, "disc_max": max(d) if d else None}


out = {}

# 쿠메: 카페24 TOP 하위 3개 목록. 이름 끝 ", 색" 제거
kume = []
for c in (459, 460, 461):
    kume += load(f"kume_cate{c}.json")
out["쿠메"] = summarize(kume, lambda i: re.sub(r",\s*[^,]+$", "", i["name"]).lower())
out["쿠메"]["source"] = "https://kume-studio.co.kr/product/list.html?cate_no=459/460/461 (SWEATER·BLOUSE&SHIRT·T-SHIRT&MTM)"

# 낫띵리튼: 브라우저로 읽은 텍스트. 팬츠·스커트 제외, '2ND / ' 같은 차수 표기와 (색) 제거
nw = []
for line in (R / "nothing-written_tops_2026-10-29.txt").read_text(encoding="utf-8").splitlines():
    if line.startswith("#") or "|" not in line:
        continue
    name, price = line.rsplit("|", 1)
    if re.search(r"pants|skirt", name, re.I):
        continue
    nw.append({"name": name, "list": int(price), "sale": int(price)})
key_nw = lambda i: re.sub(r"\s*\([^)]*\)\s*$", "", re.sub(r"^\d+(ST|ND|RD|TH)\s*/\s*", "", i["name"], flags=re.I)).strip().lower()
out["낫띵리튼"] = summarize(nw, key_nw)
out["낫띵리튼"]["source"] = "https://nothing-written.com/category/Knitwear/147, /category/Tops/79 (각 5쪽)"

# 아틀리에 나인: 메이크샵 3개 목록(셔츠/블라우스·니트/가디건·티셔츠)
nain = load("nain_tops.json")
out["아틀리에 나인"] = summarize(nain, lambda i: re.sub(r"^\([^)]*\)", "", i["name"]).strip().lower())
out["아틀리에 나인"]["source"] = "https://nain.co.kr/shop/shopbrand.html?xcode=173/175/223"

# 쉬즈미스: IDF몰 탑(159) 목록 중 SHESMISS
idf = [i for i in load("idfmall_cate159.json") if i["brand"] == "SHESMISS"]
out["쉬즈미스"] = summarize(idf, lambda i: i["no"])
out["쉬즈미스"]["source"] = "https://www.idfmall.co.kr/product/list.html?cate_no=159 (브랜드 SHESMISS만)"

# 제이제이지고트: 바바더닷컴 브랜드관 요약(브라우저 스크롤 값)
jj = load("jjjigott_babathe_2026-10-29.json")["tops"]
out["제이제이지고트"] = {"rows": jj["n"], "styles": jj["n"], "list": jj["list"], "sale": jj["sale"], "disc_share": jj["disc_share"], "disc_med": jj["disc"]["med"], "disc_max": jj["disc"]["max"],
                   "source": "https://pc.babathe.com/bnd/jjjigott/goods (전체 484 중 이름 키워드로 가른 상의 150)"}

(D / "official_tops.json").write_text(json.dumps({"observed_at": "2026-10-29", "unit": "원, 스타일(색 옵션 합침) 기준", "brands": out}, ensure_ascii=False, indent=1), encoding="utf-8")
for k, v in out.items():
    print(k, v["styles"], "정가 중앙", v["list"]["med"], "Q1~Q3", v["list"]["q1"], v["list"]["q3"], "| 판매가 중앙", v["sale"]["med"], "| 할인비율", v["disc_share"], v["disc_med"])


# ---- 니트류만 따로: 상의 전체는 티셔츠 같은 저가 품목이 섞여 브랜드마다 구성이 달라 비교가 흔들린다
KNIT = re.compile(r"니트|가디건|풀오버|knit|cardigan|pullover|sweater", re.I)
guf = json.loads((D.parent.parent.parent / "samples" / "graceyou-overview" / "data" / "products.json").read_text(encoding="utf-8"))
guf = guf if isinstance(guf, list) else guf["products"]
gk = styles([{"name": p["name"], "list": p["price"], "sale": p.get("sale") or p["price"]} for p in guf if KNIT.search(p["name"])],
            lambda i: re.sub(r"\s*\([^)]*\)\s*$", "", i["name"]).lower())
base = {"그레이스유(공식몰)": {"styles": len(gk), "list": stat([i["list"] for i in gk])}}
srcs = {"쿠메": (kume, lambda i: re.sub(r",\s*[^,]+$", "", i["name"]).lower()), "낫띵리튼": (nw, key_nw),
        "아틀리에 나인": (nain, lambda i: re.sub(r"^\([^)]*\)", "", i["name"]).strip().lower()), "쉬즈미스": (idf, lambda i: i["no"])}
for k, (items, kf) in srcs.items():
    sel = [i for i in items if KNIT.search(i["name"])]
    if sel:
        s = summarize(sel, kf)
        out[k]["knit"] = {"styles": s["styles"], "list": s["list"], "sale": s["sale"], "disc_share": s["disc_share"], "disc_med": s["disc_med"]}
out["_graceu_knit"] = base["그레이스유(공식몰)"]
(D / "official_tops.json").write_text(json.dumps({"observed_at": "2026-10-29", "unit": "원, 스타일(색 옵션 합침) 기준", "brands": out}, ensure_ascii=False, indent=1), encoding="utf-8")
print("그레이스유 니트류", base["그레이스유(공식몰)"]["styles"], base["그레이스유(공식몰)"]["list"])
for k in ("쿠메", "낫띵리튼", "아틀리에 나인", "쉬즈미스"):
    if "knit" in out[k]:
        print(k, "니트류", out[k]["knit"]["styles"], "정가 중앙", out[k]["knit"]["list"]["med"], out[k]["knit"]["list"]["q1"], out[k]["knit"]["list"]["q3"], "판매가 중앙", out[k]["knit"]["sale"]["med"], "할인", out[k]["knit"]["disc_share"], out[k]["knit"]["disc_med"])

# ---- 비교표 CSV
import csv

rows = []
gu_all = meta_gu = None
with open(D.parent / "tops_compare.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["브랜드", "구분", "스타일수", "정가Q1", "정가중앙", "정가Q3", "판매가중앙", "할인상품비율", "중앙할인율%", "출처"])
    w.writerow(["그레이스유(공식몰 상의)", "기준", 74, 114250, 158000, 226750, 158000, 0.0, "", "samples/graceyou-overview/data/products.json"])
    w.writerow(["그레이스유(공식몰 니트류)", "기준", out["_graceu_knit"]["styles"], out["_graceu_knit"]["list"]["q1"], out["_graceu_knit"]["list"]["med"], out["_graceu_knit"]["list"]["q3"], out["_graceu_knit"]["list"]["med"], 0.0, "", "같음"])
    for k, v in out.items():
        if k.startswith("_"):
            continue
        w.writerow([k, "상의 전체", v["styles"], v["list"]["q1"], v["list"]["med"], v["list"]["q3"], v["sale"]["med"], v["disc_share"], v["disc_med"] or "", v["source"]])
        if "knit" in v:
            n = v["knit"]
            w.writerow([k, "니트류만", n["styles"], n["list"]["q1"], n["list"]["med"], n["list"]["q3"], n["sale"]["med"], n["disc_share"], n["disc_med"] or "", "위와 같음, 이름에 니트·가디건·풀오버 포함"])
