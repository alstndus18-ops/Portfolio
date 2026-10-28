"""확정 비교 브랜드의 공식몰 전체 상품 목록을 읽어 날짜별 스냅샷으로 저장한다.
  python tools/snap_official.py            # 4곳 전부
  python tools/snap_official.py kume nw    # 일부만 (kume·nw·shesmiss·jjjigott)
결과: snapshots/official/<브랜드>/<오늘날짜>.json  (같은 날 다시 돌리면 덮어쓴다)
읽는 곳: 쿠메(카페24 HTML), 쉬즈미스(IDF몰 카페24 HTML에서 SHESMISS만), 낫띵리튼·제이제이지고트(스크립트로 그려지는 목록 → agent-browser).
robots.txt가 막지 않는 상품 목록 주소만 쓰고, 요청 사이 1초 쉰다. 로그인·장바구니·주문은 건드리지 않는다.
한 상품 = {id, name, list(정가), sale(판매가), disc(할인율%), soldout, badges, cats, url, pos(목록 순서)}
"""
import base64
import html
import json
import os
import re
import subprocess
from ab_util import ab as _ab
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TODAY = date.today().isoformat()
UA = {"User-Agent": "Mozilla/5.0"}
SESSION = os.environ.get("AGENT_BROWSER_SESSION") or "gu-snap-official"


