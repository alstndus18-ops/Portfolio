"""5개 브랜드 일일 관찰 수집 (기획서 §14). 실행마다 새 JSON을 남기고 기존 파일은 덮어쓰지 않는다.
  python monitor/collect.py                 # graceu kume nw jj orr 전부
  python monitor/collect.py kume orr        # 일부만
  python monitor/collect.py --promos        # 메인 화면 행사만 다시 읽기 (상품 목록 재수집 없음)
결과: snapshots/monitor/<brand>/<YYYY-MM-DD>/<run_id>.json  (products · coverage · placements · promotions)
공개 목록만 읽는다. 로그인·장바구니·주문, robots.txt가 막는 정렬/필터/검색 경로는 쓰지 않는다. 요청 사이 0.4~1초 쉰다.
판매가는 누구나 보는 화면가(public_sale)만 sale_price에 넣고, 쿠폰 등 조건부 가격은 price_observations에만 둔다.
BEST/NEW는 영역 노출 위치이며 판매 순위가 아니다. 노출 영역이 없으면 not_provided로 남긴다.
"""
import base64
import html as H
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
npm = Path(os.environ.get('APPDATA', '')) / 'npm'
if npm.is_dir() and str(npm) not in os.environ.get('PATH', ''):
    os.environ['PATH'] = str(npm) + os.pathsep + os.environ['PATH']
from ab_util import ab  # noqa: E402
KST = ZoneInfo('Asia/Seoul')
UA = {'User-Agent': 'Mozilla/5.0'}
CACHE = Path(__file__).resolve().parent / 'cache'
CATEGORIES = ['상의(니트 제외)', '니트·가디건', '원피스', '아우터', '스커트', '팬츠']
PROMO_RE = re.compile(r'\d+\s?%|할인|쿠폰|세일|\bSALE\b|적립|무료\s?배송|증정|기획전|이벤트|\bEVENT\b|타임\s?세일', re.I)
PRICE_ONLY = re.compile(r'[\d,.%\s원₩~]+')


def now():
    return datetime.now(KST).isoformat(timespec='seconds')


def http(url):
    time.sleep(0.4)
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode('utf-8', 'ignore')


PERIOD = re.compile(r'(?<!유효기간 )(20\d\d[./-]\d{1,2}[./-]\d{1,2})\s*[~\-–]\s*(20\d\d[./-]\d{1,2}[./-]\d{1,2})')
SHORT_PERIOD = re.compile(r'(?<![\d.])(\d{1,2})[./](\d{1,2})\s*(?:\([^)]{1,3}\))?\s*[~\-–]\s*(\d{1,2})[./](\d{1,2})(?![\d.%])')


def add_periods(promos):
    """행사 문구나 행사 페이지 글자에 적힌 기간만 붙인다. 연도 없는 MM.DD - MM.DD는 관찰한 해로 본다. 없으면 None."""
    seen = {}
    for x in promos:
        raw, u = x.get('raw') or '', x.get('url') or ''
        m, s = PERIOD.search(raw), SHORT_PERIOD.search(raw)
        if m or s:
            y = (x.get('observed_at') or now())[:4]
            x['period'] = f'{m[1]} ~ {m[2]}' if m else f'{y}.{int(s[1]):02d}.{int(s[2]):02d} ~ {y}.{int(s[3]):02d}.{int(s[4]):02d}'
            continue
        if not u.startswith('http') or x['source'] in ('home_text', 'banner_alt', 'popup'):
            continue
        if u not in seen:
            try:
                t = ' '.join(H.unescape(re.sub(r'<[^>]+>', ' ', re.sub(r'(?s)<(script|style)[^>]*>.*?</\1>', ' ', http(u)))).split())
                m = PERIOD.search(t)
                seen[u] = f'{m[1]} ~ {m[2]}' if m else None
            except Exception:  # noqa: BLE001
                seen[u] = None
        x['period'] = seen[u]


def money(text):
    m = re.search(r'(\d[\d,]*)', text or '')
    return int(m[1].replace(',', '')) if m else None


class Browser:
    def __init__(self, session):
        self.session = session

    def open(self, url, timeout=45):
        ab('open', url, session=self.session, timeout=timeout)

    def eval(self, js, timeout=60):
        raw = ab('eval', '-b', base64.b64encode(js.encode()).decode(), session=self.session, timeout=timeout)
        # 보통은 출력 전체가 JSON 하나다. 안내 줄이 섞였을 때만 뒤에서부터 한 줄씩 본다
        for line in [raw] + list(reversed([x for x in raw.splitlines() if x.strip()])):
            try:
                v = json.loads(line)
                v = json.loads(v) if isinstance(v, str) and v[:1] in '[{"' else v
            except ValueError:
                continue
            if line is raw or isinstance(v, (dict, list)):
                return v
        raise ValueError('empty eval output')

    def page(self, url, js, tries=3, check_url=True):
        error = None
        for attempt in range(tries):
            self.open(url)
            try:
                data = self.eval(js)
            except ValueError as e:  # 느린 로딩·시간 초과 뒤의 빈 출력
                error = e
                continue
            # 이동에 실패한 채 이전 페이지를 기록하지 않는다
            if not isinstance(data, dict) or 'url' not in data or (check_url and str(data['url']).rstrip('/') != url.rstrip('/')):
                error = ValueError('navigation mismatch: ' + str(data)[:200])
                continue
            return data
        raise error

    def close(self):
        ab('close', session=self.session, timeout=20)


# ---------- 공통 분류 ----------
NON_CLOTHING = re.compile(r'\bbag\b|가방|\b백\b|shoe|슈즈|heel|힐\b|loafer|로퍼|boots?\b|부츠(?!컷)|mule|뮬|wedge|웨지|sandal|샌들|muffler|머플러|scarf|스카프|'
                          r'\bbelt\b|벨트|warmer|워머|necklace|earring|목걸이|귀걸이|모자|\bhat\b|\bcap\b|socks|양말|jewel|주얼리|keyring|키링|pouch|파우치|wallet|지갑|'
                          r'beanie|비니|gloves?\b|장갑|shawl|숄\b|slides?\b|슬라이드|flats\b|플랫\b|ballerina|발레리나|slipper|슬리퍼|swim|수영복|bikini|비키니', re.I)
