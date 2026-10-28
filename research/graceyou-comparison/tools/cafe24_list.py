"""카페24 상품 목록 페이지(공개 HTML)에서 상품명·정가·판매가를 읽는다. robots.txt가 막지 않는 주소만, 요청 사이 1초 쉰다.
  python tools/cafe24_list.py <사이트> <경로(쿼리 포함)> [최대쪽수]
  예) python tools/cafe24_list.py https://kume-studio.co.kr "/product/list.html?cate_no=459"
출력: JSON 목록 [{no,name,list,sale}]
"""
import html
import json
import re
import sys
import time
import urllib.request

UA = {"User-Agent": "Mozilla/5.0"}


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25).read().decode("utf-8", "ignore")


def parse(page):
    out = []
    for m in re.finditer(r'<li id="anchorBoxId_(\d+)"[^>]*>(.*?)(?=<li id="anchorBoxId_|</ul>\s*</div>\s*<!--|$)', page, re.S):
        no, blk = m.group(1), m.group(2)
        nm = re.search(r'product-card__title"><span[^>]*>([^<]+)</span>', blk) or re.search(r'alt="([^"]+)"', blk)
        name = html.unescape(nm.group(1)).strip() if nm else ""
        br = re.search(r'prd_brand[^>]*><span[^>]*>([^<]+)</span>', blk)
        attr = re.match(r'[^>]*', m.group(0)).group(0)
        ap, ac = re.search(r'ec-data-price="(\d+)"', attr), re.search(r'ec-data-custom="(\d+)"', attr)
        if ap and ac and int(ap.group(1)) > 0:
            out.append({"no": no, "name": name, "brand": br.group(1).strip() if br else "", "list": max(int(ac.group(1)), int(ap.group(1))), "sale": int(ap.group(1))})
            continue
        # 가격 칸만 본다(가격이 없는 칸의 숫자는 무시)
        nums = [int(p.replace(",", "")) for p in re.findall(r'>\s*([0-9]{1,3}(?:,[0-9]{3})+)\s*원', blk)]
        struck = [int(p.replace(",", "")) for p in re.findall(r'line-through[^>]*>\s*([0-9]{1,3}(?:,[0-9]{3})+)\s*원', blk)]
        if not nums:
            continue
        lst = struck[0] if struck else nums[0]
        sale = nums[-1] if struck else nums[0]
        out.append({"no": no, "name": name, "list": lst, "sale": sale})
    return out


def crawl(site, path, maxpage=8):
    seen, res = set(), []
    for pg in range(1, maxpage + 1):
        url = site + path + ("&" if "?" in path else "?") + f"page={pg}"
        items = [i for i in parse(get(url)) if i["no"] not in seen]
        if not items:
            break
        for i in items:
            seen.add(i["no"])
        res += items
        time.sleep(1)
    return res


if __name__ == "__main__":
    r = crawl(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 8)
    print(json.dumps(r, ensure_ascii=False))
