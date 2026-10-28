"""그레이스유 공식몰(카페24) 개요 수집: 카테고리·가격·할인·옵션(색·사이즈·품절·추가금)·대표 사진.

공개 상품 목록·상세 페이지만 읽는다. robots.txt가 막는 경로(?sort=·?filter=·검색·장바구니·주문)는 건드리지 않는다.
색상별 사진·소재·OCR은 하지 않는다(빠른 개요용). 요청 사이 0.4초 쉬고 동시에 2개까지만 보낸다.
옵션 해석은 similar-search/tools/collect.py의 함수를 그대로 쓴다.

  python tools/collect.py          목록·상세·대표 사진을 모두 받아 data/products.json을 만든다
  python tools/collect.py --list   목록만 확인(상품 수·카테고리별 수)
"""
import html as H
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SS_TOOLS = ROOT.parents[0] / "similar-search" / "tools"
sys.path.insert(0, str(SS_TOOLS))
import collect as C  # noqa: E402  (similar-search의 get·parse_options·meta·save_image 재사용)

DOMAIN = "graceu.co.kr"
OUT = ROOT / "data" / "products.json"
THUMBS = ROOT / "thumbs"
OBSERVED = date.today().isoformat()

# 메뉴(SHOP)에서 읽은 카테고리. kind: all=전체, type=상품군, plan=기획·컬렉션
CATS = [
    (194, "View All", "all"),
    (195, "Outwears", "type"), (196, "Dresses", "type"), (197, "Tops", "type"), (198, "Skirts", "type"),
    (199, "Pants", "type"), (205, "Shoes", "type"), (204, "Bags", "type"), (207, "Accessories", "type"),
    (337, "Jewelry", "type"), (200, "Homewears", "type"),
    (697, "NEW ARRIVAL", "plan"), (716, "HAZLE DOWN 33% OFF", "plan"), (710, "PRE-ORDER", "plan"),
    (530, "CEREMONY", "plan"), (630, "THE DAYANA", "plan"), (552, "HAUTE COUTURE", "plan"), (589, "WHITE LABEL", "plan"),
]


def list_category(cate_no):
    """카테고리 하나의 상품 [{no, thumb_src, badges}]와 화면에 표시된 상품 수."""
    cards, shown = {}, None
    for page in range(1, 40):
        html = C.get(f"https://{DOMAIN}/product/list.html?cate_no={cate_no}&page={page}")
        if shown is None:
            m = re.search(r"prdCount[^>]*>.*?(\d[\d,]*)", html, re.S)
            shown = int(m.group(1).replace(",", "")) if m else None
        start = html.find("xans-product-listnormal")
        body = html[start:] if start >= 0 else html
        got = 0
        for m in re.finditer(r'<li id="anchorBoxId_(\d+)"[^>]*>(.*?)</li>\s*(?=<li id="anchorBoxId_|</ul>)', body, re.S):
            no, blk = m.group(1), m.group(2)
            if no in cards:
                continue
            got += 1
            img = re.search(r'<img src="(//[^"]+/web/product/medium/[^"]+)"', blk)
            badges = [H.unescape(a).strip() for a in re.findall(r'<div class="icon"[^>]*>.*?</div>', blk, re.S)]
            alts = re.findall(r'<img[^>]+alt="([^"]*)"', "".join(badges))
            src = ("https:" + img.group(1)) if img else None
            month = re.search(r"/web/product/medium/(\d{6})/", src or "")  # 대표 사진 업로드 월(출시월 아님)
            cards[no] = {"no": no, "thumb_src": src, "badges": [a for a in alts if a],
                         "img_month": month.group(1) if month else None}
        if not got:
            break
    return list(cards.values()), shown


def fetch_detail(no):
    html = C.get(f"https://{DOMAIN}/product/detail.html?product_no={no}")
    title = C.meta(html, "og:title")
    price, sale = C.meta(html, "product:price:amount"), C.meta(html, "product:sale_price:amount")
    colors, sizes = C.parse_options(html, no)
    return {"name": title, "price": int(float(price)) if price else None,
            "sale": int(float(sale)) if sale else None, "colors": colors, "sizes": sizes,
            "url": f"https://{DOMAIN}/product/detail.html?product_no={no}"}