NAME_RULES = [
    ('세트', re.compile(r'세트|셋업|\bset\b|set-?up', re.I)),
    ('원피스', re.compile(r'원피스|one[- ]?piece|dress|드레스|점프수트|jumpsuit', re.I)),
    ('스커트', re.compile(r'스커트|skirt', re.I)),
    ('팬츠', re.compile(r'팬츠|pants|trousers|트라우저|슬랙스|slacks|jeans|shorts|\bshort\s*(?:\(|$)|쇼츠|반바지|바지|bootcut|부츠컷|leggings|레깅스', re.I)),
    ('아우터', re.compile(r'코트|\bcoat\b|자켓|재킷|jacket|점퍼|jumper|패딩|padding|puffer|구스다운|덕다운|블루종|blouson|트렌치|trench|parka|파카|무스탕|mustang|'
                       r'블레이저|blazer|anorak|아노락', re.I)),
    ('니트·가디건', re.compile(r'니트|knit|가디건|카디건|cardigan|sweater|스웨터|풀오버|pullover|slipover|슬립오버', re.I)),
    ('아우터', re.compile(r'\bvest\b|조끼|베스트(?!셀러)', re.I)),  # 니트 조끼는 위에서 니트로 간다
    ('상의(니트 제외)', re.compile(r'sweatshirt|맨투맨|mtm|hood|후드|t-?shirt|티셔츠|\btee\b|shirt|셔츠|blouse|블라우스|sleeveless|슬리브리스|tank|\btop\b|탑\b|polo', re.I)),
    ('팬츠', re.compile(r'데님|denim', re.I)),  # 형태어 없이 '데님'만 있으면 청바지
]
SHAPES = ('원피스', '팬츠', '스커트', '세트')
KNIT = re.compile(r'니트|knit|가디건|카디건|cardigan|sweater|스웨터|풀오버|pullover|slipover|슬립오버', re.I)


def by_name(name):
    if NON_CLOTHING.search(name or ''):
        return None
    for cat, rx in NAME_RULES:
        if rx.search(name or ''):
            return cat
    return None


def top_split(name):
    return '니트·가디건' if KNIT.search(name or '') else '상의(니트 제외)'


def finalize_category(p, menu_cats, generic_ok=True):
    """menu_cats: 원본 메뉴에서 정해진 후보(None=이름으로 판단할 메뉴). 서로 다르면 이름 규칙으로 하나를 고르고, 못 고르면 미분류."""
    name = p['name'] or ''
    if NON_CLOTHING.search(name) and not any(c in CATEGORIES for c in menu_cats if c):
        cat, basis = None, 'non_clothing_name'
    else:
        fixed = {c for c in menu_cats if c}
        named = by_name(name)
        if len(fixed) == 1:
            cat, basis = fixed.pop(), 'official_menu'
            # 니트 메뉴의 원피스·팬츠·스커트는 형태 기준으로 옮긴다
            if cat == '니트·가디건' and named in SHAPES:
                cat, basis = named, 'official_menu+name_shape'
        elif len(fixed) > 1:
            # 니트 메뉴와 형태 메뉴가 겹치면 형태(니트 스커트=스커트)를 따른다
            if named in fixed or ('니트·가디건' in fixed and named in SHAPES):
                cat, basis = named, 'menu_conflict_resolved_by_name'
            else:
                cat, basis = None, 'menu_conflict'
        elif generic_ok and named:
            cat, basis = named, 'name_rule'
        else:
            cat, basis = None, 'not_classified'
    p['category'], p['category_basis'] = cat, basis
    p['in_clothing_scope'] = cat in CATEGORIES
    p['field_status']['category'] = 'observed' if cat else 'not_checked'


def product(brand, pid, name, url, observed_at, prices, image=None, availability='unknown', availability_raw=None, badges=None):
    sale = next((x['value'] for x in prices if x['kind'] == 'public_sale' and x['value']), None)
    regular = next((x['value'] for x in prices if x['kind'] == 'regular' and x['value']), None)
    if regular is not None and sale is not None and regular <= sale:
        regular = None if regular == sale else regular
    disc = round((regular - sale) / regular * 100, 1) if regular and sale and regular > sale else None
    return {'product_id': str(pid), 'channel_id': BRANDS[brand]['channel'], 'name': name, 'url': url, 'image_url': image,
            'observed_at': observed_at, 'sale_price': sale, 'regular_price': regular, 'currency': 'KRW',
            'displayed_discount_pct': disc, 'discount_basis': 'regular_price vs public sale_price' if disc is not None else None,
            'price_observations': prices, 'availability': availability, 'availability_raw': availability_raw,
            'badges': badges or [], 'category_raw': [], 'category': None, 'subtype': None, 'audience': 'unisex' if re.search(r'unisex', name or '', re.I) else 'women',
            'model_id': None, 'model_basis': None, 'published_at': None, 'published_date_kind': None, 'season_label': None, 'materials': None,
            'field_status': {'sale_price': 'observed' if sale else 'failed', 'regular_price': 'observed' if regular else 'not_provided',
                             'availability': 'observed' if availability != 'unknown' else 'not_checked',
                             'materials': 'not_checked', 'published_at': 'not_checked', 'model_id': 'not_checked'}}


def price_obs(value, kind, raw, source, observed_at, label=None, conditions=None):
    return {'value': value, 'kind': kind, 'label': label, 'raw': raw, 'conditions': conditions, 'source_url': source, 'observed_at': observed_at}


def home_promotions(br, url):
    """메인 화면의 공개 행사 문구(글자·배너 대체텍스트·행사 링크)를 원문으로 모은다. 혜택 해석은 하지 않는다."""
    js = r'''JSON.stringify({url:location.href,lines:document.body.innerText.split('\n').map(s=>s.trim()).filter(Boolean),
alts:[...document.querySelectorAll('img[alt]')].map(i=>i.alt.trim()).filter(Boolean),
pops:(()=>{const q='[class*="popup" i],[id*="popup" i],[class*="modal" i],[id*="modal" i]';
return [...document.querySelectorAll(q)].filter(e=>!e.parentElement?.closest(q)).map(e=>e.textContent.replace(/\s+/g,' ').trim()).filter(Boolean)})(),
links:[...document.querySelectorAll('a[href]')].map(a=>({t:(a.innerText||a.querySelector('img')?.alt||'').trim().replace(/\s+/g,' '),u:a.href}))})'''
    try:
        d = br.page(url, js, check_url=False)
    except Exception as e:  # noqa: BLE001
        return [{'source': 'home', 'url': url, 'status': 'failed', 'error': str(e)}], 'failed'
    seen, out = set(), []
    for kind, items in (('home_text', d['lines']), ('banner_alt', d['alts'])):
        for t in items:
            if len(t) <= 80 and PROMO_RE.search(t) and not PRICE_ONLY.fullmatch(t) and t not in seen:
                seen.add(t)
                out.append({'source': kind, 'raw': t, 'url': d['url'], 'observed_at': now()})
    # 팝업은 닫혀 있거나 숨겨져도 문구가 남아 있어 글자 전체를 본다 (끝난 행사도 기록)
    for t in d.get('pops', []):
        t = re.sub(r'\s*(오늘|하루|일주일)\s*(동안|하루)?\s*(보지\s*않기|열지\s*않음)|\s*닫기|\s*CLOSE', '', t, flags=re.I).strip()
        if len(t) <= 200 and PROMO_RE.search(t) and t not in seen:
            seen.add(t)
            out.append({'source': 'popup', 'raw': t, 'url': d['url'], 'observed_at': now()})
    for l in d['links']:
        if l['t'] and len(l['t']) <= 80 and PROMO_RE.search(l['t']) and not PRICE_ONLY.fullmatch(l['t']) and l['t'] not in seen:
            seen.add(l['t'])
            out.append({'source': 'home_link', 'raw': l['t'], 'url': l['u'], 'observed_at': now()})
    return out, 'observed'


