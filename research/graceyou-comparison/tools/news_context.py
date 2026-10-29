"""어패럴뉴스 기사 본문에서 특정 브랜드 이름 앞뒤 문장을 뽑는다(같이 언급된 브랜드를 보기 위함).
  python tools/news_context.py 그레이스유 낫띵리튼 쿠메   → data/raw/news/context_<날짜>.json
data/raw/news/<날짜>_apparelnews.json 의 해당 키워드 검색 결과 기사만 읽는다. 요청 사이 1.5초.
"""
import glob
import html
import json
import re
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

N = Path(__file__).resolve().parent.parent / "data" / "raw" / "news"
CONTACT = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+|\b0\d{1,2}-\d{3,4}-\d{4}\b|\b01\d-?\d{3,4}-?\d{4}\b")  # 기사 하단의 기자·담당자 연락처는 저장하지 않는다


def body(url):
    page = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read().decode("utf-8", "ignore")
    m = re.search(r'<div[^>]*id="(?:articleBody|news_body|article_view)"[^>]*>(.*?)</div>\s*<(?:div|p)[^>]*class="(?:btn|relation|tag)', page, re.S)
    t = m.group(1) if m else page
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", t, flags=re.S)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))).strip()


if __name__ == "__main__":
    src = json.loads(Path(sorted(glob.glob(str(N / "*_apparelnews.json")))[-1]).read_text(encoding="utf-8"))
    out = {}
    for name in sys.argv[1:]:
        res = []
        for a in src.get(name, []):
            try:
                t = body(a["url"])
            except Exception as e:  # noqa: BLE001
                res.append({"idx": a["idx"], "title": a["title"], "error": str(e)})
                continue
            ctx = [CONTACT.sub("[연락처 생략]", t[max(0, m.start() - 160): m.end() + 160]) for m in re.finditer(re.escape(name), t)][:3]
            res.append({"idx": a["idx"], "url": a["url"], "title": a["title"], "meta": a["meta"], "context": ctx})
            time.sleep(1.5)
        out[name] = res
        print(name, len(res))
    (N / f"context_{date.today().isoformat()}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
