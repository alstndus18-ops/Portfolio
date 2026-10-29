"""모델별 소재·혼용률 기록. 색상만 다른 상품은 한 모델로 묶고 모델당 상세 페이지 하나만 읽는다.
  python monitor/materials.py [brand ...] [--limit N]
결과: monitor/materials.json (브랜드 → 모델 → 기록, 이미 확인한 모델은 다시 읽지 않음), monitor/out/materials.csv
소재는 상세 페이지 글자에서만 읽는다. 그레이스유 최근 상품은 상품정보 이미지에만 있어 이미지 주소를 남기고
monitor/graceu_material_reads.json(이미지를 보고 적은 원문)이 있으면 붙인다.
"""
import csv
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect import ROOT, http, now  # noqa: E402

BRANDS = ['graceu', 'kume', 'nw', 'jj', 'orr']
HERE = Path(__file__).resolve().parent
STORE = HERE / 'materials.json'
FIBER = (r'램스울|lambswool|울|wool|캐시미어|cashmere|재생면|면|모(?=\s*[:：]?\s*\d)|코튼|cotton|폴리에스터|폴리에스테르|폴리우레탄|폴리아미드|폴리|polyester|나일론|nylon|레이온|rayon|비스코스|viscose|아크릴|acrylic|'
         r'모달|modal|린넨|리넨|linen|마\b|실크|silk|견|스판덱스|스판|spandex|span(?![a-z])|elastane|페이퍼|paper|폴리우레탄|polyurethane|알파카|alpaca|모헤어|mohair|앙고라|angora|'
         r'텐셀|tencel|리오셀|lyocell|아세테이트|acetate|큐프라|cupro|bemberg|벰베르크|소가죽|양가죽|가죽|leather|lambskin|램스킨|sheepskin|쉽스킨|cowhide|천연모피|모피|lamb ?skin|합성피혁|인조가죽|솜털|깃털|down|feather|메리노|merino|야크|yak|폴리아미드|polyamide|pbt|기타섬유|기타|polyurethan|poly(?![a-z])|ramie|라미|hemp|헴프|metallic|메탈릭|메탈사|lurex|루렉스')
MAT_RE = re.compile(rf'((?:\[?\s*(?:겉감|안감|충전재|배색|내피|본판|몸판|부속|트리밍|outshell|shell|lining|filling|trim|contrast|main|body)\s*\d*\s*\]?\s*[:：]?\s*)?)'
                    rf'((?:(?:{FIBER})[\w ()]{{0,12}}?\s*[:：]?\s*\d{{1,3}}(?:\.\d)?\s*%(?!\s*off)[\s,/]*)+)', re.I)
FIBER_KO = {'wool': '울', 'lambswool': '램스울', 'cashmere': '캐시미어', 'cotton': '면', '코튼': '면', 'polyester': '폴리에스터', '폴리에스테르': '폴리에스터',
            '폴리': '폴리에스터', 'nylon': '나일론', 'polyamide': '나일론', '폴리아미드': '나일론', 'rayon': '레이온', 'viscose': '레이온', '비스코스': '레이온',
            'acrylic': '아크릴', 'modal': '모달', 'linen': '린넨', '리넨': '린넨', '마': '린넨', 'silk': '실크', '견': '실크', 'spandex': '폴리우레탄',
            'span': '폴리우레탄', '스판': '폴리우레탄', '스판덱스': '폴리우레탄', 'elastane': '폴리우레탄', 'polyurethane': '폴리우레탄', 'alpaca': '알파카',
            'mohair': '모헤어', 'angora': '앙고라', 'tencel': '텐셀', 'lyocell': '텐셀', '리오셀': '텐셀', 'acetate': '아세테이트', 'cupro': '큐프라', 'bemberg': '큐프라', '벰베르크': '큐프라',
            'leather': '가죽', 'lambskin': '가죽', '램스킨': '가죽', 'sheepskin': '가죽', '쉽스킨': '가죽', 'cowhide': '가죽', '소가죽': '가죽',
            '양가죽': '가죽', '천연모피': '모피', 'lamb skin': '가죽', '인조가죽': '합성피혁', 'poly': '폴리에스터', 'polyurethan': '폴리우레탄', 'down': '솜털', 'feather': '깃털', 'merino': '울', '메리노': '울', 'yak': '야크', '모': '울', 'paper': '페이퍼'}
JJ_NOTI = 'https://pc.babathe.com/goods/includeGoodsDtlNotifyList?goodsId={}&stId=1&svcGbCd=10'
GU_INFO = re.compile(r'E18489E185A1E186BCE18491E185AEE186B7')  # '상품' 자모 = 상품정보제공고시 이미지


def latest_run(brand):
    files = sorted((ROOT / 'snapshots' / 'monitor' / brand).glob('*/*.json'))
    runs = [json.loads(f.read_text(encoding='utf-8')) for f in reversed(files[-6:])]
    for want in ('complete', 'partial'):
        for r in runs:
            if r.get('status') == want and r.get('schema_version', 1) >= 2:
                return r
    raise SystemExit(f'{brand}: 사용할 목록 실행이 없음')


