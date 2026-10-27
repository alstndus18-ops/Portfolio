"""상의 샘플 수집: 블루팝스(기존 샘플 목록) + 카페24 보세 여성몰의 상의 카테고리.

상품마다 상세 페이지 구매 옵션의 색상·사이즈(품절·추가금 포함)와 사진을 받는다. cands = 대표 사진 후보
(대표·추가·상세 설명 앞쪽), more = 색상별 사진 후보(나머지 추가·상세 설명 사진).
사진은 cache/에 있으면 다시 받지 않는다. 상의가 가장 잘 보이는 컷과 색상별 컷은 analyze.py가 고른다.
출력: data/products_raw.json, cache/<몰>/<상품번호>_<URL 해시>.jpg (긴 변 800px, 저장소에 올리지 않음)
공개 상품 목록·상세 페이지만 읽는다. 몰마다 페이지 요청 사이 0.4초 쉰다(몰끼리는 동시에, 사진은 상품마다 3장씩 동시에).
"""
import csv
import hashlib
import io
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
CACHE = ROOT / "cache"
OUT = ROOT / "data" / "products_raw.json"
PER_MALL = 100
MIN_PER_MALL = 60
MALL_TARGET = 4
CATEGORY = "상의"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
MAX_EXTRA, MAX_EDITOR = 3, 5  # 대표 사진 후보
MAX_EXTRA_ALL, MAX_EDITOR_ALL = 12, 40  # 색상별 사진 후보까지
IMG_WORKERS = 3

# 쇼핑몰 목록(korea_shopping_malls.csv)에서 상의 카테고리가 확인된 카페24 몰. 무작위 순서(시드 20261027, 1028)
# 썸스토어(somestore.co.kr)는 중고·빈티지 편집숍이라 보세 샘플에서 뺐다.
CANDIDATES = [
    ("MALL-0261", "피에스룩", "pslook.co.kr", 29),
    ("MALL-0189", "메이홀릭", "mayholic.co.kr", 25),
    ("MALL-0186", "마크들리", "markedly.co.kr", 78),
    ("MALL-0269", "레이디뮤즈", "ladymuse.co.kr", 44),
    ("MALL-0098", "사라172", "sara172.com", 47),
    ("MALL-0255", "룩엠제이", "lookmj.co.kr", 25),
    ("MALL-0170", "유어바웃미", "uaboutme.com", 27),
    ("MALL-0161", "모어모먼트", "moremoment.com", 44),
    ("MALL-0223", "데이로제", "dayroze.com", 45),
    ("MALL-0080", "슬로우리스트", "slowlist.co.kr", 78),
]
COLOR_TITLE = re.compile(r"색상|컬러|색깔|color", re.I)
SIZE_TITLE = re.compile(r"사이즈|size|치수", re.I)
SIZE_VALUE = re.compile(r"^(free|f|one ?size|프리|xs|s|m|l|xl|xxl|\d{2}(\D.*)?|\d(\(.*\))?)$", re.I)
COLOR_WORD = re.compile(r"블랙|화이트|아이보리|크림|베이지|그레이|차콜|네이비|블루|소라|그린|카키|민트|핑크|레드|브라운"
                        r"|옐로우|퍼플|라벤더|오트밀|멜란지|와인|버건디|오렌지|코랄|머스타드|올리브|모카|카멜|데님|청", re.I)
SKIP_IMG = re.compile(r"logo|icon|notice|banner|common|btn|size|delivery|info|blank", re.I)
NOT_DETAIL = re.compile(r"/web/product/|echosting|facebook|/board/|review", re.I)  # 다른 상품 썸네일·후기

_local = threading.local()


def session():
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
        _local.s.headers["User-Agent"] = UA
    return _local.s


def get(url):
    time.sleep(0.4)
    r = session().get(url, timeout=20)
    r.raise_for_status()
    return r.content.decode("utf-8", errors="replace")


def save_image(src, dest):
    if dest.exists():
        return True
    try:
        time.sleep(0.2)
        r = session().get(src, timeout=20)
        r.raise_for_status()
        im = Image.open(io.BytesIO(r.content)).convert("RGB")
        if min(im.size) < 150:
            return False
        # 세로로 긴 상세 이미지(색상별 착용 컷을 이어 붙인 것)는 나중에 컷별로 자르므로 폭 기준으로 줄인다
        im.thumbnail((600, 60000) if im.height > im.width * 1.8 else (800, 800))
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, "JPEG", quality=88)
        return True
    except Exception:  # noqa: BLE001
        return False


def list_product_nos(domain, cate_no):
    nos = []
    for page in range(1, 15):
        html = get(f"https://{domain}/product/list.html?cate_no={cate_no}&page={page}")
        start = html.find("xans-product-listnormal")
        body = html[start:] if start >= 0 else html
        found = [n for n in re.findall(r"anchorBoxId_(\d+)", body) if n not in nos]
        if not found:
            break
        nos.extend(found)
        if len(nos) >= PER_MALL:
            break
    return nos[:PER_MALL]