def refresh_months():
    """전체 목록(View All)만 다시 읽어 이미 모은 상품에 대표 사진 업로드 월(img_month)을 채운다."""
    items, _ = list_category(194)
    month = {it["no"]: it["img_month"] for it in items}
    data = json.loads(OUT.read_text(encoding="utf-8"))
    for p in data["products"]:
        p["img_month"] = month.get(p["no"])
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"img_month {sum(1 for p in data['products'] if p['img_month'])}/{len(data['products'])}개 채움")


def parse_combos(html, no):
    """구매 옵션 조합 [{color, size, soldout, extra}]. 색·사이즈 구분은 similar-search의 dim_kind를 따른다."""
    combos = C.option_combos(html, no)
    kinds = {}
    for vals, titles, _, _ in combos:
        for i, t in enumerate(titles):
            kinds.setdefault(i, (t, set()))[1].add(vals[i])
    kinds = {i: C.dim_kind(t, sorted(vs)) for i, (t, vs) in kinds.items()}
    out = []
    for vals, titles, sold, extra in combos:
        row = {"color": None, "size": None, "soldout": bool(sold)}
        for i, v in enumerate(vals):
            v = re.sub(r"\s*\(?모델\s*착용\)?", "", v).strip()
            if kinds[i] == "both":
                c, _, s = v.partition("-")
                row["color"], row["size"] = c.strip() or None, s.strip() or None
            elif kinds[i] in ("color", "size"):
                row[kinds[i]] = v or None
        if extra:
            row["extra"] = extra
        out.append(row)
    return out


def refresh_combos():
    """이미 모은 상품의 상세 페이지를 다시 읽어 옵션 조합별 품절·추가금(combos)만 채운다."""
    data = json.loads(OUT.read_text(encoding="utf-8"))

    def work(p):
        try:
            p["combos"] = parse_combos(C.get(p["url"]), p["no"])
        except Exception as e:  # noqa: BLE001
            print("조합 실패", p["no"], e)
            p["combos"] = None
        return p

    with ThreadPoolExecutor(max_workers=2) as ex:
        list(ex.map(work, data["products"]))
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for p in data["products"] if p["combos"])
    print(f"combos {ok}/{len(data['products'])}개 채움")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if "--months" in sys.argv:
        return refresh_months()
    if "--combos" in sys.argv:
        return refresh_combos()
    cards, in_cats, shown = {}, {}, {}
    for cate_no, name, kind in CATS:
        items, n = list_category(cate_no)
        shown[cate_no] = n
        print(f"{name}: 목록 {len(items)}개 (화면 표시 {n})")
        for it in items:
            cards.setdefault(it["no"], it)
            in_cats.setdefault(it["no"], []).append(cate_no)
    print(f"고유 상품 {len(cards)}개")
    if "--list" in sys.argv:
        return
    THUMBS.mkdir(parents=True, exist_ok=True)

    def work(no):
        try:
            d = fetch_detail(no)
        except Exception as e:  # noqa: BLE001
            print("상세 실패", no, e)
            return None
        src = cards[no]["thumb_src"]
        d["thumb"] = f"thumbs/{no}.jpg" if src and C.save_image(src, THUMBS / f"{no}.jpg") else None
        d.update(no=no, cates=sorted(set(in_cats[no])), badges=cards[no]["badges"], img_month=cards[no]["img_month"])
        return d

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=2) as ex:
        products = [p for p in ex.map(work, sorted(cards, key=int, reverse=True)) if p]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out = {"observed_at": OBSERVED, "domain": DOMAIN,
           "cats": [{"no": n, "name": nm, "kind": k, "shown": shown[n],
                     "listed": sum(1 for p in products if n in p["cates"])} for n, nm, k in CATS],
           "products": products}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"완료 {len(products)}개, {time.time() - t0:.0f}초 -> {OUT}")


if __name__ == "__main__":
    main()
