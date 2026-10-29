"""상의 비교용 수집: 그레이스유와 확정 4곳의 '상의'를 같은 방식으로 읽는다 (목록 → 상세 → 옵션·품절).
  python tools/tops_collect.py gu kume shesmiss nw     # 카페24 몰은 일반 요청으로 읽는다 (상세 2개씩 동시, 요청 사이 0.4초)
  python tools/tops_collect.py jj                      # 바바더닷컴: 분류는 일반 요청, 옵션은 agent-browser로 화면에 그려진 값을 읽는다
결과: snapshots/tops/<브랜드>/<오늘날짜>.json  (행 = 사이트에 올라온 상품 한 줄. 색상별로 따로 올린 몰은 색상마다 한 줄)
읽는 값: 상품명·정가·판매가, 옵션(색상·사이즈)과 품절 표시. 재고 수량은 저장하지 않는다(품절 여부만).
옵션 해석은 samples/similar-search/tools/collect.py 의 함수(option_combos·dim_kind)를 그대로 쓴다.
robots.txt가 막는 경로(?sort=·?filter=·검색·장바구니·주문)는 건드리지 않는다.
"""
import base64
import html as H
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / "samples" / "similar-search" / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect as C  # noqa: E402  (get·meta·option_combos·dim_kind 재사용)

TODAY = date.today().isoformat()
OUT = ROOT / "snapshots" / "tops"

BRANDS = {
    "gu": {"ko": "그레이스유", "domain": "graceu.co.kr", "cate": 197, "brand": None, "note": "상의(Tops) 카테고리 197"},
    "kume": {"ko": "쿠메", "domain": "kume-studio.co.kr", "cate": 458, "brand": None, "note": "WOMEN > TOP(458). 479는 MEN TOP이라 쓰지 않는다"},
    "shesmiss": {"ko": "쉬즈미스", "domain": "www.idfmall.co.kr", "cate": 159, "brand": "SHESMISS", "note": "IDF몰 탑(159) 중 SHESMISS만"},
    "nw": {"ko": "낫띵리튼", "domain": "nothing-written.com", "cate": None, "brand": None, "note": "Tops·Knitwear(지난 시즌 79·147 + 현재 시즌 294·295·303·304) 중 바지·치마로 잘못 분류된 것 제외"},
}
CLEAN_COLOR = re.compile(r"\s*\(?모델\s*착용\)?")


def list_rows(domain, cate, brand=None):
    """카페24 목록에서 상품 번호(와 몰이 표시한 브랜드)를 모은다. 새 상품이 없는 쪽에서 멈춘다."""
    seen, rows = set(), []
    for page in range(1, 40):
        h = C.get(f"https://{domain}/product/list.html?cate_no={cate}&page={page}")
        parts = re.split(r'<li id="anchorBoxId_(\d+)"', h)[1:]
        new = 0
        for no, rest in zip(parts[0::2], parts[1::2]):
            if no in seen:
                continue
            seen.add(no)
            new += 1
            br = re.search(r'prd_brand[^>]*><span[^>]*>([^<]+)</span>', rest[:9000])
            if brand and (not br or br.group(1).strip() != brand):
                continue
            rows.append(no)
        if not new:
            break
    return rows