# ---------- 그레이스유 (카페24, 브라우저) ----------
GU_JS = r'''JSON.stringify({url:location.href,title:document.title,
count:document.querySelector('.prdCount')?.textContent||null,
menus:[...document.querySelectorAll('a[href]')].filter(a=>new URL(a.href).pathname.startsWith('/category/')).map(a=>({name:a.textContent.trim().replace(/\s*\(\)$/,''),url:a.href})),
pages:[...document.querySelectorAll('.ec-base-paginate a[href]')].map(a=>a.href).filter(u=>u.includes('page=')),
cards:[...document.querySelectorAll('.xans-product-listnormal li[id^="anchorBoxId_"]')].map(e=>({
id:e.id.replace('anchorBoxId_',''),name:e.querySelector('.description')?.getAttribute('data-tle')||e.querySelector('.name')?.innerText.trim(),
url:e.querySelector('.name a')?.href,image:e.querySelector('a[name^="anchorBoxName_"] img')?.src,
fields:[...e.querySelectorAll('.spec>li')].map(f=>({label:f.querySelector('.title')?.textContent.trim(),text:f.innerText.trim(),raw:f.textContent.trim()})),
badges:[...e.querySelectorAll('.icon img')].map(i=>({alt:i.alt,src:i.src})),
}))})'''
FIRST_PAGE = re.compile(r'[?&]page=1(?!\d)')
GU_MENU = {'Outwears': '아우터', 'Dresses': '원피스', 'Skirts': '스커트', 'Pants': '팬츠', 'Homewears': '홈웨어', 'Tops': 'TOPS'}
GU_LISTS = ['View All', 'Outwears', 'Dresses', 'Tops', 'Skirts', 'Pants', 'Homewears', 'NEW ARRIVAL', 'PRE-ORDER', 'HAZLE DOWN 33% OFF',
            'CEREMONY', 'THE DAYANA', 'HAUTE COUTURE', 'WHITE LABEL']


def gu_card(card, ts, source):
    prices = []
    for f in card['fields']:
        label = (f.get('label') or '').replace(':', '').strip()
        if '가' not in label:
            continue
        kind = {'판매가': 'public_sale', '할인판매가': 'public_sale', '소비자가': 'regular'}.get(label, 'unknown')
        prices.append(price_obs(money(f['text']), kind, f['raw'], source, ts, label))
    # 할인판매가가 있으면 그것이 화면 판매가다
    if any(x['label'] == '할인판매가' for x in prices):
        for x in prices:
            if x['label'] == '판매가':
                x['kind'] = 'regular'
    badge = ' '.join(b['alt'] for b in card['badges'])
    sold = bool(re.search(r'품절|sold.?out', badge, re.I))
    return product('graceu', card['id'], card['name'], card['url'], ts, prices, card['image'],
                   'sold_out' if sold else 'unknown', badge or None, card['badges'])


def paginate(br, start, js, read_count, coverage, on_cards):
    """카페24식 쪽 번호 목록을 끝까지 읽는다. 표시 수를 채운 뒤의 반복은 끝, 그 전의 반복은 이동 실패로 본다."""
    queue, visited, ids, expected = [start], set(), [], None
    while queue:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        p = br.page(url, js)
        p['observed_at'] = now()
        n = read_count(p)
        if n is not None:
            if expected is not None and expected != n:
                coverage.update(status='partial', reason='display_count_changed')
            expected = n
        new = [c for c in p['cards'] if c['id'] not in ids]
        ids += [c['id'] for c in new]
        on_cards(new, p, url, len(ids) - len(new))
        if not new and p['cards']:
            if expected is not None and len(ids) >= expected:
                break
            if not FIRST_PAGE.search(url):
                coverage.update(status='partial', reason='repeated_product_ids')
                break
        for link in p.get('pages', []):
            if link not in visited and link not in queue and not FIRST_PAGE.search(link):
                queue.append(link)
    coverage.update(expected_count=expected, fetched_count=len(ids), visited_pages=len(visited), end_reached=True, product_ids=ids)
    if expected is not None and len(ids) != expected:
        coverage.update(status='partial', reason='count_mismatch')


def collect_graceu(run):
    br = Browser('fcp-mon-graceu')
    first = br.page('https://graceu.co.kr/product/list.html?cate_no=197', GU_JS)
    menus = {m['name']: m['url'] for m in first['menus']}
    run['menus'] = menus
    products, cats = {}, {}
    for name in GU_LISTS:
        if name not in menus:
            run['coverage'].append({'name': name, 'status': 'failed', 'reason': 'menu_missing'})
            continue
        cov = {'name': name, 'url': menus[name], 'status': 'complete', 'end_reached': False}

        def on_cards(new, p, url, offset, name=name):
            for i, card in enumerate(new, offset + 1):
                prod = products.setdefault(card['id'], gu_card(card, p['observed_at'], url))
                prod['category_raw'].append(name)
                if name == 'NEW ARRIVAL' and i <= 20:
                    run['placements'].append({'product_id': card['id'], 'list_kind': 'NEW', 'list_name': name, 'list_url': menus[name], 'position': i,
                                              'explicit_rank': None, 'sort': 'site_default', 'observed_at': p['observed_at']})
        try:
            paginate(br, menus[name], GU_JS, lambda p: money(p['count']) if p['count'] else None, cov, on_cards)
        except Exception as e:  # noqa: BLE001
            run['failed_urls'].append({'url': menus[name], 'error': str(e)})
            cov.update(status='failed', reason=str(e))
        run['coverage'].append(cov)
        print(f"  {name}: {cov.get('fetched_count')}/{cov.get('expected_count')} {cov['status']}", flush=True)
    for p in products.values():
        menu = [GU_MENU.get(c) for c in p['category_raw'] if c in GU_MENU]
        menu = [top_split(p['name']) if c == 'TOPS' else c for c in menu]
        # 여러 메뉴에 걸친 상품은 상의 메뉴보다 형태 메뉴(원피스·팬츠 등)를 우선한다
        shape = {c for c in menu if c not in ('상의(니트 제외)', '니트·가디건')}
        finalize_category(p, list(shape) if shape else menu, generic_ok=False)
    run['products'] = list(products.values())
    run['placement_status'] = {'BEST': {'status': 'not_provided', 'evidence': '메뉴(SHOP·BRAND·STORIES)와 메인 화면에 BEST 영역 없음 (메인은 이미지 섹션만)'},
                               'NEW': {'status': 'observed', 'list': 'NEW ARRIVAL', 'sort': 'site_default'}}
    promos, st = home_promotions(br, 'https://graceu.co.kr/')
    for c in run['coverage']:
        if re.search(r'OFF|SALE', c['name'], re.I):
            promos.append({'source': 'promo_menu', 'raw': c['name'], 'url': c['url'], 'product_count': c.get('fetched_count'), 'observed_at': now()})
    run['promotions'], run['promotion_status'] = promos, st
    br.close()