def parse_materials(text):
    groups = []
    for m in MAT_RE.finditer(text):
        comp = re.sub(r'[\[\]:：\d\s]', '', m.group(1)).lower() or None
        raw = ' '.join((m.group(1) + m.group(2)).split()).strip(' ,/')
        parts = [(f.group(1).lower(), float(f.group(2))) for f in
                 re.finditer(r'({})[\w ()]{{0,12}}?\s*[:：]?\s*(\d{{1,3}}(?:\.\d)?)\s*%(?!\s*off)'.format(FIBER), m.group(2), re.I)]
        gap = text[groups[-1]['end']:m.start()] if groups else '\n'
        # 같은 줄에서 수식어(ANTI-PILLING 등) 하나로 끊긴 혼용률은 앞 덩어리에 잇는다
        if (groups and comp is None and re.fullmatch(r'[ \t,/]*[A-Za-z가-힣\-]{0,15}[ \t]*', gap)
                and not re.search(r'lining|ri[bp]|shell|안감|배색|겉감|충전', gap, re.I)):
            g = groups[-1]
            g.update(raw=f"{g['raw']} {' '.join(gap.split())} {raw}".replace('  ', ' '), parts=g['parts'] + parts, end=m.end())
            continue
        groups.append({'comp': comp, 'raw': raw, 'parts': parts, 'end': m.end()})
    out, seen = [], set()
    for g in groups:
        key = (g['comp'], tuple(g['parts']))
        if key in seen:
            continue
        seen.add(key)
        out += [{'component': g['comp'], 'fiber': f, 'percent': pct, 'raw': g['raw']} for f, pct in g['parts']]
    return out


def main_fiber(rec):
    mats = [m for m in rec.get('materials') or [] if m['component'] in (None, '겉감', 'outshell', 'shell', 'main', '본판', '몸판')]
    if not mats:
        return None
    f = max(mats, key=lambda m: m['percent'])['fiber'].lower()
    return FIBER_KO.get(f, f)


def model_key(brand, p):
    if p.get('model_id'):
        return 'id:' + p['model_id']
    n = re.sub(r'^\s*(?:\[[^\]]*\]\s*)+', '', p['name'] or '')  # [1st Re-order] 같은 표시
    n = re.sub(r'\s*\([^()]*\)\s*$', '', n)  # (Black), (Black, W)
    if brand == 'kume':
        n = re.sub(r',\s*[^,]+$', '', n)  # ", Ivory"
    return ' '.join(n.lower().split())


def page_text(h):
    h = re.sub(r'(?is)<(script|style|noscript)\b.*?</\1>', ' ', h)
    h = re.sub(r'(?i)<br\s*/?>|</(p|div|li|tr|td|th|dt|dd|h\d)>', '\n', h)
    return html.unescape(re.sub(r'<[^>]+>', ' ', h))


def get(url):
    url = urllib.parse.quote(url, safe=':/?&=%#+,')  # 오르 한글 주소
    for i in range(4):
        try:
            return http(url)
        except urllib.error.HTTPError as e:
            if e.code != 429 or i == 3:
                raise
            time.sleep(10 * (i + 1))  # 요청 제한: 쉬었다가 다시


def pct_text(text):
    """'%'가 있는 줄과 그 바로 앞 줄(겉감·Shell 같은 머리말)만 남긴다. 규칙이 바뀌면 이 원문으로 다시 해석한다."""
    lines = [' '.join(x.split()) for x in text.splitlines()]
    keep = sorted({j for i, x in enumerate(lines) if '%' in x for j in (i - 1, i) if j >= 0 and lines[j]})
    return '\n'.join(lines[j] for j in keep)[:12000]


def parsed(rec):
    mats = parse_materials(rec.get('raw_text') or '')
    if mats:
        rec.update(status='observed', materials=mats, materials_raw=sorted({m['raw'] for m in mats}))
    else:
        rec.update(status='not_found', materials=None, materials_raw=None)
    return rec


def read_model(brand, p, reads):
    rec = {'checked_at': now(), 'url': p['url'], 'product_id': p['product_id']}
    h = None
    try:
        if brand == 'jj':  # 소재는 상품정보제공고시 '제품소재' (화면이 따로 불러옴)
            gid = re.search(r'goodsId=(\w+)', p['url']).group(1)
            items = json.loads(http(JJ_NOTI.format(gid)))['goodsNotifyList'] or []
            rec['source'] = 'jj_notify_제품소재'
            rec['raw_text'] = page_text(next((i['itemVal'] or '' for i in items if i.get('itemNm') == '제품소재'), ''))[:4000]
        else:
            h = get(p['url'])
            rec['source'] = 'detail_text'
            rec['raw_text'] = pct_text(page_text(h))
    except Exception as e:  # noqa: BLE001
        return {**rec, 'status': 'failed', 'error': str(e)[:200]}
    if parsed(rec)['status'] == 'observed':
        return rec
    if brand == 'graceu':
        imgs = [u for u in re.findall(r'ec-data-src="([^"]+)"', h) if GU_INFO.search(u)]
        if imgs:
            img = imgs[-1] if imgs[-1].startswith('http') else 'https://graceu.co.kr' + imgs[-1]
            r = reads.get(p['product_id'])
            if r:
                mats = parse_materials(r['material_raw'])
                return {**rec, 'status': 'observed' if mats else 'failed', 'source': f"image_read ({r.get('read_by')}, {r.get('read_at')})",
                        'material_image': img, 'materials': mats, 'materials_raw': [r['material_raw']]}
            return {**rec, 'status': 'image_only', 'material_image': img}
    return rec


