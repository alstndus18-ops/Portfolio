"""어패럴뉴스(apparelnews.co.kr) 사이트 검색으로 키워드별 기사 제목·요약을 모은다.
robots.txt가 /search/를 막지 않는 곳만 쓴다. 네이버·구글 검색 결과 페이지는 robots.txt가 모든 봇을 막아서(AI 검색·수집 명시 금지) 자동으로 읽지 않는다.
  python tools/news_search.py "키워드" ["키워드2" ...]   → data/raw/news/<날짜>_apparelnews.json 에 합쳐 저장
요청 사이 1.5초 쉰다. 쪽당 결과는 사이트가 정한 수(약 10개), 키워드마다 최대 3쪽.
"""
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "news"
UA = {"User-Agent": "Mozilla/5.0"}
CONTACT = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+|\b0\d{1,2}-\d{3,4}-\d{4}\b|\b01\d-?\d{3,4}-?\d{4}\b")  # 기사 하단의 기자·담당자 연락처는 저장하지 않는다
BASE = "https://www.apparelnews.co.kr"


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode("utf-8", "ignore")


def clean(s):
    return CONTACT.sub("[연락처 생략]", html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))).strip())


def parse(page):
    out = []
    m = re.search(r'<ul class="sublist">(.*?)</ul>\s*(?:<div|<!--)', page, re.S) or re.search(r'<ul class="sublist">(.*)', page, re.S)
    if not m:
        return out
    for li in re.findall(r"<li>(.*?)</li>", m.group(1), re.S):
        href = re.search(r'href="(/news/news_view/\?[^"]+)"', li)
        title = re.search(r"<dt>(.*?)</dt>", li, re.S)
        txt = re.search(r'<dd class="txt">(.*?)</dd>', li, re.S)
        dd = [clean(x) for x in re.findall(r"<dd[^>]*>(.*?)</dd>", li, re.S)]
        if href and title:
            idx = re.search(r"idx=(\d+)", href.group(1))
            out.append({"idx": idx.group(1) if idx else "", "url": BASE + html.unescape(href.group(1)), "title": clean(title.group(1)),
                        "snippet": clean(txt.group(1)) if txt else "", "meta": [x for x in dd if x and x != (clean(txt.group(1)) if txt else "")][:3]})
    return out


def search(kw, pages=3):
    res, seen = [], set()
    for p in range(1, pages + 1):
        url = f"{BASE}/search/?searchWord={urllib.parse.quote(kw)}&page={p}"
        items = [i for i in parse(get(url)) if i["idx"] not in seen]
        if not items:
            break
        for i in items:
            seen.add(i["idx"])
            i["keyword"] = kw
        res += items
        time.sleep(1.5)
    return res


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"{date.today().isoformat()}_apparelnews.json"
    data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    for kw in sys.argv[1:]:
        data[kw] = search(kw)
        print(kw, len(data[kw]))
    f.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