# ---------- 쿠메 (카페24, 일반 요청) ----------
KUME = 'https://kume-studio.co.kr'
KUME_LISTS = {453: ('WOMEN ALL', None), 454: ('OUTER', '아우터'), 458: ('TOP', 'TOP'), 459: ('TOP>SWEATER', '니트·가디건'),
              460: ('TOP>BLOUSE & SHIRT', '상의(니트 제외)'), 461: ('TOP>T-SHIRT & MTM', '상의(니트 제외)'), 462: ('BOTTOM', None),
              463: ('BOTTOM>SKIRT', '스커트'), 464: ('BOTTOM>DENIM', None), 465: ('BOTTOM>PANTS', '팬츠'), 466: ('BOTTOM>SHORTS', '팬츠'),
              467: ('DRESS', '원피스'), 468: ('ACC', 'ACC'), 572: ('WOMEN BEST', None), 609: ('26FW WOMEN', None)}


def kume_cards(h):
    out = []
    for no, blk in re.findall(r'<li id="anchorBoxId_(\d+)"(.*?)(?=<li id="anchorBoxId_|</ul>\s*</div>\s*</div>|$)', h, re.S):
        nm = re.search(r'class="\s*name"[^>]*>(.*?)</a>', blk, re.S)
        spans = re.findall(r'<span[^>]*>([^<]*)</span>', nm.group(1)) if nm else []
        name = next((H.unescape(s).strip() for s in reversed(spans) if s.strip() and s.strip() != '상품명'), '')
        items = re.findall(r'<li class="xans-record-">\s*<span([^>]*)>([^<]*)</span>', blk)
        img = re.search(r'<img src="([^"]+)"[^>]*class="big"', blk)
        out.append({'id': no, 'name': name, 'prices': [(('line-through' in a), t.strip()) for a, t in items if money(t)],
                    'image': ('https:' + img.group(1)) if img and img.group(1).startswith('//') else (img.group(1) if img else None)})
    return out


def collect_kume(run):
    products, members = {}, {}
    for cate, (label, _) in KUME_LISTS.items():
        url = f'{KUME}/product/list.html?cate_no={cate}'
        cov = {'name': label, 'url': url, 'status': 'complete', 'expected_count': None}
        ids = []
        try:
            for pg in range(1, 30):
                ts = now()
                h = http(url + (f'&page={pg}' if pg > 1 else ''))
                cards = [c for c in kume_cards(h) if c['id'] not in ids]
                if not cards:
                    break
                for i, c in enumerate(cards, len(ids) + 1):
                    ids.append(c['id'])
                    members.setdefault(c['id'], []).append(cate)
                    if cate == 572 and i <= 20:
                        run['placements'].append({'product_id': c['id'], 'list_kind': 'BEST', 'list_name': label, 'list_url': url, 'position': i,
                                                  'explicit_rank': None, 'sort': 'site_default', 'observed_at': ts})
                    if c['id'] in products or cate in (572, 609):
                        continue
                    prices = [price_obs(money(t), 'regular' if struck else 'public_sale', t, url, ts) for struck, t in c['prices']]
                    if len(prices) == 1:
                        prices[0]['kind'] = 'public_sale'
                    products[c['id']] = product('kume', c['id'], c['name'], f"{KUME}/product/detail.html?product_no={c['id']}", ts, prices, c['image'])
                if not re.search(rf'page={pg + 1}\b', h):
                    break
        except Exception as e:  # noqa: BLE001
            cov.update(status='failed', reason=str(e))
            run['failed_urls'].append({'url': url, 'error': str(e)})
        cov.update(fetched_count=len(ids), end_reached=cov['status'] == 'complete', product_ids=ids)
        run['coverage'].append(cov)
        print(f'  {label}: {len(ids)} {cov["status"]}', flush=True)
    for pid, cates in members.items():
        if pid not in products:  # BEST·시즌 목록에만 있고 여성 전체 목록에는 없는 상품
            continue
        p = products[pid]
        p['category_raw'] = [KUME_LISTS[c][0] for c in cates]
        menu = [KUME_LISTS[c][1] for c in cates if KUME_LISTS[c][1]]
        if 'ACC' in menu:
            finalize_category(p, [], generic_ok=False)
            p['category_basis'] = 'official_menu_acc'
            continue
        sub = [c for c in menu if c not in ('TOP',)]
        menu = sub or [top_split(p['name']) for c in menu if c == 'TOP']
        finalize_category(p, menu)
    run['products'] = list(products.values())
    run['placement_status'] = {'BEST': {'status': 'observed', 'list': 'WOMEN BEST (cate 572)', 'sort': 'site_default'},
                               'NEW': {'status': 'not_provided', 'evidence': 'NEW 메뉴 없음. 26FW(cate 608/609)는 시즌 컬렉션이라 NEW로 대체하지 않음'}}
    br = Browser('fcp-mon-kume')
    run['promotions'], run['promotion_status'] = home_promotions(br, KUME + '/')
    br.close()


