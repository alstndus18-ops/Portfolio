"""상세 비교 표본 (기획서 §14): 그레이스유 최대 12개 + 비교 4곳에서 각 표본과 가장 가까운 상품 1개씩.
  python monitor/details.py            # 최신 목록 실행으로 표본을 고르고 상세를 읽는다
결과: snapshots/monitor/details/<YYYY-MM-DD>/<run_id>.json  (samples · pairs)
소재·제조국·실측은 상세 화면 글자에서만 읽는다. 그레이스유는 소재가 상세 이미지(상품정보제공고시)에만 있어
이미지 주소를 남기고, 판독값은 monitor/graceu_material_reads.json(사람·에이전트가 이미지를 보고 적은 원문)에서 붙인다.
"""
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect import CATEGORIES, KST, ROOT, Browser, now  # noqa: E402

BRANDS = ['graceu', 'kume', 'nw', 'jj', 'orr']
HERE = Path(__file__).resolve().parent
FIBER = (r'램스울|lambswool|울|wool|캐시미어|cashmere|재생면|면|모(?=\s*[:：]?\s*\d)|코튼|cotton|폴리에스터|폴리에스테르|폴리우레탄|폴리아미드|폴리|polyester|나일론|nylon|레이온|rayon|비스코스|viscose|아크릴|acrylic|'
         r'모달|modal|린넨|리넨|linen|마\b|실크|silk|견|스판덱스|스판|spandex|span\b|elastane|페이퍼|paper|폴리우레탄|polyurethane|알파카|alpaca|모헤어|mohair|앙고라|angora|'
         r'텐셀|tencel|리오셀|lyocell|아세테이트|acetate|큐프라|cupro|소가죽|양가죽|가죽|leather|솜털|깃털|down|feather|메리노|merino|야크|yak|폴리아미드|polyamide|pbt|기타섬유')
MAT_RE = re.compile(rf'((?:\[?\s*(?:겉감|안감|충전재|배색|내피|본판|몸판|부속|트리밍|outshell|shell|lining|filling|trim|contrast|main|body)\s*\d*\s*\]?\s*[:：]?\s*)?)'
                    rf'((?:(?:{FIBER})[\w ]{{0,12}}?\s*[:：]?\s*\d{{1,3}}(?:\.\d)?\s*%(?!\s*off)[\s,/]*)+)', re.I)
PART_RE = re.compile(r'(?:{})\s*[:：]?\s*(\d{{1,3}}(?:\.\d)?)\s*%'.format(FIBER), re.I)

DETAIL_JS = r"""(()=>{const b=document.body.cloneNode(true);b.querySelectorAll('script,style,noscript,svg').forEach(e=>e.remove());
const text=(b.innerText&&b.innerText.trim()?document.body.innerText:'')+'\n'+b.textContent.replace(/[ \t]+/g,' ').replace(/\n\s*\n+/g,'\n');
const opts=[...document.querySelectorAll('select')].map(s=>[...s.options].map(o=>o.text.trim()).filter(t=>t&&!/^-|선택|필수|empty/i.test(t)));
const radios=[...document.querySelectorAll('input[type=radio][data-attr-val]')].map(i=>i.getAttribute('data-attr-val')+(i.disabled?' (선택 불가)':''));
const imgs=[...document.querySelectorAll('#prdDetail img, .cont_detail img, .product-detail img')].map(i=>i.getAttribute('ec-data-src')||i.getAttribute('data-src')||i.src).filter(u=>u&&!u.startsWith('data:'));
return JSON.stringify({url:location.href,title:document.title,text:text.slice(0,60000),opts,radios,imgs})})()"""


def latest_run(brand):
    files = sorted((ROOT / 'snapshots' / 'monitor' / brand).glob('*/*.json'))
    runs = [json.loads(f.read_text(encoding='utf-8')) for f in reversed(files[-6:])]
    for want in ('complete', 'partial'):
        for r in runs:
            if r.get('status') == want and r.get('schema_version', 1) >= 2:
                return r
    raise SystemExit(f'{brand}: 사용할 목록 실행이 없음')


