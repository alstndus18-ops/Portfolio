"""수집 원본(JSON)으로 CSV와 웹페이지를 만든다. 원본만 읽고, 결과 파일은 손으로 고치지 않는다.
  python monitor/build.py
결과: monitor/out/index.html (인터넷 없이 표가 보임. 상품 사진만 원본 주소에서 불러옴), monitor/out/*.csv (UTF-8 BOM)
브랜드별 대표 실행 = 가장 최근 날짜의 마지막 complete 실행(없으면 partial을 쓰고 표시). 변화는 그 이전 날짜의 대표 실행과 비교한다.
"""
import csv
import html
import itertools
import json
import math
import re
import statistics as st
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect import BRANDS, CATEGORIES, ROOT, now  # noqa: E402
from materials import model_key  # noqa: E402

OUT = Path(__file__).resolve().parent / 'out'
MON = ROOT / 'snapshots' / 'monitor'
EVENT_BADGE = re.compile(r'쿠폰|SEASON OFF|특가|아울렛|SALE', re.I)
ALL = '전체'

# 행사 문구 분류: 문구에 적힌 말만 근거로 삼는 키워드 규칙이다(효과·의도는 해석하지 않는다).
# 메시지 유형은 planning/deep-research-report-2b.md '메시지 다중라벨 코딩' 중 문구에서 읽히는 4개만 쓴다.
PLAIN_DISCOUNT = '프로모션 표시 없이 할인'
PRICE_WORDS = re.compile(r'\d+\s*%|할인|쿠폰|\bSALE\b|\bOFF\b|특가|아울렛|\bOUTLET\b|UP TO', re.I)
BENEFIT_WORDS = re.compile(r'무료\s*배송|적립|사은품|포인트|리뷰|증정', re.I)
MSG_CODES = (
    ('가격·혜택', re.compile(PRICE_WORDS.pattern + '|' + BENEFIT_WORDS.pattern, re.I)),
    ('신상·시간성', re.compile(r'신상|\bNEW\b|컬렉션|\bCOLLECTION\b|\bDROP\b|시즌(?!\s*오프)|\bSEASON\b(?!\s*OFF)|재입고|\d{2}\s*(?:FW|SS)\b', re.I)),
    ('희소·독점', re.compile(r'한정|단독|예약|콜라보|\bLIMITED\b|\bEXCLUSIVE\b', re.I)),
    ('서비스', re.compile(r'출고|배송비|교환|반품|환불|당일')),
)


def message_info(text):
    """행사 문구 하나 → (판촉 형태, 메시지 유형 목록). 형태는 가격형(할인·쿠폰)/비가격형(사은품·적립·무료배송)/혼합/분류 불가."""
    if text == PLAIN_DISCOUNT:
        return '-', []
    t = re.sub(r'쿠폰\s*(?:을\s*)?증정', '쿠폰', text or '')  # '쿠폰 증정'은 사은품이 아니라 쿠폰이다
    price, benefit = bool(PRICE_WORDS.search(t)), bool(BENEFIT_WORDS.search(t))
    kind = '혼합' if price and benefit else '가격형' if price else '비가격형' if benefit else '분류 불가'
    return kind, [name for name, rx in MSG_CODES if rx.search(t)]


def message_rows(events):
    rows = []
    for e in events:
        kind, codes = message_info(e['event'])
        rows.append({'brand': e['brand'], 'event': e['event'], 'promo_kind': kind, 'message_codes': ' | '.join(codes)})
    return rows


def event_rows(brand, run):
    """행사 하나당 한 줄: 적용 의류 모델 수와 그 상품들의 화면 할인율 범위."""
    clothing = [p for p in run['products'] if p['in_clothing_scope']]
    total = len({model_key(brand, p) for p in clothing})
    ev, period, list_urls = {}, {}, set()
    for x in run['promotions']:
        if x['source'] in ('promo_menu', 'promo_collection'):
            nm, k = x['raw'], x['raw'].split('/')[-1].strip()
            ev[k] = [p for p in clothing if any(c == nm or c.startswith(nm + ' /') for c in p['category_raw'])]
            period[k] = x.get('period')
            list_urls.add(urllib.parse.unquote(x['url']).rstrip('/'))
    for p in clothing:
        for b in p.get('badges') or []:
            if isinstance(b, str) and EVENT_BADGE.search(b):
                ev.setdefault(b.strip('[] '), []).append(p)
    ev = {k: v for k, v in ev.items() if v}
    # 하위 행사를 모두 담은 상위 목록(예: Outlet = 20~50-off)은 하위 이름 앞에 붙이고 따로 세지 않는다
    for k in list(ev):
        if k not in ev:
            continue
        subs = [j for j in ev if j != k and {id(p) for p in ev[j]} < {id(p) for p in ev[k]}]
        if subs and {id(p) for j in subs for p in ev[j]} == {id(p) for p in ev[k]}:
            for j in subs:
                ev[f'{k} {j}'] = ev.pop(j)
                period[f'{k} {j}'] = period.get(j) or period.get(k)
            del ev[k]
    in_event = {id(p) for v in ev.values() for p in v}
    plain = [p for p in clothing if p.get('displayed_discount_pct') and id(p) not in in_event]
    name = BRANDS[brand]['name']

    def row(k, ps):
        n = len({model_key(brand, p) for p in ps})
        d = sorted({round(p['displayed_discount_pct']) for p in ps if p.get('displayed_discount_pct')})
        return {'brand': name, 'event': k, 'models': n, 'total': total, 'period': period.get(k) or '-',
                'discount': '할인 표시 없음' if not d else f'{d[0]}%' if d[0] == d[-1] else f'{d[0]}~{d[-1]}%'}
    rows = [row(k, ps) for k, ps in ev.items()]
    # 상품 목록이 없는 행사(메인 문구·배너 링크). 목록 행사와 같은 주소, 다른 문구에 포함된 문구는 뺀다
    texts = [x for x in run['promotions'] if x['source'] in ('home_text', 'home_link', 'popup') and (x.get('url') or '').startswith('http')
             and re.search(r'%|쿠폰', x.get('raw') or '') and not re.fullmatch(r'\s*쿠폰\s*받기\s*팝업\s*', x['raw'])
             and urllib.parse.unquote(x['url']).rstrip('/') not in list_urls]
    for x in texts:
        if any(x['raw'] != y['raw'] and x['raw'] in y['raw'] for y in texts):
            continue
        pct = re.findall(r'(\d+)\s*%', x['raw'])
        rows.append({'brand': name, 'event': x['raw'], 'models': None, 'total': total, 'period': x.get('period') or '-',
                     'discount': (f'최대 {pct[-1]}%' if re.search(r'up to|최대|~', x['raw'], re.I) else f'{pct[-1]}%') if pct else ''})
    if plain:
        rows.append(row('프로모션 표시 없이 할인', plain))
    return rows