# ---------- 낫띵리튼 (카페24 변형, 브라우저) ----------
NW = 'https://nothing-written.com'
NW_LISTS = [('Outwears', 78, '아우터'), ('Leather', 318, '아우터'), ('Coat', 258, '아우터'), ('Jacket', 253, '아우터'), ('Jumper', 265, '아우터'),
            ('Vest', 257, None), ('Tops', 79, 'TOP'), ('Shirt-', 145, '상의(니트 제외)'), ('Tee', 146, '상의(니트 제외)'), ('Sleeveless', 181, '상의(니트 제외)'),
            ('Knitwear', 147, '니트·가디건'), ('Bottoms', 81, None), ('Skirt', 155, '스커트'), ('Denim', 156, None), ('Pants', 276, '팬츠'),
            ('Dress', 277, '원피스'), ('Essentials', 110, None), ('Restock', 84, None), ('26-Summer.', 315, None),
            ('Outlet', 154, None), ('20-off', 250, None), ('30-off', 251, None), ('40-off', 252, None), ('50-off', 281, None)]
NW_JS = r"""JSON.stringify({url:location.href,cards:[...document.querySelectorAll('.col60')].map(e=>{const a=e.querySelector('.name a');const m=a&&a.getAttribute('href').match(/product_no=(\d+)/);
const box=e.closest('li')||e.parentElement;const img=box&&box.querySelector('img');
const pr=[...e.querySelectorAll('.price > div')].filter(d=>!d.classList.contains('thumbnail-soldout')).map(d=>d.innerText.trim()).filter(t=>/₩/.test(t));
const so=e.querySelector('.thumbnail-soldout');return {id:m?m[1]:null,name:a?a.innerText.trim():'',prices:pr,image:img?img.src:null,
soldout:!!(so&&!so.classList.contains('displaynone')),soldRaw:so?so.innerText.trim():null}}).filter(r=>r.id)})"""


def collect_nw(run):
    br = Browser('fcp-mon-nw')
    products, members = {}, {}
    for label, no, _ in NW_LISTS:
        base = f'{NW}/category/{label}/{no}/'
        cov = {'name': label.strip('-.'), 'url': base, 'status': 'complete', 'expected_count': None}
        ids = []
        try:
            for pg in range(1, 40):
                url = base + (f'?page={pg}' if pg > 1 else '')
                d = br.page(url, NW_JS)
                ts = now()
                fresh = [c for c in d['cards'] if c['id'] not in ids]
                if not fresh:
                    break
                for c in fresh:
                    ids.append(c['id'])
                    members.setdefault(c['id'], []).append(label)
                    if c['id'] in products:
                        continue
                    vals = [money(x) for x in c['prices'] if money(x)]
                    prices = [price_obs(money(x), 'unknown', x, url, ts) for x in c['prices'] if money(x)]
                    if prices:
                        lo, hi = min(vals), max(vals)
                        for x in prices:
                            x['kind'] = 'public_sale' if x['value'] == lo else 'regular'
                    products[c['id']] = product('nw', c['id'], c['name'], f"{NW}/product/detail.html?product_no={c['id']}", ts, prices, c['image'],
                                                'sold_out' if c['soldout'] else 'no_soldout_mark', c['soldRaw'] if c['soldout'] else None)
                    products[c['id']]['field_status']['availability'] = 'observed'
        except Exception as e:  # noqa: BLE001
            cov.update(status='failed', reason=str(e))
            run['failed_urls'].append({'url': base, 'error': str(e)})
        cov.update(fetched_count=len(ids), end_reached=cov['status'] == 'complete', product_ids=ids)
        run['coverage'].append(cov)
        print(f'  {label}: {len(ids)} {cov["status"]}', flush=True)
    menu_of = {label: cat for label, _, cat in NW_LISTS}
    for pid, labels in members.items():
        p = products[pid]
        p['category_raw'] = [x.strip('-.') for x in labels]
        menu = [menu_of[x] for x in labels if menu_of[x]]
        sub = [c for c in menu if c != 'TOP']
        menu = sub or [top_split(p['name']) for c in menu if c == 'TOP']
        finalize_category(p, menu)
    run['products'] = list(products.values())
    run['placement_status'] = {'BEST': {'status': 'not_provided', 'evidence': '여성 메뉴·메인에 BEST 영역 없음 (Restock·시즌은 BEST로 대체하지 않음)'},
                               'NEW': {'status': 'not_provided', 'evidence': '여성 메뉴·메인에 NEW 영역 없음'}}
    promos, st = home_promotions(br, NW + '/')
    for c in run['coverage']:
        if re.search(r'off|Outlet', c['name'], re.I):
            promos.append({'source': 'promo_menu', 'raw': c['name'], 'url': c['url'], 'product_count': c['fetched_count'], 'observed_at': now()})
    run['promotions'], run['promotion_status'] = promos, st
    br.close()


# ---------- 제이제이지고트 (바바더닷컴 브랜드관) ----------
BB = 'https://pc.babathe.com'
JJ_GOODS = BB + '/bnd/jjjigott/goods'
JJ_BEST = BB + '/bnd/jjjigott/promotion/2db1911e-7c47-4fe5-84d2-85bc730723ec'
JJ_BEST_JS = r"""(()=>{const ids=[];for(const a of document.querySelectorAll('a[onclick*="goodsId="],a[href*="goodsId="]')){const m=((a.getAttribute('onclick')||'')+(a.getAttribute('href')||'')).match(/goodsId=(GD\d+)/);if(m&&!ids.includes(m[1]))ids.push(m[1])}
const t=document.body.innerText;const per=(t.match(/\d{4}\.\d{2}\.\d{2}\s*~\s*\d{4}\.\d{2}\.\d{2}/)||[null])[0];return JSON.stringify({url:location.href,ids,period:per})})()"""


def jj_detail(gid):
    url = f'{BB}/goods/indexGoodsDetail?goodsId={gid}'
    try:
        h = http(url)
    except Exception as e:  # noqa: BLE001
        return gid, {'error': str(e), 'url': url}
    m = re.search(r'contentGoodsDtlCateNavigationBox"[^>]*>(.*?)</ul>', h, re.S)
    crumb = [H.unescape(x).strip() for x in re.findall(r'<a[^>]*>([^<]*)</a>', m.group(1))] if m else []
    org, sale = re.search(r'orgAmt\s*:\s*(\d+)', h), re.search(r'saleAmt\s*:\s*(\d+)', h)
    return gid, {'crumb': crumb, 'org': int(org[1]) if org else None, 'sale': int(sale[1]) if sale else None, 'url': url, 'observed_at': now()}