def http(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode("utf-8", "ignore")


def ab(*args, timeout=75):
    return _ab(*args, timeout=timeout, session=SESSION)


def ab_json(js, timeout=120):
    raw = ab("eval", "-b", base64.b64encode(js.encode("utf-8")).decode("ascii"), timeout=timeout)
    # 페이지가 알리는 도구 목록 같은 안내 줄이 앞뒤에 섞일 수 있어, 뒤에서부터 JSON으로 읽히는 첫 줄을 쓴다
    for line in reversed([x for x in raw.splitlines() if x.strip()]):
        try:
            v = json.loads(line)
        except ValueError:
            continue
        return json.loads(v) if isinstance(v, str) else v
    raise ValueError("eval 결과를 읽지 못함: " + raw[:120])


def finish(slug, source, products, note=""):
    seen, uniq = set(), []
    for p in products:
        if p["id"] in seen:
            continue
        seen.add(p["id"])
        p["disc"] = round((1 - p["sale"] / p["list"]) * 100) if p["list"] and p["sale"] < p["list"] else 0
        uniq.append(p)
    for i, p in enumerate(uniq, 1):
        p["pos"] = i
    out = ROOT / "snapshots" / "official" / slug
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{TODAY}.json").write_text(json.dumps({"brand": slug, "source": source, "observed_at": TODAY, "note": note, "n": len(uniq), "products": uniq}, ensure_ascii=False, indent=1), encoding="utf-8")
    sold = sum(1 for p in uniq if p["soldout"])
    print(slug, "상품", len(uniq), "품절", sold, "할인중", sum(1 for p in uniq if p["disc"]))


# ---------- 카페24 목록 (쿠메·IDF몰) ----------
def cafe24_items(site, path, maxpage=15, brand=None):
    res, seen = [], set()
    for pg in range(1, maxpage + 1):
        page = http(f"{site}{path}{'&' if '?' in path else '?'}page={pg}")
        items = []
        for m in re.finditer(r'<li id="anchorBoxId_(\d+)"([^>]*)>(.*?)(?=<li id="anchorBoxId_|</ul>\s*</div>\s*<!--|$)', page, re.S):
            no, attr, blk = m.group(1), m.group(2), m.group(3)
            if no in seen:
                continue
            nm = re.search(r'product-card__title"><span[^>]*>([^<]+)</span>', blk) or re.search(r'class="[^"]*name"[^>]*>.*?<span[^>]*>([^<]+)</span>', blk, re.S) or re.search(r'alt="([^"]+)"', blk)
            name = html.unescape(nm.group(1)).strip() if nm else ""
            br = re.search(r'prd_brand[^>]*><span[^>]*>([^<]+)</span>', blk)
            if brand and (not br or br.group(1).strip() != brand):
                seen.add(no)
                continue
            ap, ac = re.search(r'ec-data-price="(\d+)"', attr), re.search(r'ec-data-custom="(\d+)"', attr)
            if ap and ac and int(ap.group(1)) > 0:
                lst, sale = max(int(ac.group(1)), int(ap.group(1))), int(ap.group(1))
            else:
                nums = [int(p.replace(",", "")) for p in re.findall(r'>\s*([0-9]{1,3}(?:,[0-9]{3})+)\s*원', blk)]
                struck = [int(p.replace(",", "")) for p in re.findall(r'line-through[^>]*>\s*([0-9]{1,3}(?:,[0-9]{3})+)\s*원', blk)]
                if not nums:
                    continue
                lst = struck[0] if struck else nums[0]
                sale = nums[-1] if struck else nums[0]
            soldout = bool(re.search(r'class="soldout"[^>]*>\s*[^<\s]', blk) or "품절" in re.sub(r"<script.*?</script>", "", blk, flags=re.S) or re.search(r"icon_soldout|sold[\s_-]?out\.(png|gif)", blk, re.I))
            badges = [html.unescape(x).strip() for x in re.findall(r'custom_option\d*[^>]*><span[^>]*>([^<]+)</span>', blk)]
            seen.add(no)
            items.append({"id": no, "name": name, "list": lst, "sale": sale, "soldout": soldout, "badges": badges,
                          "url": f"{site}/product/detail.html?product_no={no}"})
        if not items and not re.search(r'anchorBoxId_', page):
            break
        res += items
        time.sleep(1)
    return res


def snap_kume():
    items = cafe24_items("https://kume-studio.co.kr", "/product/list.html?cate_no=453")
    finish("kume", "https://kume-studio.co.kr/product/list.html?cate_no=453 (ALL)", items)


def snap_shesmiss():
    allp = []
    for cate in (157, 159, 160, 156, 155, 158):  # 아우터·탑·팬츠·스커트·드레스·잡화
        for it in cafe24_items("https://www.idfmall.co.kr", f"/product/list.html?cate_no={cate}", maxpage=25, brand="SHESMISS"):
            it["cats"] = [cate]
            allp.append(it)
    finish("shesmiss", "https://www.idfmall.co.kr/product/list.html?cate_no=157/159/160/156/155/158 (브랜드 SHESMISS만)", allp,
           "IDF몰은 쉬즈미스·리스트·시스티나 합동몰. 신규 최대 20% 쿠폰은 정가·판매가에 반영되지 않은 별도 혜택.")


# ---------- 낫띵리튼 (브라우저) ----------
NW_CATS = {"Outwears": 293, "Tops": 294, "Knitwear": 295, "Bottoms": 296, "Coat": 299, "Jacket": 300, "Jumper": 301, "Shirt": 303, "Tee": 304,
           "20-off": 250, "30-off": 251, "40-off": 252, "50-off": 281, "Restock": 84, "Outlet": 154, "Tops-archive": 79, "Knitwear-archive": 147}
NW_JS = r"""(()=>{const rows=[...document.querySelectorAll('.col60')].map(e=>{const a=e.querySelector('.name a');const m=a&&a.getAttribute('href').match(/product_no=(\d+)/);const pr=[...e.querySelectorAll('.price > div')].filter(d=>!d.classList.contains('thumbnail-soldout')).map(d=>d.innerText.trim()).filter(t=>/₩/.test(t));const so=e.querySelector('.thumbnail-soldout');return {id:m?m[1]:null,name:a?a.innerText.trim():'',prices:pr,soldout:!!(so&&!so.classList.contains('displaynone')&&so.offsetParent)}}).filter(r=>r.id);return JSON.stringify(rows)})()"""


def snap_nw():
    prods = []
    for label, no in NW_CATS.items():
        got = set()
        for pg in range(1, 30):
            # 이 쇼핑몰은 /product/list.html?page=N 으로는 쪽이 안 넘어가고 /category/<이름>/<번호>/?page=N 형태만 넘어간다
            ab("open", f"https://nothing-written.com/category/{label}/{no}/?page={pg}")
            rows = ab_json(NW_JS)
            fresh = [r for r in rows if r["id"] not in got]
            if not fresh:
                break
            got.update(r["id"] for r in fresh)
            rows = fresh
            for r in rows:
                am = [int(re.sub(r"[^0-9]", "", x)) for x in r["prices"] if re.sub(r"[^0-9]", "", x)]
                if not am:
                    continue
                prods.append({"id": r["id"], "name": r["name"], "list": max(am), "sale": min(am), "soldout": r["soldout"], "badges": [], "cats": [label],
                              "url": f"https://nothing-written.com/product/detail.html?product_no={r['id']}"})
            time.sleep(1)
    merged = {}
    for p in prods:
        if p["id"] in merged:
            merged[p["id"]]["cats"] = sorted(set(merged[p["id"]]["cats"] + p["cats"]))
            merged[p["id"]]["list"] = max(merged[p["id"]]["list"], p["list"])
            merged[p["id"]]["sale"] = min(merged[p["id"]]["sale"], p["sale"])
        else:
            merged[p["id"]] = p
    finish("nothing-written", "https://nothing-written.com/product/list.html?cate_no=" + "/".join(str(v) for v in NW_CATS.values()), list(merged.values()),
           "현재 시즌(293~304)+세일·재입고·아웃렛+상의·니트 지난 시즌 전체(79·147). 카테고리에 안 걸린 지난 시즌 아우터·하의·원피스는 빠져 있다.")


# ---------- 제이제이지고트 (바바더닷컴 브라우저) ----------
BB_SCROLL = r"""(async()=>{const cnt=()=>document.body.innerText.split('상세보기').length-1;let last=cnt(),same=0;for(let i=0;i<90&&same<5;i++){window.scrollTo(0,document.body.scrollHeight-1200);await new Promise(r=>setTimeout(r,300));window.scrollTo(0,document.body.scrollHeight);await new Promise(r=>setTimeout(r,1500));const c=cnt();if(c===last)same++;else{same=0;last=c;}}return JSON.stringify(cnt())})()"""
BB_READ = r"""(()=>{const out=[];const seen=new Set();for(const a of document.querySelectorAll('a[onclick*="goodsId="]')){const m=a.getAttribute('onclick').match(/goodsId=(GD\d+)/);if(!m||seen.has(m[1]))continue;let c=a;while(c.parentElement){const p=c.parentElement;const ids=new Set([...p.querySelectorAll('a[onclick*="goodsId="]')].map(x=>(x.getAttribute('onclick').match(/goodsId=(GD\d+)/)||[])[1]));if(ids.size>1)break;c=p}const el=c;const L=el.innerText.split('\n').map(s=>s.trim()).filter(Boolean).filter(x=>x!=='상세보기'&&x!=='장바구니 담기'&&x!=='JJ JIGOTT');seen.add(m[1]);out.push({id:m[1],L})}return JSON.stringify(out)})()"""


def snap_jj():
    ab("open", "https://pc.babathe.com/bnd/jjjigott/goods")
    time.sleep(3)
    ab_json(BB_SCROLL, timeout=200)
    rows = ab_json(BB_READ, timeout=60)
    prods = []
    for r in rows:
        L = r["L"]
        pi = next((i for i, x in enumerate(L) if re.fullmatch(r"\d+%", x)), None)
        nums = [(i, int(x.replace(",", ""))) for i, x in enumerate(L) if re.fullmatch(r"[0-9]{1,3}(,[0-9]{3})+", x)]
        if not nums:
            continue
        end = pi if pi is not None else nums[0][0]
        name = " ".join(x for x in L[:end] if not re.fullmatch(r"\[.*\]", x)).strip()
        badges = [x for x in L[:end] if re.fullmatch(r"\[.*\]", x)] + [x for x in L if x in ("NEW", "BEST") or "쿠폰" in x]
        lst = nums[0][1]
        sale = nums[1][1] if (pi is not None and len(nums) > 1) else lst
        prods.append({"id": r["id"], "name": name, "list": lst, "sale": sale, "soldout": any("품절" in x or "SOLD" in x.upper() for x in L), "badges": badges, "cats": [],
                      "url": f"https://pc.babathe.com/goods/indexGoodsDetail?goodsId={r['id']}"})
    finish("jjjigott", "https://pc.babathe.com/bnd/jjjigott/goods (바바더닷컴 브랜드관 전체)", prods, "바바그룹 그룹몰. 사이트 표시 total과 읽은 수를 비교할 것.")


JOBS = {"kume": snap_kume, "shesmiss": snap_shesmiss, "nw": snap_nw, "jjjigott": snap_jj}

if __name__ == "__main__":
    for k in (sys.argv[1:] or list(JOBS)):
        try:
            JOBS[k]()
        except Exception as e:  # noqa: BLE001
            print(k, "실패:", repr(e)[:300])
    ab("close")