def meta(html, prop):
    m = re.findall(r'<meta[^>]+property="' + re.escape(prop) + r'"[^>]+content="([^"]*)"', html)
    return m[-1].strip() if m else ""


def clean_opt(v):
    return re.sub(r"\s*\[품절\]|\s*\([+-][\d,]+원\)", "", v).strip()


def dim_kind(title, values):
    """옵션 한 줄이 색상인지 사이즈인지(둘 다면 'both'). 제목이 애매하면 값 모양으로 판단."""
    c, s = bool(COLOR_TITLE.search(title)), bool(SIZE_TITLE.search(title))
    if c and s:
        return "both"
    if c or s:
        return "color" if c else "size"
    if values and all(SIZE_VALUE.search(v) for v in values):
        return "size"
    return "color" if values and any(COLOR_WORD.search(v) for v in values) else None


def option_combos(html, no):
    """구매 옵션 조합 [(값 목록, 제목 목록, 품절, 추가금)]. 페이지 안 option_stock_data(JSON)가 우선, 없으면 셀렉트."""
    m = re.search(r"option_stock_data\s*=\s*'(.*?)';", html)
    if m:
        try:
            data = json.loads(json.loads('"' + m.group(1) + '"'))
            out = []
            for d in data.values():
                titles = re.split(r"#\$%", d.get("option_name") or "")
                vals = d.get("option_value_orginal") or [d.get("option_value", "")]
                if len(vals) != len(titles):
                    vals = (d.get("option_value") or "").split("#$%")
                if len(vals) != len(titles):
                    continue
                # 재고 수량은 공개하지 않는 몰이 있어, 수량이 있을 때만 0개를 품절로 본다
                sold = d.get("is_selling") != "T" or d.get("is_display") == "F" or (
                    d.get("use_stock") is True and d.get("use_soldout") == "T"
                    and "stock_number" in d and int(d.get("stock_number") or 0) <= 0)
                out.append(([clean_opt(v) for v in vals], titles, sold, int(float(d.get("stock_price") or 0))))
            if out:
                return out
        except (ValueError, TypeError, AttributeError):
            pass
    dims = []
    for sel in re.finditer(r"<select([^>]*)>([\s\S]*?)</select>", html):
        attrs, inner = sel.groups()
        if 'product_type="product_option"' not in attrs or f'option_product_no="{no}"' not in attrs:
            continue
        title = (re.search(r'option_title="([^"]*)"', attrs) or [None, ""])[1]
        opts = [(clean_opt(v), "[품절]" in v) for v in re.findall(r'<option value="[^"*][^"]*"[^>]*>([^<]+)</option>', inner)]
        dims.append((title, [o for o in opts if o[0]]))
    return [([v], [t], sold, 0) for t, opts in dims for v, sold in opts]


def parse_options(html, no):
    """옵션 색상·사이즈 목록. 각 값은 {name, soldout(모든 조합이 품절), extra(추가금, 있으면)}."""
    acc = {"color": {}, "size": {}}

    def add(kind, v, sold, extra):
        model = "모델착용" in v
        v = re.sub(r"\s*\(?모델\s*착용\)?", "", v).strip()
        if not v or "선택" in v:
            return
        o = acc[kind].setdefault(v, {"name": v, "soldout": True, "extra": extra})
        if model:
            o["model"] = True
        o["soldout"] = o["soldout"] and sold
        o["extra"] = min(o["extra"], extra)

    combos = option_combos(html, no)
    kinds = {}
    for vals, titles, _, _ in combos:
        for i, t in enumerate(titles):
            kinds.setdefault(i, (t, set()))[1].add(vals[i])
    kinds = {i: dim_kind(t, sorted(vs)) for i, (t, vs) in kinds.items()}
    for vals, titles, sold, extra in combos:
        for i, v in enumerate(vals):
            if kinds[i] == "both":  # '블랙-1(55-66)': 첫 '-' 앞이 색, 뒤가 사이즈
                c, _, s = v.partition("-")
                add("color", c.strip(), sold, extra)
                add("size", s.strip(), sold, extra)
            elif kinds[i]:
                add(kinds[i], v, sold, extra)
    clean = lambda d: [{k: v for k, v in o.items() if k != "extra" or v} for o in d.values()]
    return clean(acc["color"]), clean(acc["size"])