def split_options(h, no):
    """상세 페이지 옵션을 색상·사이즈·조합으로 정리한다. 독립 선택형(색상 따로·사이즈 따로)은 곱해서 조합을 만든다."""
    recs = C.option_combos(h, no)
    single, multi = {}, []
    for vals, titles, sold, _ in recs:
        if len(titles) == 1:
            single.setdefault(titles[0], {})[CLEAN_COLOR.sub("", vals[0]).strip()] = bool(sold)
        else:
            multi.append(([CLEAN_COLOR.sub("", v).strip() for v in vals], titles, bool(sold)))
    combos = []
    if multi:
        kinds = {}
        for vals, titles, _ in multi:
            for i, t in enumerate(titles):
                kinds.setdefault(i, (t, set()))[1].add(vals[i])
        kinds = {i: C.dim_kind(t, sorted(vs)) for i, (t, vs) in kinds.items()}
        for vals, titles, sold in multi:
            row = {"color": None, "size": None, "soldout": sold}
            for i, v in enumerate(vals):
                if kinds[i] == "both":
                    c, _, s = v.partition("-")
                    row["color"], row["size"] = c.strip() or None, s.strip() or None
                elif kinds[i] in ("color", "size"):
                    row[kinds[i]] = v or None
            combos.append(row)
    elif single:
        dims = {t: (C.dim_kind(t, sorted(vs)), vs) for t, vs in single.items()}
        col = next((vs for k, vs in dims.values() if k == "color"), None)
        siz = next((vs for k, vs in dims.values() if k == "size"), None)
        both = next((vs for k, vs in dims.values() if k == "both"), None)
        if both:
            for v, sold in both.items():
                c, _, s = v.partition("-")
                combos.append({"color": c.strip() or None, "size": s.strip() or None, "soldout": sold})
        elif col and siz:
            combos = [{"color": c, "size": s, "soldout": cs or ss} for c, cs in col.items() for s, ss in siz.items()]
        elif col:
            combos = [{"color": c, "size": None, "soldout": cs} for c, cs in col.items()]
        elif siz:
            combos = [{"color": None, "size": s, "soldout": ss} for s, ss in siz.items()]
    colors, sizes = {}, {}
    for c in combos:
        for key, acc in (("color", colors), ("size", sizes)):
            if c[key]:
                acc[c[key]] = acc.get(c[key], True) and c["soldout"]
    return ([{"name": k, "soldout": v} for k, v in colors.items()], [{"name": k, "soldout": v} for k, v in sizes.items()], combos)


def cafe24_row(domain, no):
    url = f"https://{domain}/product/detail.html?product_no={no}"
    h = C.get(url)
    price, sale = C.meta(h, "product:price:amount"), C.meta(h, "product:sale_price:amount")
    colors, sizes, combos = split_options(h, no)
    no_option = False
    if not combos:
        # 옵션이 없는 상품(단일 사이즈)은 페이지에 상품 단위 재고 정보만 있다. 수량은 저장하지 않고 품절 여부만 쓴다
        m = re.search(r"option_stock_data\s*=\s*'(.*?)';", h)
        if m:
            try:
                d = json.loads(json.loads('"' + m.group(1) + '"'))
                if isinstance(d, dict) and "use_stock" in d:
                    sold = bool(d.get("use_stock") and d.get("use_soldout") == "T" and int(d.get("stock_number") or 0) <= 0)
                    combos = [{"color": None, "size": "(옵션 없음)", "soldout": sold}]
                    sizes = [{"name": "(옵션 없음)", "soldout": sold}]
                    no_option = True
            except (ValueError, TypeError):
                pass
    lst = int(float(price)) if price else None
    sal = int(float(sale)) if sale else lst
    name = H.unescape(C.meta(h, "og:title"))
    if domain == "kume-studio.co.kr":  # og:title 이 가게 제목(KUMÉ | Wear Your Dream)이라 <title> 에서 읽는다
        tt = re.search(r"<title>([^<]*)</title>", h)
        name = H.unescape(re.sub(r"\s+-\s+KUME\s*$", "", tt.group(1))).strip() if tt else name
    return {"id": no, "name": name, "url": url, "list": lst, "sale": sal, "colors": colors, "sizes": sizes, "combos": combos, "has_options": bool(combos), "no_option": no_option}


def save(slug, source, rows, note):
    d = OUT / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{TODAY}.json").write_text(json.dumps({"brand": slug, "observed_at": TODAY, "source": source, "note": note, "n": len(rows), "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = sum(1 for r in rows if r.get("error"))
    print(slug, "행", len(rows), "옵션 읽음", sum(1 for r in rows if r.get("has_options")), "실패", bad, flush=True)