def jj_category(crumb, name):
    c = crumb[2:] if len(crumb) >= 3 and crumb[1] == '패션' else []
    if not c:
        return None, 'name_rule'
    top, sub = c[0], (c[1] if len(c) > 1 else '')
    if top == '아우터':
        if '가디건' in sub or '베스트' in sub:
            return ('니트·가디건' if KNIT.search(name) or '가디건' in ''.join(c) else '아우터'), 'official_breadcrumb+name'
        return '아우터', 'official_breadcrumb'
    if top == '원피스':
        return '원피스', 'official_breadcrumb'
    if top == '상의':
        return ('니트·가디건' if '니트' in sub or KNIT.search(name) else '상의(니트 제외)'), 'official_breadcrumb'
    if top == '하의':
        if '스커트' in sub:
            return '스커트', 'official_breadcrumb'
        if '팬츠' in sub:
            return '팬츠', 'official_breadcrumb'
        return by_name(name), 'official_breadcrumb+name'
    return None, 'official_breadcrumb_non_clothing'


def jj_list():
    """브랜드관 스크롤이 부르는 목록 요청을 한 번에 받는다 (스크롤은 페이지 경계에서 상품이 빠짐)."""
    page = http(JJ_GOODS)
    hidden = {k: v for k, v in re.findall(r'<input[^>]*type="hidden"[^>]*id="([^"]+)"[^>]*value="([^"]*)"', page)}
    total = (re.search(r'total\s*:\s*([\d,]+)', page) or [None, None])[1]
    data = {'brandNo': hidden.get('brandNo', ''), 'gubun': hidden.get('gubun', 'display'), 'tmplType': hidden.get('tmplType', ''),
            'bndThumbYn': hidden.get('bndThumbYn', ''), 'searchDisplay': 2000, 'pageNumber': 1}
    req = urllib.request.Request(BB + '/search/getGoodsListAjax', data=urllib.parse.urlencode(data).encode(),
                                 headers={**UA, 'X-Requested-With': 'XMLHttpRequest', 'Referer': JJ_GOODS})
    frag = urllib.request.urlopen(req, timeout=60).read().decode('utf-8', 'ignore')
    rows = {}
    for blk in re.split(r'<li class="[^"]*">', frag)[1:]:
        m = re.search(r'goodsId=(GD\d+)', blk)
        if not m or m.group(1) in rows:  # 같은 카드가 응답에 두 번 들어 있다
            continue
        blk = re.sub(r'(?s)<button\b.*?</button>|</?strong>', '', blk)
        L = [H.unescape(x).strip() for x in re.sub(r'<[^>]+>', '\n', blk).split('\n')]
        rows[m.group(1)] = [x for x in L if x and x != 'JJ JIGOTT']
    return [{'id': k, 'L': v} for k, v in rows.items()], total


def collect_jj(run):
    rows, total = jj_list()
    ts = now()
    # 화면 'total'은 목록에 나오지 않는 상품까지 센 값이라 기대 수로 쓰지 않는다 (요청 크기·분류·정렬을 바꿔도 목록은 같은 수)
    cov = {'name': 'JJ JIGOTT 브랜드관 ALL', 'url': JJ_GOODS, 'expected_count': None, 'site_total_text': money(total) if total else None,
           'fetched_count': len(rows), 'status': 'complete', 'end_reached': True, 'product_ids': [r['id'] for r in rows]}
    run['coverage'].append(cov)
    print(f"  ALL: {len(rows)} (화면 total {cov['site_total_text']}) {cov['status']}", flush=True)
    CACHE.mkdir(exist_ok=True)
    cache_path = CACHE / 'jj_breadcrumbs.json'
    crumbs = json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
    if not crumbs:  # 오늘 기존 상의 수집이 남긴 위치 표시를 처음 한 번 재사용한다
        seed = ROOT / 'snapshots' / 'tops' / 'jj' / 'categories-2026-10-29.json'
        if seed.exists():
            s = json.loads(seed.read_text(encoding='utf-8'))
            crumbs = {g: v for g, v in s['other'].items() if len(v) >= 3}
            crumbs.update({g: ['HOME', '패션', '상의'] for g in s['tops']})
    parsed, need = {}, []
    for r in rows:
        L = r['L']
        pi = next((i for i, x in enumerate(L) if re.fullmatch(r'\d+%', x)), None)
        nums = [(i, int(x.replace(',', ''))) for i, x in enumerate(L) if re.fullmatch(r'[0-9]{1,3}(,[0-9]{3})+', x)]
        end = pi if pi is not None else (nums[0][0] if nums else len(L))
        name = ' '.join(x for x in L[:end] if not re.fullmatch(r'\[.*\]', x)).strip()
        badges = [x for x in L[:end] if re.fullmatch(r'\[.*\]', x)] + [x for x in L[end:] if x in ('NEW', 'BEST', '예약배송') or '쿠폰' in x or '품절' in x]
        coupon = next((x for x in badges if '쿠폰' in x), None)
        parsed[r['id']] = (name, badges, coupon, pi, nums, L)
        if coupon or r['id'] not in crumbs:
            need.append(r['id'])
    with ThreadPoolExecutor(max_workers=2) as ex:
        details = dict(ex.map(jj_detail, need))
    for gid, d in details.items():
        if d.get('crumb') and len(d['crumb']) >= 3:
            crumbs[gid] = d['crumb']
    cache_path.write_text(json.dumps(crumbs, ensure_ascii=False, indent=0), encoding='utf-8')
    products = []
    for gid, (name, badges, coupon, pi, nums, L) in parsed.items():
        prices = []
        if nums:
            if pi is not None and len(nums) > 1:
                prices.append(price_obs(nums[0][1], 'regular', L[nums[0][0]], JJ_GOODS, ts, 'list_regular'))
                prices.append(price_obs(nums[1][1], 'conditional' if coupon else 'public_sale', f'{L[pi]} {L[nums[1][0]]}', JJ_GOODS, ts, 'list_display',
                                        coupon))
            else:
                prices.append(price_obs(nums[0][1], 'conditional' if coupon else 'public_sale', L[nums[0][0]], JJ_GOODS, ts, 'list_display', coupon))
        d = details.get(gid)
        if d and d.get('sale'):
            # 쿠폰가가 붙은 상품은 상세 기본 판매가(saleAmt)를 화면 판매가로 쓴다
            prices.append(price_obs(d['sale'], 'public_sale', f"saleAmt {d['sale']}", d['url'], d['observed_at'], 'detail_saleAmt'))
            if d.get('org') and d['org'] > d['sale']:
                prices.append(price_obs(d['org'], 'regular', f"orgAmt {d['org']}", d['url'], d['observed_at'], 'detail_orgAmt'))
        if coupon:
            prices = [x for x in prices if not (x['kind'] == 'regular' and x['label'] == 'list_regular')] if any(x['label'] == 'detail_orgAmt' for x in prices) else prices
        sold = any('품절' in b for b in badges)
        p = product('jj', gid, name, f'{BB}/goods/indexGoodsDetail?goodsId={gid}', ts, prices,
                    f'https://image.babathe.com/goods/{gid}/{gid}_1.jpg', 'sold_out' if sold else 'unknown', None, badges)
        crumb = crumbs.get(gid, [])
        p['category_raw'] = crumb[1:] if crumb else ['(위치 표시 없음)']
        cat, basis = jj_category(crumb, name)
        if basis == 'name_rule':
            finalize_category(p, [])
        else:
            finalize_category(p, [cat] if cat else [], generic_ok=False)
            p['category_basis'] = basis if cat else 'official_breadcrumb_non_clothing'
        if coupon and not (d and d.get('sale')):
            p['field_status']['sale_price'] = 'failed'
        products.append(p)
    run['products'] = products
    br = Browser('fcp-mon-jj')
    try:
        b = br.page(JJ_BEST, JJ_BEST_JS, check_url=False)
        for i, gid in enumerate(b['ids'][:20], 1):
            run['placements'].append({'product_id': gid, 'list_kind': 'BEST', 'list_name': 'MOST LOVED (#BEST, MD 추천순)', 'list_url': JJ_BEST,
                                      'position': i, 'explicit_rank': None, 'sort': 'MD 추천순(기본)', 'observed_at': now()})
        run['placement_status'] = {'BEST': {'status': 'observed', 'list': 'MOST LOVED 기획전 ' + (b.get('period') or ''), 'sort': 'MD 추천순(기본)',
                                            'note': '브랜드관 프로모션 영역. 전몰 베스트·판매 순위 아님'},
                                   'NEW': {'status': 'not_provided', 'evidence': '브랜드관에 NEW 메뉴 없음. 상품 카드의 NEW 배지는 badges에 보존'}}
    except Exception as e:  # noqa: BLE001
        run['placement_status'] = {'BEST': {'status': 'failed', 'error': str(e)}, 'NEW': {'status': 'not_provided'}}
    promos, st = home_promotions(br, BB + '/bnd/jjjigott')
    n_coupon = sum(1 for v in parsed.values() if v[2])
    promos.append({'source': 'list_badge', 'raw': f'목록 카드에 쿠폰 표시가 있는 상품 {n_coupon}개', 'url': JJ_GOODS, 'product_count': n_coupon, 'observed_at': ts})
    run['promotions'], run['promotion_status'] = promos, st
    br.close()


