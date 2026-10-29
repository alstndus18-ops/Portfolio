"""Small read-only browser pilot. Explicit URLs only; never a full catalogue crawl."""
import base64
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from ab_util import ab

JS = r'''JSON.stringify({url:location.href,title:document.title,text:document.body.innerText,
links:Array.from(document.querySelectorAll('a[href]')).map(a=>({text:a.innerText.trim(),url:a.href})).filter(a=>a.text),
selects:Array.from(document.querySelectorAll('select')).map(s=>({name:s.name,id:s.id,options:Array.from(s.options).map(o=>({text:o.text,value:o.value,disabled:o.disabled}))})),
detailImages:Array.from(document.querySelectorAll('#prdDetail img')).map(i=>({src:i.currentSrc||i.src,lazy:i.getAttribute('ec-data-src')||i.getAttribute('data-src'),alt:i.alt})),
structured:Array.from(document.querySelectorAll('script[type="application/ld+json"]')).map(s=>s.textContent)})'''

if __name__ == '__main__':
    brand, label, url = sys.argv[1:4]
    session = 'fcp-pilot-' + brand
    opened = ab('open', url, session=session) if url != '--current' else 'current page'
    raw = ab('eval', '-b', base64.b64encode(JS.encode()).decode(), session=session)
    try:
        data = json.loads(raw)
        if isinstance(data, str):
            data = json.loads(data)
    except ValueError:
        data = {'error': raw, 'navigation': opened}
    now = datetime.now(ZoneInfo('Asia/Seoul'))
    record = {'brand': brand, 'scope': 'pilot_page_only', 'observed_at': now.isoformat(), 'requested_url': url, 'page': data}
    out = Path(__file__).parent / '2026-10-29' / f'{brand}-{label}-{now:%H%M%S}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out))
    print(json.dumps({'title': data.get('title'), 'text': data.get('text', '')[:6000]}, ensure_ascii=False))