def runs_by_date(brand):
    days = {}
    for f in sorted((MON / brand).glob('*/*.json')):
        r = json.loads(f.read_text(encoding='utf-8'))
        if r.get('schema_version', 1) < 2 or r.get('status') == 'failed':
            continue
        days.setdefault(f.parent.name, []).append(r)
    rep = {}
    for day, rs in days.items():
        done = [r for r in rs if r['status'] == 'complete']
        rep[day] = (done or rs)[-1]
    return rep


def quartiles(vals):
    vals = sorted(vals)
    if len(vals) < 4:
        return (vals[0], st.median(vals), vals[-1]) if vals else (None, None, None)
    q = st.quantiles(vals, n=4, method='inclusive')
    return q[0], q[1], q[2]


def model_units(brand, products):
    """색상만 다른 상품은 한 모델로 묶어 모델당 1표(가장 낮은 판매가)."""
    by_model = {}
    for p in products:
        by_model.setdefault(model_key(brand, p), []).append(p)
    return [min(ps, key=lambda p: p['sale_price'] or 10 ** 9) for ps in by_model.values()]


def category_rows(brand, run):
    rows = []
    clothing = [p for p in run['products'] if p['in_clothing_scope'] and p['sale_price']]
    groups = {}
    for p in clothing:
        groups.setdefault(model_key(brand, p), []).append(p)
    # 색상끼리 분류가 갈린 모델은 가장 많은 쪽 분류로 한 번만 센다
    model_cat = {k: max(CATEGORIES, key=[p['category'] for p in ps].count) for k, ps in groups.items()}
    for cat in [ALL] + CATEGORIES:
        ps = [p for k, g in groups.items() if cat in (ALL, model_cat[k]) for p in g]
        units, unit = model_units(brand, ps), '모델(색상 묶음)'
        sale = [p['sale_price'] for p in units]
        q1, med, q3 = quartiles(sale)
        reg = [p['regular_price'] or p['sale_price'] for p in units]
        disc = [p for p in units if p.get('displayed_discount_pct')]
        rows.append({'brand': BRANDS[brand]['name'], 'category': cat, 'unit': unit, 'n': len(units), 'pages': len(ps),
                     'sale_median': med, 'sale_q1': q1, 'sale_q3': q3, 'regular_median': st.median(reg) if reg else None,
                     'sale_min': min(sale) if sale else None, 'sale_max': max(sale) if sale else None,
                     'regular_min': min(reg) if reg else None, 'regular_max': max(reg) if reg else None,
                     'median_gap': st.median(reg) - med if reg else None,
                     'discount_models': len(disc),
                     'discount_share_pct': round(len(disc) / len(units) * 100) if units else None,
                     'discount_median_pct': st.median([p['displayed_discount_pct'] for p in disc]) if disc else None,
                     'discount_min_pct': min(p['displayed_discount_pct'] for p in disc) if disc else None,
                     'discount_max_pct': max(p['displayed_discount_pct'] for p in disc) if disc else None,
                     'sold_out_marked': sum(1 for p in units if p['availability'] == 'sold_out'),
                     'availability_unknown': sum(1 for p in units if p['availability'] == 'unknown'), 'run_id': run['run_id'],
                     'reg_prices': reg, 'sale_prices': sale})
    return rows


def changes(brand, prev, cur):
    if not prev:
        return []
    a = {p['product_id']: p for p in prev['products'] if p['in_clothing_scope']}
    b = {p['product_id']: p for p in cur['products'] if p['in_clothing_scope']}
    between = f"{prev['started_at'][:16]} ~ {cur['started_at'][:16]}"
    out = []

    def add(pid, kind, before, after, p):
        out.append({'brand': BRANDS[brand]['name'], 'product_id': pid, 'name': p['name'], 'category': p['category'], 'change': kind,
                    'before': before, 'after': after, 'between': between, 'url': p['url']})
    for pid in b.keys() - a.keys():
        add(pid, '최초 발견(이번 조사 기준)', '', b[pid]['sale_price'], b[pid])
    for pid in a.keys() - b.keys():
        add(pid, '목록 미노출(삭제·판매종료로 단정하지 않음)', a[pid]['sale_price'], '', a[pid])
    for pid in a.keys() & b.keys():
        x, y = a[pid], b[pid]
        if x['sale_price'] and y['sale_price'] and x['sale_price'] != y['sale_price']:
            add(pid, '판매가 변화', x['sale_price'], y['sale_price'], y)
        if (x.get('displayed_discount_pct') or 0) != (y.get('displayed_discount_pct') or 0):
            add(pid, '표시 할인율 변화(%p)', x.get('displayed_discount_pct') or 0, y.get('displayed_discount_pct') or 0, y)
        if (x['availability'] == 'sold_out') != (y['availability'] == 'sold_out') and 'unknown' not in (x['availability'], y['availability']):
            add(pid, '품절 표시 변화', x['availability'], y['availability'], y)
    pa = {(z['list_kind'], z['product_id']) for z in prev['placements']}
    pb = {(z['list_kind'], z['product_id']) for z in cur['placements']}
    names = {p['product_id']: p for p in cur['products'] + prev['products']}
    for kind, pid in pb - pa:
        add(pid, f'{kind} 상위 20 진입', '', 'in', names.get(pid, {'name': pid, 'category': None, 'url': ''}))
    for kind, pid in pa - pb:
        add(pid, f'{kind} 상위 20 이탈(전체 제외 아님)', 'in', '', names.get(pid, {'name': pid, 'category': None, 'url': ''}))
    return out


def write_csv(name, rows, cols=None):
    cols = cols or (list(rows[0].keys()) if rows else ['empty'])
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def won(v):
    return '' if v in (None, '') else f'{int(v):,}'


def esc(v):
    return html.escape('' if v is None else str(v))