def collect_cafe24(slug):
    b = BRANDS[slug]
    if slug == "nw":
        snap = json.loads((ROOT / "snapshots" / "official" / "nothing-written" / f"{TODAY}.json").read_text(encoding="utf-8"))
        tops = {"Tops", "Knitwear", "Shirt", "Tee", "Tops-archive", "Knitwear-archive"}
        ids = [p["id"] for p in snap["products"] if set(p.get("cats", [])) & tops and not re.search(r"pants|skirt|shorts|dress", p["name"], re.I)]
        source = "https://nothing-written.com/category/{Tops,Knitwear,Shirt,Tee}/… (snapshots/official 의 카테고리 표시 기준)"
    else:
        ids = list_rows(b["domain"], b["cate"], b["brand"])
        source = f"https://{b['domain']}/product/list.html?cate_no={b['cate']}"
    print(slug, "목록", len(ids), flush=True)

    def work(no):
        try:
            return cafe24_row(b["domain"], no)
        except Exception as e:  # noqa: BLE001
            return {"id": no, "error": repr(e)[:160], "url": f"https://{b['domain']}/product/detail.html?product_no={no}"}

    with ThreadPoolExecutor(max_workers=2) as ex:
        rows = list(ex.map(work, ids))
    if slug == "shesmiss":
        off = {p["id"]: p for p in json.loads((ROOT / "snapshots" / "official" / "shesmiss" / f"{TODAY}.json").read_text(encoding="utf-8"))["products"]}
        for r in rows:
            o = off.get(r["id"])
            if o and not r.get("error"):
                r["meta_list"], r["meta_sale"] = r["list"], r["sale"]
                r["list"], r["sale"] = o["list"], o["sale"]
    save(slug, source, rows, b["note"])


# ---------- 제이제이지고트 (바바더닷컴) ----------
JJ_JS = r"""(()=>{const out={sizes:[],siblings:[],groups:[]};
document.querySelectorAll('#optionContList input[type=radio][data-attr-val]').forEach(i=>{const lab=document.querySelector('label[for="'+i.id+'"]');const cls=(i.className||'')+' '+(lab?lab.className+' '+lab.innerText:'');out.sizes.push({attr:i.getAttribute('data-attr-nm')||'',name:i.getAttribute('data-attr-val'),soldout:!!(i.disabled||/soldout|sold-out|disabled|품절/i.test(cls))})});
document.querySelectorAll('#optionContList dt').forEach(d=>out.groups.push(d.getAttribute('data-attr-nm')));
document.querySelectorAll('#goodsDtlModelNoBoxList li a').forEach(a=>{const m=((a.getAttribute('onclick')||'')+(a.href||'')).match(/goodsId=(GD\d+)/);if(m&&!out.siblings.includes(m[1]))out.siblings.push(m[1])});
const sb=document.querySelector('#btnGoodsDtlSoldOut');out.soldBtn=!!(sb&&sb.offsetParent!==null);
const h=document.querySelector('h1,.prd-name,.goods-name');out.title=h?h.innerText.trim():'';
return JSON.stringify(out)})()"""


def collect_jj():
    from ab_util import ab
    snap = json.loads((ROOT / "snapshots" / "official" / "jjjigott" / f"{TODAY}.json").read_text(encoding="utf-8"))
    base = {p["id"]: p for p in snap["products"]}
    # 1) 분류: 상세 HTML의 위치 표시(HOME > 패션 > 상의 > 니트웨어)로 상의만 고른다
    cat = {}

    def crumb(gid):
        try:
            h = C.get(f"https://pc.babathe.com/goods/indexGoodsDetail?goodsId={gid}")
            m = re.search(r'contentGoodsDtlCateNavigationBox"[^>]*>(.*?)</ul>', h, re.S)
            return gid, re.findall(r"<a[^>]*>([^<]*)</a>", m.group(1)) if m else []
        except Exception as e:  # noqa: BLE001
            return gid, ["ERR " + repr(e)[:60]]

    with ThreadPoolExecutor(max_workers=2) as ex:
        for gid, path in ex.map(crumb, list(base)):
            cat[gid] = path
    tops = [g for g, p in cat.items() if len(p) >= 3 and p[2] == "상의"]
    print("jj 전체", len(base), "상의", len(tops), "분류 못 읽음", sum(1 for p in cat.values() if len(p) < 3), flush=True)
    # 2) 옵션: 화면에 그려진 값을 읽는다
    rows = []
    session = __import__("os").environ.get("AGENT_BROWSER_SESSION") or "gu-tops-jj"
    for i, gid in enumerate(tops, 1):
        p = base[gid]
        row = {"id": gid, "name": p["name"], "url": p["url"], "list": p["list"], "sale": p["sale"], "cat_path": cat[gid]}
        try:
            ab("open", p["url"], timeout=60, session=session)
            raw = ab("eval", "-b", base64.b64encode(JJ_JS.encode("utf-8")).decode("ascii"), timeout=60, session=session)
            line = next((x for x in reversed(raw.splitlines()) if x.strip().startswith('"')), "")
            d = json.loads(json.loads(line)) if line else None
            if d is None:
                raise ValueError("eval 결과 없음: " + raw[:80])
            sizes = [{"name": s["name"], "soldout": s["soldout"]} for s in d["sizes"]]
            row.update({"sizes": sizes, "colors": [], "siblings": d["siblings"] or [gid], "groups": d["groups"], "product_soldout": d["soldBtn"],
                        "combos": [{"color": None, "size": s["name"], "soldout": s["soldout"] or d["soldBtn"]} for s in sizes], "has_options": bool(sizes)})
        except Exception as e:  # noqa: BLE001
            row["error"] = repr(e)[:160]
        rows.append(row)
        if i % 20 == 0:
            print("jj", i, "/", len(tops), flush=True)
    save("jj", "https://pc.babathe.com/bnd/jjjigott/goods (분류: 상세 화면의 위치 표시 상의)", rows, "바바더닷컴 JJ지고트 브랜드관. 색상은 상품 번호가 따로이고 같은 모델 묶음은 siblings 로 확인")
    (OUT / "jj" / f"categories-{TODAY}.json").write_text(json.dumps({"observed_at": TODAY, "tops": sorted(tops), "other": {g: pth for g, pth in cat.items() if g not in tops}}, ensure_ascii=False, indent=1), encoding="utf-8")
    collect_jj_extra()  # 위치 표시를 못 읽은 상품 중 이름이 상의인 것을 덧붙인다