def image_candidates(html, domain):
    """(대표 후보, 색상별 사진 후보). 대표 후보 = 대표 사진(og:image 마지막) + 추가 사진 3장 + 상세 설명 사진 앞 5장,
    색상별 후보 = 나머지 추가 사진과 상세 설명 사진(색상별 착용 컷은 보통 상세 설명 뒤쪽에 있다)."""
    def full(u):
        u = u.strip()
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return f"https://{domain}{u}"
        return u

    og = meta(html, "og:image")
    head = [full(og)] if og and "/web/product/" in og else []
    extras = []
    for u in re.findall(r'(?:src|ec-data-src)="([^"]*/web/product/extra/(?:small|big)/[^"]+)"', html):
        u = full(u.replace("/extra/small/", "/extra/big/"))
        if u not in head + extras:
            extras.append(u)
    # 상세 설명 사진. 몰마다 올리는 경로가 달라(/web/upload/, /web/<몰>/ 등) 경로로 거르지 않고 썸네일·후기만 뺀다
    editor = []
    for u in re.findall(r'<img[^>]+?(?:ec-data-src|data-src|src)="([^"]+\.(?:jpe?g|webp))(?:\?[^"]*)?"', html, re.I):
        u = full(u)
        if SKIP_IMG.search(u) or NOT_DETAIL.search(u) or u in head + extras + editor:
            continue
        editor.append(u)
    main = head + extras[:MAX_EXTRA] + editor[:MAX_EDITOR]
    more = extras[MAX_EXTRA:MAX_EXTRA_ALL] + editor[MAX_EDITOR:MAX_EDITOR_ALL]
    return main, more


def fetch_detail(item, domain, url):
    html = get(url)
    no = url.split("product_no=")[1].split("&")[0]
    item["colors"], item["sizes"] = parse_options(html, no)
    main, more = image_candidates(html, domain)
    key = item["id"].split("-")[0]
    rels = [f"cache/{key}/{no}_{hashlib.md5(src.encode()).hexdigest()[:10]}.jpg" for src in main + more]
    with ThreadPoolExecutor(max_workers=IMG_WORKERS) as ex:
        ok = list(ex.map(lambda a: save_image(a[0], ROOT / a[1]), zip(main + more, rels)))
    item["cands"] = [r for r, o in zip(rels[:len(main)], ok) if o]
    item["more"] = [r for r, o in zip(rels[len(main):], ok[len(main):]) if o]
    return html


def collect_mall(mall_id, name, domain, cate_no):
    try:
        nos = list_product_nos(domain, cate_no)
    except Exception as e:  # noqa: BLE001
        print(f"{name}: 목록 실패 {e}")
        return []
    if len(nos) < MIN_PER_MALL:
        print(f"{name}: 상의 {len(nos)}개라 건너뜀")
        return []
    items = []
    key = domain.split(".")[0]
    for no in nos:
        url = f"https://{domain}/product/detail.html?product_no={no}&cate_no={cate_no}"
        item = {"id": f"{key}-{no}", "mall_id": mall_id, "mall": name, "category": CATEGORY, "url": url}
        try:
            html = fetch_detail(item, domain, url)
        except Exception as e:  # noqa: BLE001
            print(f"{name}: 상세 실패 {no} {e}")
            continue
        title = re.sub(r"\s+-\s+" + re.escape(name) + r".*$", "", meta(html, "og:title"))
        if not title or not item["cands"]:
            continue
        price, sale = meta(html, "product:price:amount"), meta(html, "product:sale_price:amount")
        item.update(name=title, price=int(float(price)) if price else None,
                    sale=int(float(sale)) if sale else None)
        items.append(item)
    print(f"{name}: 상의 {len(items)}개")
    return items


def collect_bluepops():
    path = REPO / "samples" / "bluepops-all" / "products.csv"
    items = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["카테고리"] == CATEGORY][:PER_MALL]
    for row in rows:
        item = {"id": f"bluepops-{row['상품번호']}", "mall_id": "bluepops", "mall": "블루팝스",
                "category": CATEGORY, "name": row["상품명"],
                "price": int(row["판매가"]) if row["판매가"] else None,
                "sale": int(row["할인가(쿠폰 적용가)"]) if row["할인가(쿠폰 적용가)"] else None,
                "url": row["상품 링크"]}
        try:
            fetch_detail(item, "www.bluepops.co.kr", row["상품 링크"])
        except Exception as e:  # noqa: BLE001
            print(f"블루팝스: 상세 실패 {row['상품번호']} {e}")
            continue
        if item["cands"]:
            items.append(item)
    print(f"블루팝스: 상의 {len(items)}개")
    return items


def main():
    # 상의가 충분한 몰을 무작위 순서대로 먼저 고른 뒤, 몰마다 동시에 받는다.
    chosen = []
    for cand in CANDIDATES:
        if len(chosen) >= MALL_TARGET:
            break
        try:
            if len(list_product_nos(cand[2], cand[3])) >= MIN_PER_MALL:
                chosen.append(cand)
        except Exception:  # noqa: BLE001
            pass
    print("고른 몰:", ", ".join(c[1] for c in chosen))
    with ThreadPoolExecutor(max_workers=len(chosen) + 1) as ex:
        futures = [ex.submit(collect_bluepops)] + [ex.submit(collect_mall, *c) for c in chosen]
        products = [p for f in futures for p in f.result()]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(products, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"합계 {len(products)}개, 사진 후보 {sum(len(p['cands']) for p in products)}장 -> {OUT}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