def main():
    OUT.mkdir(exist_ok=True)
    reps = {b: runs_by_date(b) for b in BRANDS}
    cur = {b: reps[b][max(reps[b])] for b in BRANDS if reps[b]}
    prev = {b: reps[b][sorted(reps[b])[-2]] if len(reps[b]) > 1 else None for b in cur}
    products, cats, places, promos, covs, chg, status, events = [], [], [], [], [], [], [], []
    for b, r in cur.items():
        name = BRANDS[b]['name']
        byid = {p['product_id']: p for p in r['products']}
        for p in r['products']:
            products.append({'brand': name, 'product_id': p['product_id'], 'name': p['name'], 'category': p['category'] or '', 'in_clothing_scope': p['in_clothing_scope'],
                             'subtype': p.get('subtype') or '', 'sale_price': p['sale_price'], 'regular_price': p['regular_price'],
                             'displayed_discount_pct': p.get('displayed_discount_pct'), 'availability': p['availability'], 'audience': p.get('audience'),
                             'model_id': p.get('model_id') or '', 'season_label': p.get('season_label') or '', 'category_raw': ' | '.join(p['category_raw']),
                             'category_basis': p.get('category_basis'), 'url': p['url'], 'observed_at': p['observed_at'], 'run_id': r['run_id']})
        cats += category_rows(b, r)
        events += event_rows(b, r)
        for z in r['placements']:
            p = byid.get(z['product_id'], {})
            places.append({'brand': name, 'list_kind': z['list_kind'], 'list_name': z['list_name'], 'position': z['position'], 'product_id': z['product_id'],
                           'name': p.get('name') or z.get('name'), 'category': p.get('category') or '(목록 밖·비의류)', 'sale_price': p.get('sale_price'),
                           'sort': z['sort'], 'observed_at': z['observed_at'], 'url': z['list_url']})
        for x in r['promotions']:
            promos.append({'brand': name, 'source': x.get('source'), 'raw': x.get('raw') or x.get('error'), 'product_count': x.get('product_count'),
                           'url': x.get('url'), 'observed_at': x.get('observed_at')})
        for c in r['coverage']:
            covs.append({'brand': name, 'list': c['name'], 'expected_count': c.get('expected_count'), 'fetched_count': c.get('fetched_count'),
                         'status': c['status'], 'reason': c.get('reason', ''), 'url': c.get('url')})
        chg += changes(b, prev[b], r)
        ps = r.get('placement_status', {})
        models = sum(c['n'] for c in cats if c['brand'] == name and c['category'] == ALL)

        def shown(kind):
            x = ps.get(kind, {})
            if x.get('status') != 'observed':
                return '없음'
            label = re.sub(r'\s*\([^()]*\)|\s*\d{4}\.\d{2}\.\d{2}\s*~\s*\d{4}\.\d{2}\.\d{2}', '', x.get('list') or '').strip()
            return f'있음 ({label})' if label else '있음'
        status.append({'brand': name, 'channel': r['channel_id'],
                       'models': f'{models} (목록 일부만 읽힘)' if r['status'] == 'partial' else models,
                       'best': shown('BEST'), 'new': shown('NEW')})
    write_csv('products.csv', products)
    write_csv('category_prices.csv', cats, [k for k in cats[0] if not k.endswith('_prices')])
    write_csv('placements.csv', places)
    write_csv('promotions.csv', promos)
    write_csv('events.csv', events)
    write_csv('promo_messages.csv', message_rows(events))
    write_csv('coverage.csv', covs)
    write_csv('changes.csv', chg, ['brand', 'product_id', 'name', 'category', 'change', 'before', 'after', 'between', 'url'])
    page(status, cats, events)
    print(OUT / 'index.html')