def collect_jj_extra():
    """위치 표시를 못 읽은 상품(HOME만 나옴) 중 이름이 상의인 것을 화면에서 읽어 기존 jj 스냅샷에 덧붙인다."""
    from ab_util import ab
    import os
    cats = json.loads((OUT / "jj" / f"categories-{TODAY}.json").read_text(encoding="utf-8"))
    snap_path = OUT / "jj" / f"{TODAY}.json"
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    have = {r["id"] for r in snap["rows"]}
    base = {p["id"]: p for p in json.loads((ROOT / "snapshots" / "official" / "jjjigott" / f"{TODAY}.json").read_text(encoding="utf-8"))["products"]}
    top_name = re.compile(r"니트|티셔츠|블라우스|셔츠|가디건|풀오버")
    not_top = re.compile(r"원피스|팬츠|스커트|자켓|재킷|코트|점퍼|패딩|베스트|세트")
    ids = [g for g, v in cats["other"].items() if len(v) < 3 and g not in have and top_name.search(base[g]["name"]) and not not_top.search(base[g]["name"])]
    print("jj 위치 표시 없음 중 이름이 상의인 것", len(ids), ids, flush=True)
    session = os.environ.get("AGENT_BROWSER_SESSION") or "gu-tops-jj"
    for gid in ids:
        p = base[gid]
        row = {"id": gid, "name": p["name"], "url": p["url"], "list": p["list"], "sale": p["sale"], "cat_path": cats["other"][gid], "cat_by": "이름"}
        try:
            ab("open", p["url"], timeout=60, session=session)
            raw = ab("eval", "-b", base64.b64encode(JJ_JS.encode("utf-8")).decode("ascii"), timeout=60, session=session)
            line = next((x for x in reversed(raw.splitlines()) if x.strip().startswith('"')), "")
            d = json.loads(json.loads(line))
            sizes = [{"name": s["name"], "soldout": s["soldout"]} for s in d["sizes"]]
            row.update({"sizes": sizes, "colors": [], "siblings": d["siblings"] or [gid], "groups": d["groups"], "product_soldout": d["soldBtn"],
                        "combos": [{"color": None, "size": s["name"], "soldout": s["soldout"] or d["soldBtn"]} for s in sizes], "has_options": bool(sizes)})
        except Exception as e:  # noqa: BLE001
            row["error"] = repr(e)[:160]
        snap["rows"].append(row)
    snap["n"] = len(snap["rows"])
    snap["note"] = (snap.get("note", "") + f" / 위치 표시를 못 읽은 {len(cats['other']) and sum(1 for v in cats['other'].values() if len(v) < 3)}개 중 이름이 상의인 {len(ids)}개를 덧붙임").strip(" /")
    snap_path.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    print("jj 덧붙임 완료, 행", snap["n"], flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for k in sys.argv[1:]:
        if k == "jj+":
            collect_jj_extra()
        elif k == "jj":
            collect_jj()
        else:
            collect_cafe24(k)