def run_brand(brand, store, reads, limit=None):
    run = latest_run(brand)
    groups = {}
    for p in run['products']:
        if p['in_clothing_scope']:
            groups.setdefault(model_key(brand, p), []).append(p)
    old = store.get(brand, {})
    def stale(k):
        o = old.get(k)
        # 새 모델·실패만 다시 읽는다. 이미지 상품은 판독이 새로 생겼을 때만
        return not o or o['status'] == 'failed' or (o['status'] == 'image_only' and o['product_id'] in reads)
    todo = [(k, ps) for k, ps in groups.items() if stale(k)]
    todo = todo[:limit] if limit else todo
    # 같은 모델은 판매 중인 색상 페이지를 대표로 읽는다
    pick = {k: sorted(ps, key=lambda p: p.get('availability') == 'sold_out')[0] for k, ps in todo}
    with ThreadPoolExecutor(1 if brand == 'orr' else 4) as ex:  # 오르(Shopify)는 동시 요청에 429
        res = dict(zip(pick, ex.map(lambda k: read_model(brand, pick[k], reads), pick)))
    new = {}
    for k, ps in groups.items():
        base = res.get(k) or old.get(k) or {'status': 'not_checked'}
        name = re.sub(r'\s*\([^()]*\)\s*$', '', ps[0]['name'])
        name = re.sub(r',\s*[^,]+$', '', name) if brand == 'kume' else name
        new[k] = {**base, 'name': name, 'category': ps[0]['category'],
                  'color_pages': len(ps), 'product_ids': [p['product_id'] for p in ps], 'list_run_id': run['run_id']}
    # 지금 목록에 없는 모델도 기록은 남긴다 (소재는 바뀌지 않음)
    for k, v in old.items():
        new.setdefault(k, {**v, 'listed': False})
    store[brand] = new
    cnt = {}
    for k in groups:
        cnt[new[k]['status']] = cnt.get(new[k]['status'], 0) + 1
    print(f'{brand}: 의류 모델 {len(groups)}개 (색상 페이지 {sum(len(v) for v in groups.values())}) 이번에 읽음 {len(res)} → {cnt}', flush=True)


def write_csv(store):
    out = HERE / 'out' / 'materials.csv'
    out.parent.mkdir(exist_ok=True)
    with out.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['brand', 'model', 'category', 'color_pages', 'status', 'main_fiber', 'materials', 'source', 'url', 'material_image', 'checked_at'])
        for b in BRANDS:
            for k, r in sorted(store.get(b, {}).items(), key=lambda x: (x[1].get('category') or '', x[1].get('name') or '')):
                if r.get('listed') is False:
                    continue
                w.writerow([b, r.get('name'), r.get('category'), r.get('color_pages'), r['status'], main_fiber(r) or '',
                            ' / '.join(r.get('materials_raw') or []), r.get('source', ''), r.get('url'), r.get('material_image', ''), r.get('checked_at', '')])
    print(out)


def reparse(store):
    """저장된 원문(raw_text)으로 다시 해석한다. 페이지를 다시 열지 않는다."""
    for recs in store.values():
        for r in recs.values():
            if str(r.get('source', '')).startswith('image_read'):
                r['materials'] = parse_materials('\n'.join(r.get('materials_raw') or [])) or None
                continue
            if r.get('raw_text') is None:
                continue
            img = r['status'] == 'image_only'
            if parsed(r)['status'] != 'observed' and img:
                r['status'] = 'image_only'


def main():
    limit = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else None
    args = [a for a in sys.argv[1:] if not a.startswith('--') and not a.isdigit()]
    store = json.loads(STORE.read_text(encoding='utf-8')) if STORE.exists() else {}
    if '--reparse' in sys.argv:
        reparse(store)
        STORE.write_text(json.dumps(store, ensure_ascii=False, indent=1), encoding='utf-8')
        write_csv(store)
        return
    rp = HERE / 'graceu_material_reads.json'
    reads = json.loads(rp.read_text(encoding='utf-8')) if rp.exists() else {}
    brands = args or BRANDS
    with ThreadPoolExecutor(len(brands)) as ex:
        list(ex.map(lambda b: run_brand(b, store, reads, limit), brands))
    if not limit:
        STORE.write_text(json.dumps(store, ensure_ascii=False, indent=1), encoding='utf-8')
        write_csv(store)
    else:  # 시험 실행: 저장하지 않고 읽은 결과만 보여 준다
        for b in brands:
            for r in [r for r in store[b].values() if r['status'] != 'not_checked']:
                print(' ', b, r['status'], r.get('name'), '|', ' / '.join(r.get('materials_raw') or [])[:120], r.get('error', ''))


if __name__ == '__main__':
    main()