FONT = 'https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css'
CSS = """
:root{--bg:#F5F4F0;--card:#FFFFFF;--line:#E3E1DB;--row:#EFEDE8;--soft:#EEECE6;--ink:#191A1C;--mute:#5F5E5A;--faint:#ADABA4;
--red:#FCE4E4;--red-t:#A12A27;--yel:#FBF0D2;--yel-t:#8A5A00;--blue:#E1F3FE;--blue-t:#175F8F}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-size:18px;line-height:1.5;-webkit-font-smoothing:antialiased;
font-family:'Pretendard Variable',Pretendard,'Apple SD Gothic Neo','Malgun Gothic',system-ui,sans-serif}
main{max-width:1440px;margin:0 auto;padding:56px 40px 120px}
header{margin-bottom:36px}
h1{font-size:44px;font-weight:750;letter-spacing:-0.035em;line-height:1.15;margin:0}
section{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:40px 44px 36px;margin-bottom:36px}
h2{font-size:30px;font-weight:750;letter-spacing:-0.025em;margin:0 0 28px}
.wrap{overflow-x:auto;margin:0 -12px}
table{width:100%;border-collapse:separate;border-spacing:0;font-size:20px;font-variant-numeric:tabular-nums}
th{font-size:17px;font-weight:650;color:#45443F;text-align:left;padding:14px;border-bottom:2px solid var(--line);white-space:nowrap;vertical-align:bottom}
td{padding:18px 14px;border-bottom:1px solid var(--row);vertical-align:middle;font-weight:500}
tbody tr:last-child td{border-bottom:0}
tbody tr:hover td{background:#FAFAF8}
.n{text-align:right;white-space:nowrap}
th.n{text-align:right}
.grp{text-align:center;color:var(--ink);font-size:18px;font-weight:750;border-bottom:1px solid var(--line)}
th+th,td+td,tbody.bg td:first-child:not(.bcell){border-left:1px solid #F1EFEA}
th.gl,td.gl{border-left:2px solid #D9D6CE}
.sub{display:block;font-size:16px;font-weight:500;color:var(--mute);margin-top:2px}
.dash{color:var(--faint)}
.brand{font-weight:700;white-space:nowrap}
.site{font-size:15px;color:var(--mute);font-weight:500;display:block;margin-top:2px}
b{font-weight:750}
tr.ref td{background:#FFFAEC}
tr.ref:hover td{background:#FDF5DF}
tbody.ref td{background:#FFFAEC}
.bar{height:6px;background:var(--soft);border-radius:3px;margin-top:8px;overflow:hidden}
.bar i{display:block;height:100%;background:#A9A497;border-radius:3px}
tr.ref .bar i{background:#C99A2E}
.pill{display:inline-block;font-size:18px;font-weight:700;color:var(--red-t);background:var(--red);border-radius:8px;padding:3px 11px;white-space:nowrap}
.mono{font-size:18px;color:var(--ink);white-space:nowrap}
.gap{color:var(--blue-t);font-weight:700}
.tabs{display:inline-flex;gap:4px;background:var(--soft);border-radius:12px;padding:5px;margin-bottom:28px;flex-wrap:wrap}
.tabs button{border:0;background:transparent;font:inherit;font-size:18px;font-weight:600;color:var(--mute);padding:10px 22px;border-radius:8px;cursor:pointer}
.tabs button.on{background:var(--card);color:var(--ink);font-weight:700;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.tabs button:active{transform:scale(.98)}
tbody.bg tr:first-child td{border-top:2px solid var(--line)}
tbody.bg:first-of-type tr:first-child td{border-top:0}
td.bcell{vertical-align:top;padding-top:20px}
table.promo{font-size:17px}
table.promo td{padding:10px 14px;line-height:1.4}
table.promo td.bcell{padding-top:12px}
table.promo .sub{display:inline;font-size:14px;margin:0 0 0 6px}
table.promo .pill{font-size:15px;padding:2px 9px}
table.promo .mono{font-size:16px}
.tag{display:inline-block;font-size:14px;font-weight:650;color:var(--blue-t);background:var(--blue);border-radius:7px;padding:2px 8px;margin:1px 4px 1px 0;white-space:nowrap}
.tag.kind{color:var(--yel-t);background:var(--yel)}
.note{font-size:15px;line-height:1.6;color:var(--mute);margin:14px 0 0;padding-left:18px}
.note li{margin:2px 0}
.msg-head{margin:36px 0 14px}
.dist{margin-top:44px;padding-top:36px;border-top:2px solid var(--line)}
.dhead{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:12px}
h3{font-size:23px;font-weight:750;letter-spacing:-0.02em;margin:0}
.seg{display:inline-flex;gap:4px;background:var(--soft);border-radius:12px;padding:5px}
.seg button{border:0;background:transparent;font:inherit;font-size:17px;font-weight:600;color:var(--mute);padding:8px 20px;border-radius:8px;cursor:pointer}
body:not([data-mode=sale]) .seg [data-m=reg],body[data-mode=sale] .seg [data-m=sale]{background:var(--card);color:var(--ink);font-weight:700;box-shadow:0 1px 3px rgba(0,0,0,.08)}
body:not([data-mode=sale]) .m-sale,body[data-mode=sale] .m-reg{display:none}
.sample{margin-top:36px}
h4{font-size:18px;font-weight:700;color:var(--mute);margin:0 0 14px;letter-spacing:-0.01em}
h4 b{color:var(--ink);margin-right:6px}
.drow{display:grid;grid-template-columns:150px minmax(0,1fr);gap:24px;align-items:center}
.dname{font-weight:700}
.drow.ref .dname{color:var(--yel-t)}
.axis .lab{display:grid;grid-template-columns:repeat(var(--k),1fr);font-size:15px;font-weight:500;color:var(--mute);text-align:center;white-space:nowrap;padding-top:8px}
.legend{display:flex;align-items:center;gap:3px;font-size:14px;font-weight:600;color:var(--mute);margin:0 0 12px}
.legend i{display:block;width:26px;height:12px;border-radius:3px}
.legend span{margin:0 6px}
table.hm{border-spacing:3px;margin:0 -3px;table-layout:fixed}
table.hm th,table.hm td{border:0;text-align:center;padding:0}
table.hm thead th{font-size:15px;font-weight:600;color:#45443F;padding:0 0 8px}
table.hm th.hb{text-align:left;vertical-align:middle;width:170px;font-size:18px;font-weight:700;color:var(--ink)}
table.hm th.hb small{display:block;font-size:14px;font-weight:500;color:var(--mute)}
table.hm tr.ref th.hb{color:var(--yel-t)}
table.hm td{height:62px;border-radius:6px;font-size:19px;font-weight:700;line-height:1.15}
table.hm td small{display:block;font-size:14px;font-weight:500;opacity:.78;margin-top:2px}
table.hm td.peak{box-shadow:inset 0 0 0 2px rgba(25,26,28,.55)}
table.hm td.zero{background:#FAF9F6;color:var(--faint);font-weight:400}
table.hm tr.ref th.hb::before{content:'';display:inline-block;width:4px;height:18px;border-radius:2px;background:#C99A2E;margin-right:8px;vertical-align:-3px}
table.hm tbody tr:hover td{filter:brightness(.96)}
.heat:not(.fine) .v-fine,.heat.fine .v-main{display:none}
.more{border:1px solid var(--line);background:var(--card);font:inherit;font-size:15px;font-weight:650;color:var(--ink);padding:4px 12px;border-radius:7px;cursor:pointer;margin-left:12px;vertical-align:1px}
.heat.fine .more{background:var(--ink);color:#fff;border-color:var(--ink)}
.frow{display:grid;grid-template-columns:170px repeat(var(--k),minmax(0,1fr));margin-top:4px}
.frow .hb{font-size:18px;font-weight:700;line-height:1.25;align-self:center;padding-right:8px}
.frow .hb small{display:block;font-size:14px;font-weight:500;color:var(--mute)}
.frow.ref .hb{color:var(--yel-t)}
.frow.ref .hb::before{content:'';display:inline-block;width:4px;height:18px;border-radius:2px;background:#C99A2E;margin-right:8px;vertical-align:-3px}
.frow i{display:flex;align-items:center;justify-content:center;height:46px;background:#F7F6F2}
.frow .hb+i{border-radius:8px 0 0 8px}
.frow i:last-child{border-radius:0 8px 8px 0}
.frow.ref i{background:#FFF6DE}
.frow i b{display:block;width:calc(var(--s) * 90%);max-width:40px;min-width:5px;aspect-ratio:1;border-radius:50%;background:#B07A26}
.frow i.peak b{background:#5E3C0A}
.frow i:hover{background:#ECE9E1}
.fhead{margin:0 0 4px}
.fhead .tick{font-size:14px;font-weight:600;color:#45443F;border-left:1.5px solid #D9D6CE;padding-left:3px;white-space:nowrap;overflow:hidden}
.fhead .tick.end{position:relative;border-left:0;overflow:visible}
.fhead .tick.end b{position:absolute;right:0;font-weight:600}
@media (max-width:1360px){table{font-size:18px}th{font-size:15.5px}th,td{padding-left:10px;padding-right:10px}section{padding:32px 28px 28px}main{padding:40px 20px 100px}}
.range .drow:not(.axis){padding:27px 0 30px;border-bottom:1px solid var(--row)}
.rtrack{position:relative;height:22px}
.rg{position:absolute;top:-8px;bottom:-8px;width:1px;background:#EFEDE8}
.rlab{position:relative;height:24px;margin-top:8px}
.rlab span{position:absolute;transform:translateX(-50%);font-size:15px;font-weight:500;color:var(--mute);white-space:nowrap}
.rline{position:absolute;top:50%;height:2px;margin-top:-1px;background:#A39E92;border-radius:1px}
.rbox{position:absolute;top:0;bottom:0;border-radius:6px;background:#CFCAC0}
.drow.ref .rline{background:#C99A2E}
.drow.ref .rbox{background:#E6C885}
.rmed{position:absolute;top:-5px;bottom:-5px;width:3px;margin-left:-1.5px;background:var(--ink);border-radius:2px}
.rmed span{position:absolute;bottom:100%;left:50%;transform:translateX(-50%);margin-bottom:2px;font-size:14px;font-weight:700;white-space:nowrap}
.rend{position:absolute;top:27px;font-size:13px;line-height:18px;font-weight:500;color:var(--mute);white-space:nowrap}
.ridge .drow:not(.axis),.bars .drow:not(.axis){padding:12px 0;border-bottom:1px solid var(--row)}
.ridge svg,.bars svg{display:block;width:100%;height:115px;overflow:hidden}
.bars svg rect:hover{fill:#8C6222}
.chart-note{font-size:15px;color:var(--mute);line-height:1.65;margin:10px 0 18px}
.chart-scroll{padding:8px 0 12px;min-width:0}
.chart-inner{min-width:0;width:100%}
.range .chart-inner{padding-right:12px}
.range .rtrack,.range .rlab{margin-left:10px;margin-right:10px}
.rlab span:first-child{transform:none}
.rlab span:last-child{transform:translateX(-100%)}
.dname small{display:block;font-size:13px;font-weight:500;color:var(--mute)}
.sample h4{line-height:1.7}
.sample h4 b{display:block;font-size:20px}
.rpoint{position:absolute;top:50%;width:6px;height:6px;border-radius:50%;background:#8C877C;transform:translate(-50%,-50%)}
.drow.ref .rpoint{background:#B07A26}
.qval{position:absolute;top:27px;font-size:13px;line-height:18px;font-weight:650;white-space:nowrap;color:#625B4E}
.qval.left{transform:translateX(-100%);padding-right:4px}
.qval.right{padding-left:4px}
.axis .lab span:last-child{font-weight:700}
.linear-axis{position:relative;height:27px;font-size:12px;color:var(--mute);margin-top:3px}
.linear-axis span{position:absolute;transform:translateX(-50%);white-space:nowrap}
.linear-axis span:first-child{transform:none}.linear-axis span:last-child{transform:translateX(-100%)}
.tail-note{display:block;font-size:12px;font-weight:500;color:#787265;margin-top:7px}
@media(max-width:1000px){.range .rlab .compact-hide{display:none}}
@media(max-width:700px){.dhead{flex-wrap:wrap;gap:12px}h1{font-size:32px}section{padding:24px 16px}.tabs{overflow-x:auto}.chart-note{font-size:14px}.drow{grid-template-columns:105px minmax(0,1fr);gap:10px}.dname{font-size:14px}.rlab span{font-size:11px}.qval{font-size:11px}.rend{font-size:10px}}
@media (prefers-reduced-motion:no-preference){section{opacity:0;transform:translateY(12px);transition:opacity .6s cubic-bezier(.16,1,.3,1),transform .6s cubic-bezier(.16,1,.3,1)}section.in{opacity:1;transform:none}}
"""
JS = """
document.querySelectorAll('.tabs').forEach(t=>{const ps=[...t.parentElement.querySelectorAll('.panel')];
const show=i=>{t.querySelectorAll('button').forEach((b,j)=>b.classList.toggle('on',j===i));ps.forEach((p,j)=>p.hidden=j!==i)};
t.querySelectorAll('button').forEach((b,i)=>b.onclick=()=>show(i));show(0)});
const setPriceMode=m=>{document.body.dataset.mode=m;document.querySelectorAll('.seg button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.m===m)))};
document.querySelectorAll('.seg button').forEach(b=>b.onclick=()=>setPriceMode(b.dataset.m));setPriceMode('sale');
document.querySelectorAll('.heat .more').forEach(e=>e.onclick=()=>{const h=e.closest('.heat');h.classList.toggle('fine');e.textContent=h.classList.contains('fine')?'기본 보기':'상세 보기'});
if(matchMedia('(prefers-reduced-motion: no-preference)').matches){const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}}),{threshold:.08});
document.querySelectorAll('section').forEach(s=>io.observe(s))}
"""
REF = '그레이스유'
GRAD = itertools.count()