def tokens(name):
    n = (name or '').lower()
    keys = {'cardigan': r'cardigan|가디건|카디건', 'vest': r'vest|베스트', 'pullover': r'pullover|풀오버|sweater|스웨터', 'turtle': r'turtle|터틀|폴라',
            'coat': r'coat|코트', 'jacket': r'jacket|자켓|재킷', 'padding': r'padding|down|패딩|다운', 'tweed': r'tweed|트위드',
            'blouse': r'blouse|블라우스', 'shirt': r'shirt|셔츠', 'tee': r't-?shirt|티셔츠|tee\b', 'mini': r'mini|미니', 'midi': r'midi|미디',
            'long': r'long|롱|maxi|맥시', 'wide': r'wide|와이드', 'slim': r'slim|슬림', 'pleats': r'pleat|플리츠', 'cashmere': r'cashmere|캐시미어',
            'wool': r'wool|울', 'leather': r'leather|레더|가죽', 'denim': r'denim|데님', 'knit': r'knit|니트', 'fur': r'fur|퍼', 'belted': r'belt|벨티드'}
    return {k for k, rx in keys.items() if re.search(rx, n)}


def eligible(p):
    return p['in_clothing_scope'] and p['sale_price'] and p.get('availability') != 'sold_out'


def base_name(name):
    return re.sub(r'\s*\([^)]*\)\s*$', '', name or '').strip().lower()