# ---------- 오르 (Shopify 공개 JSON) ----------
ORR = 'https://orr.store'


def orr_menu_category(title):
    t = title.upper().replace(' ', '')
    if re.search(r'SWIM|SHOE|ACC|BAG', t):
        return 'EXCLUDE'
    if 'SET' in t:
        return '세트'
    if re.search(r'/OUT|OUTER', t):
        return '아우터'
    if 'KNIT/PANTS' in t:
        return '팬츠'
    if 'KNIT' in t and ('SKIRT' in t or 'DRESS' in t):
        return None
    if 'KNIT' in t:
        return '니트·가디건'
    if re.search(r'/TOP', t):
        return 'TOP'
    if re.search(r'BTM/(PANTS|SHORTS)', t):
        return '팬츠'
    if re.search(r'SKIRT&DRESS/DRESS', t):
        return '원피스'
    if re.search(r'SKIRT&DRESS/SKIRT', t):
        return '스커트'
    return None


def collect_orr(run):
    cols = json.loads(http(ORR + '/collections.json?limit=250'))['collections']
    wanted = [c for c in cols if re.match(r'CLOT?/', c['title']) or re.match(r'(SALE/[12]차 SALE|TIME SALE) / ', c['title'])]
    products, members = {}, {}
    for c in wanted:
        handle = urllib.parse.quote(c['handle'])
        url = f"{ORR}/collections/{handle}/products.json?limit=250"
        # collections.json의 products_count는 화면에 공개되지 않은 상품까지 센다(점퍼 22 vs 화면·JSON 13). 표시 개수로 쓰지 않는다
        cov = {'name': c['title'], 'url': f"{ORR}/collections/{handle}", 'expected_count': None, 'admin_products_count': c['products_count'],
               'status': 'complete'}
        ids = []
        try:
            for pg in range(1, 10):
                ts = now()
                items = json.loads(http(url + f'&page={pg}'))['products']
                for it in items:
                    pid = str(it['id'])
                    if pid in ids:
                        continue
                    ids.append(pid)
                    members.setdefault(pid, []).append(c['title'])
                    if pid not in products:
                        products[pid] = orr_product(it, url, ts)
                if len(items) < 250:
                    break
        except Exception as e:  # noqa: BLE001
            cov.update(status='failed', reason=str(e))
            run['failed_urls'].append({'url': url, 'error': str(e)})
        cov.update(fetched_count=len(ids), end_reached=cov['status'] == 'complete', product_ids=ids)
        run['coverage'].append(cov)
    print(f"  collections {len(wanted)}, products {len(products)}, partial {sum(1 for c in run['coverage'] if c['status'] != 'complete')}", flush=True)
    for pid, titles in members.items():
        p = products[pid]
        p['category_raw'] = titles
        menu = [orr_menu_category(t) for t in titles]
        if 'EXCLUDE' in menu and not any(m in CATEGORIES + ['TOP', '세트'] for m in menu):
            finalize_category(p, [], generic_ok=False)
            p['category_basis'] = 'official_collection_non_clothing'
            continue
        menu = [m for m in menu if m and m != 'EXCLUDE']
        sub = [m for m in menu if m != 'TOP']
        menu = sub or [top_split(p['name']) for m in menu if m == 'TOP']
        finalize_category(p, menu)
    run['products'] = list(products.values())
    for kind, handle, name in (('BEST', 'best-seller', '베스트셀러'), ('NEW', 'new-in', '신상품')):
        ts = now()
        items = json.loads(http(f'{ORR}/collections/{handle}/products.json?limit=250'))['products']
        for i, it in enumerate(items[:20], 1):
            run['placements'].append({'product_id': str(it['id']), 'list_kind': kind, 'list_name': name, 'list_url': f'{ORR}/collections/{handle}',
                                      'position': i, 'explicit_rank': None, 'sort': 'collection_default', 'observed_at': ts, 'name': it['title']})
    run['placement_status'] = {'BEST': {'status': 'observed', 'list': '베스트셀러(best-seller)', 'sort': 'collection_default',
                                        'note': '화면 정렬 표시는 신상품순. 신발 등 비의류 포함, 원래 위치 유지. 판매 순위 아님'},
                               'NEW': {'status': 'observed', 'list': '신상품(new-in)', 'sort': 'collection_default'}}
    br = Browser('fcp-mon-orr')
    promos, st = home_promotions(br, ORR + '/')
    br.close()
    for c in cols:
        if c['handle'] in ('time-sale', '1차_sale', 'sale-2차', 'sale'):
            promos.append({'source': 'promo_collection', 'raw': c['title'], 'url': f"{ORR}/collections/{c['handle']}", 'product_count': c['products_count'],
                           'observed_at': now()})
    run['promotions'], run['promotion_status'] = promos, st


