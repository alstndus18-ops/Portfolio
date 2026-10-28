"""메이크샵(EUC-KR) 상품 목록에서 상품명·정가·판매가를 읽는다. robots.txt가 막지 않는 /shop/shopbrand.html만, 요청 사이 1초 쉰다.
  python tools/makeshop_list.py https://nain.co.kr 175 173 223
출력: JSON [{no,name,list,sale}]
"""
import html
import json
import re
import sys
import time
import urllib.request


def get(url):
    raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=25).read()
    return raw.decode("euc-kr", "ignore")


def parse(page):
    out = []
    for blk in re.split(r'<div class="thumb">', page)[1:]:
        no = re.search(r"branduid=(\d+)", blk)
        nm = re.search(r'<li class="dsc">\s*(.*?)\s*</li>', blk, re.S)
        pr = re.search(r'<span class="price">\s*([0-9,]+)', blk)
        if not (no and nm and pr):
            continue
        strikes = [int(x.replace(",", "")) for x in re.findall(r"<strike>\s*([0-9,]+)", blk)]
        sale = int(pr.group(1).replace(",", ""))
        out.append({"no": no.group(1), "name": html.unescape(re.sub(r"<[^>]+>", "", nm.group(1))).strip(), "list": max([sale] + strikes), "sale": sale})
    return out


if __name__ == "__main__":
    site, cats = sys.argv[1], sys.argv[2:]
    seen, res = set(), []
    for c in cats:
        for pg in range(1, 15):
            items = [i for i in parse(get(f"{site}/shop/shopbrand.html?type=Y&xcode={c}&sort=&page={pg}")) if i["no"] not in seen]
            if not items:
                break
            for i in items:
                seen.add(i["no"])
                i["cate"] = c
            res += items
            time.sleep(1)
    print(json.dumps(res, ensure_ascii=False))