def sub(text):
    return f'<span class="sub">{text}</span>'


def money_cell(v, cls='n'):
    return f'<td class="{cls}">{won(v) if v not in (None, "") else "<span class=dash>-</span>"}</td>'


def brand_cell(b, site=None, attrs=''):
    return f'<td class="brand"{attrs}>{esc(b)}' + (f'<span class="site">{esc(site)}</span>' if site else '') + '</td>'


def man(v):
    return f'{round(v / 1000) / 10:g}만'


HEAT = ((0, (251, 247, 238)), (.3, (242, 222, 178)), (.55, (222, 179, 102)), (.8, (176, 121, 34)), (1, (120, 74, 10)))


def heat_color(a):
    for (x0, c0), (x1, c1) in zip(HEAT, HEAT[1:]):
        if a <= x1:
            f = (a - x0) / (x1 - x0)
            return 'rgb({},{},{})'.format(*(round(u + (v - u) * f) for u, v in zip(c0, c1)))
    return 'rgb({},{},{})'.format(*HEAT[-1][1])


def dist(rows):
    """한 분류의 브랜드별 가격대 분포. 모든 브랜드가 같은 구간을 쓰고, 막대 높이는 브랜드 안 비중."""
    vals = sorted(v for c in rows for v in c['reg_prices'] + c['sale_prices'])
    if not vals:
        return ''
    # 위쪽 10%는 마지막 'n만~' 칸에 모아 극단값이 축을 늘리지 않게 한다
    top = vals[int(len(vals) * 0.9)]
    step = next((s for s in (10000, 20000, 30000, 50000, 100000, 200000) if math.ceil(top / s) - vals[0] // s <= 10), 500000)
    lo, hi = vals[0] // step * step, math.ceil(top / step) * step
    starts = list(range(lo, hi, step))
    labels = [f'{a / 10000:g}~{(a + step) / 10000:g}만' for a in starts] + ([f'{hi / 10000:g}만~'] if vals[-1] >= hi else [])
    k = len(labels)

    def counts(ps):
        c = [0] * k
        for v in ps:
            c[(v - lo) // step if v < hi else k - 1] += 1
        return c
    over = len(labels) > len(starts)

    def row(c, inner):
        return f'<div class="drow{" ref" if c["brand"] == REF else ""}"><div class="dname">{esc(c["brand"])}<small>{len(c[key]):,}모델</small></div>{inner}</div>'
    axis = (f'<div class="drow axis"><div></div><div class="lab" style="--k:{k}">'
            + ''.join(f'<span>{x}</span>' for x in labels) + '</div></div>')
    # 상세 보기: 같은 폭(step)으로 가장 비싼 제품까지 나눈다. 칸이 너무 많아지지 않게 48칸에서 자르고 나머지는 마지막 칸
    fhi = max(hi, min(vals[-1] // step * step + step, lo + 48 * step))
    fstarts = list(range(lo, fhi, step))
    fine_labels = [f'{a / 10000:g}~{(a + step) / 10000:g}만' for a in fstarts] + ([f'{fhi / 10000:g}만~'] if vals[-1] >= fhi else [])
    g = next(x for x in (1, 2, 4, 5, 10, 20) if len(fstarts) / x <= 8)
    fine_head = ''.join(f'<span class="tick" style="grid-column:span {min(g, len(fstarts) - i)}">{a / 10000:g}만</span>'
                        for i, a in enumerate(fstarts) if i % g == 0)
    if len(fine_labels) > len(fstarts):
        fine_head += f'<span class="tick end"><b>{fhi / 10000:g}만~</b></span>'
    # 가격 범위는 최저~최고 차이가 수백 배라 1·2·5 배수 눈금(로그)으로 그리고, 40만 칸에 몰지 않는다
    marks = [m * 10 ** e for e in range(3, 9) for m in (1, 2, 5)]
    ra, rb = max(t for t in marks if t <= vals[0]), min(t for t in marks if t >= vals[-1])
    if rb == ra:
        rb = ra * 2
    rticks = [t for t in marks if ra <= t <= rb]
    compact_ticks = set(range(0, len(rticks), 2)) | {len(rticks)-1}
    if len(rticks) > 2 and len(rticks)-2 in compact_ticks:
        compact_ticks.remove(len(rticks)-2)

    def x_log(v):
        return (math.log10(v) - math.log10(ra)) / (math.log10(rb) - math.log10(ra)) * 100
    rgrid = ''.join(f'<i class="rg" style="left:{x_log(t):.2f}%"></i>' for t in rticks)
    raxis = ('<div class="drow axis"><div></div><div class="rlab">'
             + ''.join(f'<span class="{"" if i in compact_ticks else "compact-hide"}" style="left:{x_log(t):.2f}%">{man(t)}</span>' for i,t in enumerate(rticks)) + '</div></div>')
    heat, strip, ridge, bars = '', '', '', ''
    # Distribution charts retain an ordinary, equal-price axis. High-price tails
    # are counted separately, never squeezed into a fake equal-width interval.
    plot_hi = max(step * 2, math.ceil(vals[min(len(vals)-1, int(len(vals)*.95))] / step) * step)
    bin_width = max(1000, step // 2)
    nbins = math.ceil(plot_hi / bin_width)
    plot_hi = nbins * bin_width
    def hist(ps):
        bins = [0] * nbins
        for v in ps:
            if v < plot_hi:
                bins[v // bin_width] += 1
        return bins
    bin_max = max((n / len(c[ky]) * 100 for c in rows for ky in ('reg_prices','sale_prices') if c[ky] for n in hist(c[ky])), default=1) or 1
    y_max = max(10, math.ceil(bin_max / 10) * 10)
    xs = [i * plot_hi / 200 for i in range(201)]
    bandwidth = bin_width * .8
    def density(ps):
        # Reflection at zero prevents the smooth display leaking into negative prices.
        return [sum(math.exp(-.5*((x-v)/bandwidth)**2)+math.exp(-.5*((x+v)/bandwidth)**2) for v in ps) / (len(ps) or 1) for x in xs]
    curves = {(i,ky):density(c[ky]) for i,c in enumerate(rows) for ky in ('reg_prices','sale_prices')}
    density_max = max((v for ds in curves.values() for v in ds), default=1) or 1
    tick_step = max(step, math.ceil(plot_hi / step / 6) * step)
    linear_ticks = sorted(set(list(range(0, plot_hi, tick_step)) + [plot_hi]))
    linear_axis = '<div class="linear-axis">' + ''.join(f'<span style="left:{v/plot_hi*100:.2f}%">{man(v)}</span>' for v in linear_ticks) + '</div>'
    def distribution_row(c, content):
        tail = sum(v >= plot_hi for v in c[key])
        info = f'<span class="tail-note">{man(plot_hi)} 이상 {tail}모델</span>' if tail else ''
        return row(c, '<div>' + content + linear_axis + '</div>').replace('</small></div>', f'</small>{info}</div>', 1)
    for mode, key in (('reg', 'reg_prices'), ('sale', 'sale_prices')):
        data = [(c, counts(c[key]), len(c[key]) or 1) for c in rows]
        mx = max(n / t for c, cs, t in data for n in cs) or 1

        def heat_table(rows_, head, m, fine=False):
            """m = 이 표에서 가장 높은 비중. 가장 진한 색의 기준이다. 상세 보기는 칸 폭이 고르게 나오도록 격자로 그린다."""
            tr = ''
            for c, cs, t in rows_:
                cells = ''
                for j, n in enumerate(cs):
                    # 0.7제곱 눈금: 낮은 비중끼리도 색 차이가 나게 한다. 같은 비중이면 브랜드가 달라도 같은 색
                    a = (n / t / m) ** 0.7
                    pct = n / t * 100
                    peak = ' class="peak"' if n == max(cs) else ''
                    if fine:
                        # 원 넓이 = 비중. 아주 작은 비중도 점으로는 보이게 최소 크기를 둔다
                        size = max(math.sqrt(n / t / m), .2)
                        cells += (f'<i{peak} tabindex="0" aria-label="{fine_labels[j]}: {n}모델 ({pct:.1f}%)" title="{fine_labels[j]}: {n}모델 ({pct:.1f}%)"><b style="--s:{size:.3f}"></b></i>' if n else '<i></i>')
                    else:
                        cells += (f'<td{peak} style="background:{heat_color(a)};color:{"#fff" if a > .74 else "var(--ink)"}" title="{n}개 ({pct:.1f}%)">'
                                  f'{"<1" if pct < 1 else f"{pct:.0f}"}%<small>{n}개</small></td>' if n else '<td class="zero">·</td>')
                name = f'{esc(c["brand"])}<small>{len(c[key])}개</small>'
                ref = ' ref' if c['brand'] == REF else ''
                tr += f'<div class="frow{ref}"><span class="hb">{name}</span>{cells}</div>' if fine else f'<tr class="{ref}"><th class="hb">{name}</th>{cells}</tr>'
            legend = ''.join(f'<i style="background:{heat_color((i / 6) ** 0.7)}"></i>' for i in range(7))
            if fine:
                legend = '<span>원 넓이 = 브랜드 안 비중 · 마우스를 올리면 개수와 %</span>'
            body = (f'<div class="fgrid" style="--k:{len(fine_labels)}"><div class="frow fhead"><span></span>{head}</div>{tr}</div>' if fine else
                    f'<table class="hm"><thead><tr><th class="hb"></th>{head}</tr></thead><tbody>{tr}</tbody></table>')
            return f'<div class="legend"><span>{"" if fine else "0%"}</span>{legend}<span>{"" if fine else f"{m * 100:.1f}%"}</span></div>{body}'

        def fine_counts(ps):
            c = [0] * len(fine_labels)
            for v in ps:
                c[(v - lo) // step if v < fhi else len(fine_labels) - 1] += 1
            return c
        fdata = [(c, fine_counts(c[key]), t) for c, cs, t in data]
        fmx = max(n / t for c, cs, t in fdata for n in cs) or 1
        heat += (f'<div class="m-{mode}"><div class="v-main">'
                 + heat_table(data, ''.join(f'<th>{x}</th>' for x in labels), mx)
                 + f'</div><div class="v-fine">{heat_table(fdata, fine_head, fmx, True)}</div></div>')

        s = ''
        for c, cs, t in data:
            ps = sorted(c[key])
            if not ps:
                s += row(c, f'<div class="rtrack">{rgrid}</div>')
                continue
            q1, med, q3 = quartiles(ps)
            x0, xa, xm, xb, x1 = (x_log(v) for v in (ps[0], q1, med, q3, ps[-1]))
            s += row(c, f'<div class="rtrack">{rgrid}'
                        f'<span class="rline" style="left:{x0:.2f}%;width:{x1 - x0:.2f}%"></span>'
                        f'<span class="rbox" style="left:{xa:.2f}%;width:{max(xb - xa, .4):.2f}%" title="가운데 50%: {won(q1)} ~ {won(q3)}원"></span>'
                        f'<span class="rmed" style="left:{xm:.2f}%"><span>중간 {man(med)}</span></span>'
                        f'<span class="rpoint" style="left:{x0:.2f}%"></span><span class="rpoint" style="left:{x1:.2f}%"></span>'
                        f'<span class="qval left" style="left:{xa:.2f}%">{man(q1)}</span><span class="qval right" style="left:{xb:.2f}%">{man(q3)}</span>'
                        f'<span class="rend" style="left:{x0:.2f}%;transform:none">최저 {man(ps[0])}</span><span class="rend" style="left:{x1:.2f}%;transform:translateX(-100%)">최고 {man(ps[-1])}</span></div>')
        strip += f'<div class="m-{mode}">{s}</div>'

        # Ridgeline density on a linear money axis, same bandwidth and height scale.
        s = ''
        for index, (c, cs, t) in enumerate(data):
            ps = sorted(c[key])
            if not ps:
                s += row(c, '<div>관측값 없음</div>')
                continue
            col = '#C99A2E' if c['brand'] == REF else '#6F6A60'
            ds = curves[index,key]
            points = ' '.join(f'{i*5:.1f},{105-d/density_max*82:.2f}' for i,d in enumerate(ds))
            gid = f'g{next(GRAD)}'
            grid = ''.join(f'<line x1="{v/plot_hi*1000:.2f}" y1="10" x2="{v/plot_hi*1000:.2f}" y2="105" stroke="#EFEDE8"/>' for v in linear_ticks)
            med = st.median(ps)
            median = (f'<line x1="{med/plot_hi*1000:.2f}" x2="{med/plot_hi*1000:.2f}" y1="18" y2="105" stroke="{col}" stroke-dasharray="3 4"/><text x="{med/plot_hi*1000+7:.2f}" y="15" font-size="13" fill="#5F5E5A">중간 {man(med)}</text>') if med < plot_hi*.9 else ''
            svg = (f'<svg viewBox="0 0 1000 115" preserveAspectRatio="none" role="img" aria-label="{esc(c["brand"])} 가격대 분포">'
                   f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop stop-color="{col}" stop-opacity=".55"/><stop offset="1" stop-color="{col}" stop-opacity=".08"/></linearGradient></defs>{grid}'
                   f'<polygon points="0,105 {points} 1000,105" fill="url(#{gid})"/><polyline points="{points}" fill="none" stroke="{col}" stroke-width="2.2"/>{median}'
                   '<line x1="0" x2="1000" y1="105" y2="105" stroke="#D9D6CE"/></svg>')
            s += distribution_row(c, svg)
        ridge += f'<div class="m-{mode}">{s}</div>'

        s = ''
        for c, cs, t in data:
            hs = hist(c[key])
            col = '#C99A2E' if c['brand'] == REF else '#A6A094'
            grid = ''.join(f'<line x1="0" x2="1000" y1="{105-n/y_max*85:.2f}" y2="{105-n/y_max*85:.2f}" stroke="#E8E5DE" stroke-dasharray="3 4"/>' + (f'<text x="998" y="{101-n/y_max*85:.2f}" text-anchor="end" font-size="12" fill="#807A6F">{n:g}%</text>' if n else '') for n in (0,y_max/2,y_max))
            rects = ''.join(f'<rect tabindex="0" x="{j/nbins*1000:.2f}" y="{105-n/t*100/y_max*85:.2f}" width="{1000/nbins:.3f}" height="{n/t*100/y_max*85:.2f}" fill="{col}" stroke="white" stroke-width=".6" aria-label="{man(j*bin_width)}~{man((j+1)*bin_width)}: {n}모델 ({n/t*100:.1f}%)"><title>{man(j*bin_width)} 이상 {man((j+1)*bin_width)} 미만: {n}모델 ({n/t*100:.1f}%)</title></rect>' for j,n in enumerate(hs))
            peak = hs.index(max(hs))
            peak_x = max(55, min(945, (peak+.5)/nbins*1000))
            peak_label = f'<text x="{peak_x:.2f}" y="{100-max(hs)/t*100/y_max*85:.2f}" text-anchor="middle" font-size="13" font-weight="700" fill="#514B40">{max(hs)/t*100:.1f}% · {max(hs)}모델</text>' if max(hs) else ''
            svg = f'<svg viewBox="0 0 1000 115" preserveAspectRatio="none" role="img" aria-label="{esc(c["brand"])} 가격대별 상품 비중">{grid}{rects}{peak_label}</svg>'
            s += distribution_row(c, svg)
        bars += f'<div class="m-{mode}">{s}</div>'

    def sample(cls, title, note, body):
        return f'<div class="sample {cls}"><h4><b>{title}</b>{note}</h4><div class="chart-scroll"><div class="chart-inner">{body}</div></div></div>'
    return ('<div class="dist"><div class="dhead"><h3>가격대 분포</h3><div class="seg">'
            '<button type="button" data-m="reg">정가 기준*</button><button type="button" data-m="sale">판매가</button></div></div>'
            '<p class="chart-note">선택한 카테고리 · 색상 묶음 모델당 1표 · 모델 내 최저 판매가 대표값 · 품절 포함.<br>'
            '*현재 집계는 정가가 없으면 판매가를 대신 사용합니다. 매출·판매량이 아닌 등록 상품 구성입니다. '
            '브랜드별 표본 수와 수집 범위 차이를 함께 보세요.</p>'
            + sample('heat', '1. 어디에 집중돼 있나 · 가격대별 비중', '브랜드마다 합계 100% · 표에서 가장 큰 비중이 가장 진한 색 · 테두리 = 브랜드별 최다 구간<button type="button" class="more">상세 보기</button>', heat)
            + sample('range', '2. 보통 얼마인가 · 중앙 가격대와 전체 범위', '선 = 실제 최저~최고 · 상자 = 중간 50% · 세로선 = 중앙값. 가로축은 로그: 같은 거리는 같은 가격 배수이며 같은 원 차이가 아닙니다.', strip + raxis)
            + sample('ridge', '3. 어느 가격대에 몰려 있나 · 분포 곡선', f'봉우리가 높을수록 해당 가격대에 집중됩니다. 동일 가격 간격·동일 평활 폭의 비중 추정 곡선. {man(plot_hi)} 이상은 왼쪽에 별도 집계.', ridge)
            + sample('bars', '4. 가격대별 상품 비중 · 히스토그램', f'막대 하나 = {man(bin_width)}원 구간 · 높이 = 브랜드 내 비중 · 모든 브랜드 같은 눈금. 마우스를 올리면 개수와 비중을 확인할 수 있습니다. {man(plot_hi)} 이상은 별도 집계.', bars) + '</div>')


def message_summary(events):
    """브랜드별 행사 문구 분류 요약. 분모는 행사 문구 수이며 상품 수·노출 크기는 반영하지 않는다."""
    codes = [c for c, _ in MSG_CODES]
    head = ''.join(f'<th class="n{" gl" if i == 0 else ""}">{esc(h)}</th>' for i, h in enumerate(['가격형', '비가격형', '분류 불가'] + codes))
    body = ''
    for b in dict.fromkeys(e['brand'] for e in events):
        infos = [message_info(e['event']) for e in events if e['brand'] == b and e['event'] != PLAIN_DISCOUNT]
        n = len(infos) or 1

        def cell(c, gl=False):
            return f'<td class="n{" gl" if gl else ""}">{c}{sub(f"{round(c / n * 100)}%")}</td>'
        cells = ''.join(cell(sum(k == label for k, _ in infos), i == 0) for i, label in enumerate(['가격형', '비가격형', '분류 불가']))
        cells += ''.join(cell(sum(code in cs for _, cs in infos)) for code in codes)
        body += f'<tr class="{"ref" if b == REF else ""}">{brand_cell(b)}<td class="n">{len(infos)}</td>{cells}</tr>'
    return ('<h3 class="msg-head">행사 문구 유형</h3><div class="wrap"><table><thead><tr><th>브랜드</th><th class="n">행사 문구 수</th>'
            f'{head}</tr></thead><tbody>{body}</tbody></table></div>'
            '<ul class="note"><li>행사 문구 수 기준입니다. 상품 수와 화면에서 차지하는 크기는 반영하지 않습니다. 한 문구가 여러 유형에 속할 수 있어 합이 100%를 넘을 수 있습니다.</li>'
            '<li>읽은 곳은 행사 메뉴·메인 문구·팝업·배너 링크뿐입니다. 배송·적립·사은품 같은 비가격형 문구는 수집 대상이 아니어서, 0건은 "없음"이 아니라 "확인 안 됨"입니다.</li>'
            '<li>분류는 문구에 적힌 말만 보는 키워드 규칙입니다(<code>build.py</code>의 <code>MSG_CODES</code>). 효과나 의도는 판단하지 않습니다. "SEASON OFF"는 시즌 단어가 있어도 신상·시간성으로 세지 않았습니다.</li>'
            '<li>"프로모션 표시 없이 할인" 줄은 문구가 아니라 상품에 표시된 할인이라 이 요약에서 뺐습니다.</li></ul>')


def page(status, cats, events):
    s = [f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
         f'<title>그레이스유 비교</title><link rel="stylesheet" href="{FONT}"><style>{CSS}</style></head><body><main>',
         '<header><h1>그레이스유 비교</h1></header>',
         '<section><h2>상품 구성</h2><div class="wrap"><table><thead><tr><th>브랜드</th>'
         + ''.join(f'<th class="n">{esc(c)}</th>' for c in CATEGORIES) + '<th class="n gl">합계</th><th class="n">할인 제품 수</th></tr></thead><tbody>']
    for x in status:
        rows = {c['category']: c for c in cats if c['brand'] == x['brand']}
        tot = rows[ALL]['n'] or 1
        disc = rows[ALL]['discount_models']
        cells = ''
        for cat in CATEGORIES:
            n = rows[cat]['n'] if cat in rows else 0
            cells += f'<td class="n">{n}{sub(f"{round(n / tot * 100)}%")}<div class="bar"><i style="width:{n / tot * 100:.1f}%"></i></div></td>'
        s.append(f'<tr class="{"ref" if x["brand"] == REF else ""}">{brand_cell(x["brand"], x["channel"])}{cells}'
                 f'<td class="n gl"><b>{x["models"]}</b></td><td class="n">{disc}{sub(f"{disc / tot * 100:.1f}%")}</td></tr>')
    s.append('</tbody></table></div></section>')

    s.append('<section><h2>가격</h2><div class="tabs">' + ''.join(f'<button type="button">{esc(c)}</button>' for c in [ALL] + CATEGORIES) + '</div>')
    for cat in [ALL] + CATEGORIES:
        body = ''
        for c in (c for c in cats if c['category'] == cat):
            lo, hi = c['discount_min_pct'], c['discount_max_pct']
            rate = '<span class="dash">-</span>' if lo is None else f'<span class="pill">{lo:g}%</span>' if lo == hi else f'<span class="pill">{lo:g}~{hi:g}%</span>'
            gap = c['median_gap']
            body += (f'<tr class="{"ref" if c["brand"] == REF else ""}">{brand_cell(c["brand"])}<td class="n">{c["n"]}</td>'
                     + money_cell(c['regular_min'], 'n gl') + money_cell(c['regular_median']) + money_cell(c['regular_max'])
                     + money_cell(c['sale_min'], 'n gl') + money_cell(c['sale_median']) + money_cell(c['sale_max'])
                     + f'<td class="n gl">{f"<span class=gap>{won(gap)}</span>" if gap else "<span class=dash>0</span>"}</td>'
                     + f'<td class="n gl">{c["discount_models"]}{sub(f"{c['discount_models'] / c['n'] * 100:.1f}%" if c['n'] else "-")}</td><td class="n">{rate}</td></tr>')
        s.append('<div class="panel"><div class="wrap"><table><thead><tr><th rowspan="2">브랜드</th><th rowspan="2" class="n">제품 수</th>'
                 '<th colspan="3" class="grp gl">정가</th><th colspan="3" class="grp gl">판매가</th>'
                 '<th rowspan="2" class="n gl">중간가 차이</th><th rowspan="2" class="n gl">할인 제품 수</th><th rowspan="2" class="n">할인율</th></tr>'
                 '<tr><th class="n gl">최저</th><th class="n">중간</th><th class="n">최고</th><th class="n gl">최저</th><th class="n">중간</th><th class="n">최고</th></tr></thead>'
                 f'<tbody>{body}</tbody></table></div>{dist([c for c in cats if c["category"] == cat])}</div>')
    s.append('</section>')

    s.append('<section><h2>프로모션</h2><div class="wrap"><table class="promo"><thead><tr><th>브랜드</th><th>프로모션</th>'
             '<th>구분</th><th>메시지 유형</th><th class="n">적용 제품 수</th><th class="n">할인율</th><th>기간</th></tr></thead>')
    for b in dict.fromkeys(e['brand'] for e in events):
        rows = [e for e in events if e['brand'] == b]
        s.append(f'<tbody class="bg{" ref" if b == REF else ""}">')
        for i, e in enumerate(rows):
            head = brand_cell(b, attrs=f' rowspan="{len(rows)}"').replace('class="brand"', 'class="brand bcell"') if i == 0 else ''
            n = '<span class="dash">-</span>' if e['models'] is None else f"{e['models']}{sub(f'{e['models'] / e['total'] * 100:.1f}%')}"
            rate = f'<span class="pill">{esc(e["discount"])}</span>' if e['discount'] and e['discount'] != '할인 표시 없음' else f'<span class="dash">{esc(e["discount"]) or "-"}</span>'
            per = f'<span class="mono">{esc(e["period"])}</span>' if e['period'] != '-' else '<span class="dash">-</span>'
            kind, codes = message_info(e['event'])
            kind_cell = f'<span class="tag kind">{esc(kind)}</span>' if kind != '-' else '<span class="dash">-</span>'
            code_cell = ''.join(f'<span class="tag">{esc(c)}</span>' for c in codes) or '<span class="dash">-</span>'
            s.append(f'<tr>{head}<td>{esc(e["event"])}</td><td>{kind_cell}</td><td>{code_cell}</td><td class="n">{n}</td><td class="n">{rate}</td><td>{per}</td></tr>')
        s.append('</tbody>')
    s.append('</table></div>')
    s.append(message_summary(events))
    s.append('</section></main><script>' + JS + '</script></body></html>')
    # 화면에서는 분류 이름을 짧게 보인다 (CSV·데이터 값은 그대로)
    (OUT / 'index.html').write_text('\n'.join(s).replace('상의(니트 제외)', '상의'), encoding='utf-8')


if __name__ == '__main__':
    main()