def orr_product(it, source, ts):
    vs = it['variants']
    prices = sorted({int(float(v['price'])) for v in vs})
    cmp_ = sorted({int(float(v['compare_at_price'])) for v in vs if v.get('compare_at_price') and float(v['compare_at_price']) > float(v['price'])})
    obs = [price_obs(prices[0], 'public_sale', f"variant price {'/'.join(map(str, prices))}", source, ts)]
    if cmp_:
        obs.append(price_obs(cmp_[0], 'regular', f"compare_at_price {'/'.join(map(str, cmp_))}", source, ts))
    avail = [v.get('available') for v in vs]
    status = 'sold_out' if not any(avail) else ('available' if all(avail) else 'some_variants_unavailable')
    p = product('orr', it['id'], it['title'], f"{ORR}/products/{it['handle']}", ts, obs,
                it['images'][0]['src'] if it.get('images') else None, status, f'{sum(1 for a in avail if a)}/{len(avail)} variants available')
    p['price_range'] = prices if len(prices) > 1 else None
    p['variants'] = [{'variant_id': str(v['id']), 'title': v['title'], 'price': int(float(v['price'])), 'available': v.get('available')} for v in vs]
    if re.fullmatch(r'OR\w{6,}', it.get('product_type') or ''):
        p['model_id'], p['model_basis'] = it['product_type'], 'shopify product_type 품번(색상 상품 공통)'
        p['field_status']['model_id'] = 'observed'
    p['published_at'], p['published_date_kind'] = it.get('published_at'), 'shopify published_at (재게시 시 바뀔 수 있음, 출시일 아님)'
    p['field_status']['published_at'] = 'observed'
    tags = it.get('tags') or []
    p['season_label'] = next((t for t in tags if re.fullmatch(r'\d{2}(FW|SS|SU|HS|F/W|S/S)', t)), None)
    p['subtype'] = next((t for t in tags if re.fullmatch(r'[A-Z][A-Z &/-]{2,}', t) and t not in ('NEW',)), None)
    p['tags'] = tags
    return p


BRANDS = {
    'graceu': {'name': '그레이스유', 'channel': 'graceu.co.kr', 'fn': collect_graceu},
    'kume': {'name': '쿠메', 'channel': 'kume-studio.co.kr', 'fn': collect_kume},
    'nw': {'name': '낫띵리튼', 'channel': 'nothing-written.com', 'fn': collect_nw},
    'jj': {'name': '제이제이지고트', 'channel': 'pc.babathe.com/bnd/jjjigott', 'fn': collect_jj},
    'orr': {'name': '오르', 'channel': 'orr.store', 'fn': collect_orr},
}


def run_brand(brand):
    started = now()
    run_id = datetime.now(KST).strftime('%Y%m%dT%H%M%S%f+0900')
    out = ROOT / 'snapshots' / 'monitor' / brand / started[:10] / (run_id + '.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    run = {'schema_version': 2, 'run_id': run_id, 'brand_id': brand, 'brand_name': BRANDS[brand]['name'], 'channel_id': BRANDS[brand]['channel'],
           'started_at': started, 'status': 'running', 'scope': 'women clothing listing + BEST/NEW + home promotions',
           'coverage': [], 'products': [], 'placements': [], 'promotions': [], 'failed_urls': []}
    print(brand, flush=True)
    try:
        BRANDS[brand]['fn'](run)
        add_periods(run['promotions'])
    except Exception as e:  # noqa: BLE001
        run['failed_urls'].append({'url': None, 'error': repr(e)})
        run['status'] = 'failed'
    prods = run['products']
    clothing = [p for p in prods if p['in_clothing_scope']]
    if run['status'] != 'failed':
        ok = all(c['status'] == 'complete' for c in run['coverage']) and not run['failed_urls']
        run['status'] = 'complete' if ok else 'partial'
    run.update(finished_at=now(), fetched_count=len(prods), clothing_count=len(clothing),
               category_counts={c: sum(1 for p in clothing if p['category'] == c) for c in CATEGORIES},
               sale_price_missing=[p['product_id'] for p in clothing if not p['sale_price']],
               limitations=['목록 기준. 소재는 monitor/materials.py', '모델 묶음은 오르(품번)만 확인, 나머지는 색상별 페이지 기준',
                            'BEST/NEW는 노출 위치이며 판매 순위가 아님', '미분류·비의류는 의류 통계에서 제외'])
    out.write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f"  -> {run['status']} 전체 {len(prods)} 의류 {len(clothing)} {run['category_counts']} 판매가 없음 {len(run['sale_price_missing'])}", flush=True)
    print('  ', out, flush=True)
    return out


HOME = {'graceu': 'https://graceu.co.kr/', 'kume': KUME + '/', 'nw': NW + '/', 'jj': BB + '/bnd/jjjigott', 'orr': ORR + '/'}


def refresh_promotions(brand):
    """최신 complete 실행의 메인 화면 행사만 다시 읽어 새 실행 파일로 남긴다 (상품 목록은 다시 모으지 않음)."""
    files = sorted((ROOT / 'snapshots' / 'monitor' / brand).glob('*/*.json'))
    run = next(r for r in (json.loads(f.read_text(encoding='utf-8')) for f in reversed(files)) if r.get('status') == 'complete')
    br = Browser(f'fcp-mon-{brand}')
    home, run['promotion_status'] = home_promotions(br, HOME[brand])
    br.close()
    run['promotions'] = home + [x for x in run['promotions'] if x['source'] not in ('home', 'home_text', 'banner_alt', 'home_link', 'popup')]
    add_periods(run['promotions'])
    run['derived_from'], run['promotions_refreshed_at'] = run['run_id'], now()
    run['run_id'] = datetime.now(KST).strftime('%Y%m%dT%H%M%S%f+0900')
    out = ROOT / 'snapshots' / 'monitor' / brand / now()[:10] / (run['run_id'] + '.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding='utf-8')
    print(brand, out.name, [(x['source'], x['raw'][:40], x.get('period')) for x in home if x['source'] == 'popup' or x.get('period')], flush=True)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    for b in (args or list(BRANDS)):
        refresh_promotions(b) if '--promos' in sys.argv else run_brand(b)