def pick_graceu(run):
    """카테고리별 2개 (BEST 영역 미제공). NEW ARRIVAL 상단 노출 상품 1 + 판매가 중앙값에 가장 가까운 상품 1.
    NEW 노출이 없는 분류는 중앙값 상품 + 상위 가격대(Q3) 상품. 같은 모델의 색상 상품은 한 번만 고른다."""
    new_rank = {x['product_id']: x['position'] for x in run['placements'] if x['list_kind'] == 'NEW'}
    picks = []
    for cat in CATEGORIES:
        pool = [p for p in run['products'] if p['category'] == cat and eligible(p)]
        if not pool:
            continue
        prices = sorted(p['sale_price'] for p in pool)
        med, q3 = prices[len(prices) // 2], prices[len(prices) * 3 // 4]
        taken = set()

        def nearest(target, pool=pool, taken=taken):
            rest = [p for p in pool if base_name(p['name']) not in taken]
            return min(rest, key=lambda p: (abs(p['sale_price'] - target), p['product_id'])) if rest else None
        new = sorted((p for p in pool if p['product_id'] in new_rank), key=lambda p: new_rank[p['product_id']])
        chosen = []
        if new:
            chosen.append((new[0], f'NEW ARRIVAL 상단 노출 {new_rank[new[0]["product_id"]]}번째 ({cat}). BEST 영역 미제공이라 NEW 노출로 대체'))
            taken.add(base_name(new[0]['name']))
        mid = nearest(med)
        if mid:
            chosen.append((mid, f'{cat} 판매가 중앙값({med:,}원)에 가장 가까운 상품 (전체 {len(pool)}개 중)'))
            taken.add(base_name(mid['name']))
        if not new:
            hi = nearest(q3)
            if hi:
                chosen.append((hi, f'{cat} NEW 노출 없음 → 상위 가격대 Q3({q3:,}원)에 가장 가까운 상품'))
        picks += chosen[:2]
    return picks[:12]


def pick_match(gu, run, used):
    """같은 공통 분류에서 형태어 겹침이 많고 판매가가 가까운 상품. 조건이 안 맞으면 고르지 않는다."""
    gt = tokens(gu['name'])
    pool = [p for p in run['products'] if p['category'] == gu['category'] and eligible(p) and p['product_id'] not in used]
    if not pool:
        return None, f'{gu["category"]} 판매 가능 상품 없음'

    def score(p):
        return (-len(gt & tokens(p['name'])), abs(math.log(p['sale_price'] / gu['sale_price'])), p['product_id'])
    best = min(pool, key=score)
    shared = sorted(gt & tokens(best['name']))
    ratio = best['sale_price'] / gu['sale_price']
    if not shared and not (0.67 <= ratio <= 1.5):
        return None, '같은 분류에 형태어 겹침·비슷한 가격대(±50%) 상품 없음'
    return best, f'같은 분류({gu["category"]}), 형태어 겹침 {shared or "없음"}, 판매가 {best["sale_price"]:,}원 (기준의 {ratio:.2f}배)'


def parse_materials(text):
    out, seen = [], set()
    for m in MAT_RE.finditer(text):
        comp = re.sub(r'[\[\]:：\d\s]', '', m.group(1)).lower() or None
        raw = ' '.join((m.group(1) + m.group(2)).split()).strip(' ,/')
        parts = [(f.group(1).lower(), float(f.group(2))) for f in
                 re.finditer(r'({})[\w ]{{0,12}}?\s*[:：]?\s*(\d{{1,3}}(?:\.\d)?)\s*%(?!\s*off)'.format(FIBER), m.group(2), re.I)]
        key = (comp, tuple(parts))
        if key in seen:
            continue
        seen.add(key)
        out += [{'component': comp, 'fiber': f, 'percent': pct, 'raw': raw} for f, pct in parts]
    return out


def snippet(text, rx, width=500):
    m = re.search(rx, text, re.I)
    return re.sub(r'\s+', ' ', text[m.start():m.start() + width]).strip() if m else None


def read_detail(br, brand, p):
    rec = {'brand': brand, 'product_id': p['product_id'], 'name': p['name'], 'url': p['url'], 'category': p['category'], 'sale_price': p['sale_price'],
           'regular_price': p['regular_price'], 'image_url': p['image_url'], 'observed_at': now(), 'field_status': {}}
    try:
        d = br.page(p['url'], DETAIL_JS, check_url=False)
    except Exception as e:  # noqa: BLE001
        rec['error'] = str(e)
        rec['field_status'] = {k: 'failed' for k in ('materials', 'size', 'country', 'options')}
        return rec
    text = d['text']
    mats = parse_materials(text)
    rec['materials'] = mats or None
    rec['materials_raw'] = sorted({m['raw'] for m in mats}) or None
    rec['size_raw'] = snippet(text, r'실측|size\s*spec|size\s*guide|사이즈\s*(?:정보|가이드)|size\s*&\s*fit|\[SIZE')
    rec['country_raw'] = snippet(text, r'제조국|원산지|made in|country of origin', 80)
    rec['options_raw'] = [o for o in d['opts'] if o] + ([d['radios']] if d['radios'] else [])
    rec['description_raw'] = None
    if brand == 'graceu':
        info = [u for u in d['imgs'] if re.search(r'E18489E185A1E186BCE18491E185AEE186B7|상품정보', u)]  # '상품' 자모 = 상품정보제공고시 이미지
        rec['detail_images'] = [('https://graceu.co.kr' + u) if u.startswith('/') else u for u in d['imgs']]
        rec['material_image'] = (('https://graceu.co.kr' + info[-1]) if info[-1].startswith('/') else info[-1]) if info else None
    rec['field_status'] = {'materials': 'observed' if mats else ('not_checked' if brand == 'graceu' else 'not_provided'),
                           'size': 'observed' if rec['size_raw'] else 'not_checked', 'country': 'observed' if rec['country_raw'] else 'not_checked',
                           'options': 'observed' if rec['options_raw'] else 'not_checked'}
    return rec


def apply_graceu_reads(rec):
    path = HERE / 'graceu_material_reads.json'
    reads = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    r = reads.get(rec['product_id'])
    if not r:
        return
    rec['materials'] = parse_materials(r['material_raw']) or None
    rec['materials_raw'] = [r['material_raw']]
    rec['country_raw'] = r.get('country_raw') or rec.get('country_raw')
    rec['materials_source'] = f"상세 이미지 판독 ({r.get('read_by')}, {r.get('read_at')}): {r.get('image_url')}"
    rec['field_status']['materials'] = 'observed' if rec['materials'] else 'failed'
    if r.get('country_raw'):
        rec['field_status']['country'] = 'observed'


FIBER_KO = {'wool': '울', 'lambswool': '램스울', 'cashmere': '캐시미어', 'cotton': '면', '코튼': '면', 'polyester': '폴리에스터', '폴리에스테르': '폴리에스터',
            '폴리': '폴리에스터', 'nylon': '나일론', 'polyamide': '나일론', '폴리아미드': '나일론', 'rayon': '레이온', 'viscose': '레이온', '비스코스': '레이온',
            'acrylic': '아크릴', 'modal': '모달', 'linen': '린넨', '리넨': '린넨', '마': '린넨', 'silk': '실크', '견': '실크', 'spandex': '폴리우레탄',
            'span': '폴리우레탄', '스판': '폴리우레탄', '스판덱스': '폴리우레탄', 'elastane': '폴리우레탄', 'polyurethane': '폴리우레탄', 'alpaca': '알파카',
            'mohair': '모헤어', 'angora': '앙고라', 'tencel': '텐셀', 'lyocell': '텐셀', '리오셀': '텐셀', 'acetate': '아세테이트', 'cupro': '큐프라',
            'leather': '가죽', 'down': '솜털', 'feather': '깃털', 'merino': '울', '메리노': '울', 'yak': '야크', '모': '울', 'paper': '페이퍼'}


def main_fiber(rec):
    mats = [m for m in rec.get('materials') or [] if m['component'] in (None, '겉감', 'outshell', 'shell', 'main', '본판', '몸판')]
    if not mats:
        return None
    f = max(mats, key=lambda m: m['percent'])['fiber'].lower()
    return FIBER_KO.get(f, f)


def compare(gu, other):
    same, diff = [f'같은 분류 {gu["category"]}'], []
    shared = sorted(tokens(gu['name']) & tokens(other['name']))
    if shared:
        same.append('형태어 ' + ', '.join(shared))
    only = sorted(tokens(other['name']) - tokens(gu['name']))
    if only:
        diff.append('비교 상품에만 ' + ', '.join(only))
    fg, fo = main_fiber(gu), main_fiber(other)
    if fg and fo:
        (same if fg == fo else diff).append(f'주소재 {fg}' if fg == fo else f'주소재 {fg} vs {fo}')
    else:
        diff.append('소재 비교 불가(한쪽 미확인)')
    gap = other['sale_price'] - gu['sale_price']
    return {'overlap': same, 'differences': diff, 'price_diff_won': gap, 'price_diff_pct': round(gap / gu['sale_price'] * 100, 1)}


def main():
    runs = {b: latest_run(b) for b in BRANDS}
    run_id = datetime.now(KST).strftime('%Y%m%dT%H%M%S%f+0900')
    started = now()
    out = ROOT / 'snapshots' / 'monitor' / 'details' / started[:10] / (run_id + '.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    result = {'schema_version': 1, 'run_id': run_id, 'started_at': started, 'source_runs': {b: r['run_id'] for b, r in runs.items()},
              'samples': [], 'pairs': [], 'unmatched': []}
    br = Browser('fcp-mon-details')
    gu_picks = pick_graceu(runs['graceu'])
    used = {b: set() for b in BRANDS}
    for i, (gp, why) in enumerate(gu_picks, 1):
        g = read_detail(br, 'graceu', gp)
        g['selection_reason'] = why
        apply_graceu_reads(g)
        result['samples'].append(g)
        print(f'{i:2d} GU {gp["category"]} {gp["name"]} {gp["sale_price"]:,}', flush=True)
        for b in BRANDS[1:]:
            mp, reason = pick_match(gp, runs[b], used[b])
            if not mp:
                result['unmatched'].append({'graceu_product_id': gp['product_id'], 'brand': b, 'reason': reason})
                continue
            used[b].add(mp['product_id'])
            o = read_detail(br, b, mp)
            o['selection_reason'] = reason
            o['pair_with'] = gp['product_id']
            result['samples'].append(o)
            result['pairs'].append({'pair_id': f'{gp["product_id"]}~{b}~{mp["product_id"]}', 'graceu_product_id': gp['product_id'], 'brand': b,
                                    'product_id': mp['product_id'], **compare(g, o)})
            print(f'     {b}: {mp["name"]} {mp["sale_price"]:,} 소재 {o.get("materials_raw")}', flush=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    br.close()
    result['finished_at'] = now()
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    print(out)


def apply_reads_only():
    """최신 표본 실행에 그레이스유 이미지 판독값을 붙이고 비교쌍을 다시 계산해 새 실행 파일로 남긴다(상세 재방문 없음)."""
    src = sorted((ROOT / 'snapshots' / 'monitor' / 'details').glob('*/*.json'))[-1]
    result = json.loads(src.read_text(encoding='utf-8'))
    by_key = {(s['brand'], s['product_id']): s for s in result['samples']}
    for s in result['samples']:
        if s['brand'] == 'graceu':
            apply_graceu_reads(s)
    for pr in result['pairs']:
        pr.update(compare(by_key[('graceu', pr['graceu_product_id'])], by_key[(pr['brand'], pr['product_id'])]))
    result['derived_from'] = result['run_id']
    result['run_id'] = datetime.now(KST).strftime('%Y%m%dT%H%M%S%f+0900')
    result['reads_applied_at'] = now()
    out = src.parent.parent / now()[:10] / (result['run_id'] + '.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    print(out)


if __name__ == '__main__':
    apply_reads_only() if '--apply-reads' in sys.argv else main()
