"""수집 원본(JSON)으로 CSV와 웹페이지를 만든다. 원본만 읽고, 결과 파일은 손으로 고치지 않는다.
  python monitor/build.py
결과: monitor/out/index.html (인터넷 없이 표가 보임. 상품 사진만 원본 주소에서 불러옴), monitor/out/*.csv (UTF-8 BOM)
브랜드별 대표 실행 = 가장 최근 날짜의 마지막 complete 실행(없으면 partial을 쓰고 표시). 변화는 그 이전 날짜의 대표 실행과 비교한다.
"""
import csv
import html
import json
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect import BRANDS, CATEGORIES, ROOT, now  # noqa: E402

OUT = Path(__file__).resolve().parent / 'out'
MON = ROOT / 'snapshots' / 'monitor'


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


def model_units(products):
    """오르처럼 품번이 확인된 곳은 모델당 1표(확인된 최저 판매가), 나머지는 페이지(색상별 상품) 단위."""
    units, by_model = [], {}
    for p in products:
        if p.get('model_id'):
            by_model.setdefault(p['model_id'], []).append(p)
        else:
            units.append(p)
    for ps in by_model.values():
        units.append(min(ps, key=lambda p: p['sale_price'] or 10 ** 9))
    return units, ('모델(품번)' if by_model else '페이지(색상별)')


def category_rows(brand, run):
    rows = []
    clothing = [p for p in run['products'] if p['in_clothing_scope'] and p['sale_price']]
    for cat in CATEGORIES:
        ps = [p for p in clothing if p['category'] == cat]
        units, unit = model_units(ps)
        sale = [p['sale_price'] for p in units]
        q1, med, q3 = quartiles(sale)
        reg = [p['regular_price'] or p['sale_price'] for p in units]
        disc = [p for p in units if p.get('displayed_discount_pct')]
        rows.append({'brand': BRANDS[brand]['name'], 'category': cat, 'unit': unit, 'n': len(units), 'pages': len(ps),
                     'sale_median': med, 'sale_q1': q1, 'sale_q3': q3, 'regular_median': st.median(reg) if reg else None,
                     'discount_share_pct': round(len(disc) / len(units) * 100) if units else None,
                     'discount_median_pct': st.median([p['displayed_discount_pct'] for p in disc]) if disc else None,
                     'sold_out_marked': sum(1 for p in units if p['availability'] == 'sold_out'),
                     'availability_unknown': sum(1 for p in units if p['availability'] == 'unknown'), 'run_id': run['run_id']})
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


def latest_details():
    files = sorted((MON / 'details').glob('*/*.json'))
    return json.loads(files[-1].read_text(encoding='utf-8')) if files else None


def won(v):
    return '' if v in (None, '') else f'{int(v):,}'


def esc(v):
    return html.escape('' if v is None else str(v))


def table(rows, cols, money=()):
    head = ''.join(f'<th>{esc(c[1])}</th>' for c in cols)
    body = ''.join('<tr>' + ''.join(f'<td class="{"n" if k in money else ""}">{won(r.get(k)) if k in money else esc(r.get(k))}</td>' for k, _ in cols) + '</tr>'
                   for r in rows)
    return f'<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def main():
    OUT.mkdir(exist_ok=True)
    reps = {b: runs_by_date(b) for b in BRANDS}
    cur = {b: reps[b][max(reps[b])] for b in BRANDS if reps[b]}
    prev = {b: reps[b][sorted(reps[b])[-2]] if len(reps[b]) > 1 else None for b in cur}
    products, cats, places, promos, covs, chg, status = [], [], [], [], [], [], []
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
        status.append({'brand': name, 'channel': r['channel_id'], 'run': r['started_at'][:16].replace('T', ' '), 'status': r['status'],
                       'fetched': r['fetched_count'], 'clothing': r['clothing_count'], 'failed': len(r['failed_urls']),
                       'best': ps.get('BEST', {}).get('status'), 'new': ps.get('NEW', {}).get('status'),
                       'best_note': ps.get('BEST', {}).get('list') or ps.get('BEST', {}).get('evidence'),
                       'compare': f"이전 {prev[b]['started_at'][:10]}" if prev[b] else '비교 불가(기준선)'})
    det = latest_details()
    pairs = []
    if det:
        smp = {(s['brand'], s['product_id']): s for s in det['samples']}
        for pr in det['pairs']:
            g, o = smp[('graceu', pr['graceu_product_id'])], smp[(pr['brand'], pr['product_id'])]
            pairs.append({'graceu': g['name'], 'graceu_price': g['sale_price'], 'graceu_material': ' / '.join(g.get('materials_raw') or []) or '미확인',
                          'brand': BRANDS[pr['brand']]['name'], 'product': o['name'], 'price': o['sale_price'],
                          'material': ' / '.join(o.get('materials_raw') or []) or '미확인', 'category': g['category'],
                          'price_diff_pct': pr['price_diff_pct'], 'overlap': '; '.join(pr['overlap']), 'differences': '; '.join(pr['differences']),
                          'graceu_url': g['url'], 'url': o['url'], 'graceu_img': g.get('image_url'), 'img': o.get('image_url'),
                          'graceu_reason': g.get('selection_reason'), 'reason': o.get('selection_reason')})
    write_csv('products.csv', products)
    write_csv('category_prices.csv', cats)
    write_csv('placements.csv', places)
    write_csv('promotions.csv', promos)
    write_csv('coverage.csv', covs)
    write_csv('changes.csv', chg, ['brand', 'product_id', 'name', 'category', 'change', 'before', 'after', 'between', 'url'])
    write_csv('detail_pairs.csv', pairs, [k for k in (pairs[0] if pairs else {'empty': 1}) if not k.endswith('img')])
    page(status, cats, places, promos, pairs, chg, covs, det)
    print(OUT / 'index.html')


CSS = """body{font-family:'Malgun Gothic',system-ui,sans-serif;margin:24px;color:#222;max-width:1400px}h1{font-size:22px}h2{margin-top:36px;border-bottom:2px solid #222;padding-bottom:4px}
table{border-collapse:collapse;font-size:13px;margin:8px 0}th,td{border:1px solid #ddd;padding:4px 8px;vertical-align:top}th{background:#f4f4f4;position:sticky;top:0}
td.n{text-align:right;white-space:nowrap}.note{color:#666;font-size:13px}.pair{display:grid;grid-template-columns:110px 1fr 110px 1fr;gap:8px;border:1px solid #ddd;padding:8px;margin:8px 0;font-size:13px}
.pair img{width:100px;height:130px;object-fit:cover;background:#eee}.tag{display:inline-block;background:#eef;border-radius:3px;padding:0 4px;margin:1px}nav a{margin-right:12px}"""


def page(status, cats, places, promos, pairs, chg, covs, det):
    s = [f'<!doctype html><html lang="ko"><meta charset="utf-8"><title>그레이스유 비교 관찰</title><style>{CSS}</style><body>',
         '<h1>그레이스유 · 비교 4곳 관찰 (공개 화면 기준)</h1>',
         f'<p class="note">생성 {esc(now()[:16])} · 판매량·매출은 다루지 않는다. 가격은 누구나 보는 화면 판매가이며 실결제가가 아니다. BEST/NEW는 노출 위치이지 판매 순위가 아니다.</p>',
         '<nav><a href="#status">수집 현황</a><a href="#mix">상품 구성</a><a href="#price">카테고리 가격</a><a href="#pairs">비슷한 상품</a><a href="#place">BEST/NEW</a>'
         '<a href="#promo">행사</a><a href="#chg">날짜별 변화</a><a href="#files">CSV</a></nav>',
         '<h2 id="status">수집 현황</h2>',
         table(status, [('brand', '브랜드'), ('channel', '판매처'), ('run', '수집 시각'), ('status', '상태'), ('fetched', '읽은 상품'), ('clothing', '여성 의류'),
                        ('failed', '실패 URL'), ('best', 'BEST'), ('new', 'NEW'), ('best_note', 'BEST 영역'), ('compare', '변화 비교')]),
         '<p class="note">complete = 지정 목록을 끝까지 읽음. 오르 표시 개수는 공개 JSON 기준(관리용 개수는 비공개 상품 포함이라 쓰지 않음). 제이제이지고트는 그룹몰 브랜드관 표시 total과 비교.</p>',
         '<h2 id="mix">상품 구성 (여성 의류, 공통 6분류)</h2>']
    brands = [x['brand'] for x in status]
    mix = []
    for b in brands:
        rows = [c for c in cats if c['brand'] == b]
        tot = sum(c['pages'] for c in rows) or 1
        mix.append({'brand': b, **{c['category']: f"{c['pages']} ({round(c['pages'] / tot * 100)}%)" for c in rows}})
    s.append(table(mix, [('brand', '브랜드')] + [(c, c) for c in CATEGORIES]))
    s.append('<p class="note">페이지(색상별 상품) 수 기준. 상품 수 비중은 운영 비중의 단서일 뿐 매출 비중이 아니다. 세트·홈웨어·잡화·미분류는 제외.</p>')
    s.append('<h2 id="price">카테고리 가격 (화면 판매가)</h2>')
    for cat in CATEGORIES:
        s.append(f'<h3>{esc(cat)}</h3>')
        s.append(table([c for c in cats if c['category'] == cat],
                       [('brand', '브랜드'), ('n', '상품 수'), ('unit', '단위'), ('sale_q1', '판매가 Q1'), ('sale_median', '판매가 중앙'), ('sale_q3', '판매가 Q3'),
                        ('regular_median', '정가 중앙'), ('discount_share_pct', '할인 표시 %'), ('discount_median_pct', '할인율 중앙 %'),
                        ('sold_out_marked', '품절 표시'), ('availability_unknown', '품절 미확인')],
                       money=('sale_q1', 'sale_median', 'sale_q3', 'regular_median')))
    s.append('<p class="note">정가 중앙은 정가 표시가 없으면 판매가로 대신한다. 품절 미확인 = 목록에서 상태가 안 읽힘(품절 아님과 다름).</p>')
    s.append('<h2 id="pairs">비슷한 상품 (그레이스유 표본 기준)</h2>')
    if det:
        s.append(f'<p class="note">표본 실행 {esc(det["run_id"])}. 같은 공통 분류에서 이름의 형태어(가디건·코트·미니 등)가 겹치고 판매가가 가까운 상품을 골랐다. '
                 '유사도 점수가 아니다. 소재는 상세 글자(그레이스유는 상품정보고시 이미지 판독)에서만 읽었다.</p>')
        for g in dict.fromkeys(p['graceu'] for p in pairs):
            rows = [p for p in pairs if p['graceu'] == g]
            r0 = rows[0]
            s.append(f'<h3>{esc(g)} · {won(r0["graceu_price"])}원 · {esc(r0["category"])}</h3><p class="note">선정: {esc(r0["graceu_reason"])} · 소재: {esc(r0["graceu_material"])}</p>')
            for p in rows:
                s.append(f'<div class="pair"><img src="{esc(p["graceu_img"])}" loading="lazy" alt=""><div><a href="{esc(p["graceu_url"])}">그레이스유</a> {won(p["graceu_price"])}원</div>'
                         f'<img src="{esc(p["img"])}" loading="lazy" alt=""><div><b>{esc(p["brand"])}</b> <a href="{esc(p["url"])}">{esc(p["product"])}</a><br>'
                         f'{won(p["price"])}원 ({p["price_diff_pct"]:+}%) · 소재: {esc(p["material"])}<br>겹침: {esc(p["overlap"])}<br>차이: {esc(p["differences"])}'
                         f'<br><span class="note">{esc(p["reason"])}</span></div></div>')
        um = det.get('unmatched', [])
        if um:
            s.append(f'<p class="note">짝을 못 찾은 경우 {len(um)}건: ' + '; '.join(f"{BRANDS[u['brand']]['name']} - {u['reason']}" for u in um[:12]) + '</p>')
    else:
        s.append('<p>표본 실행 없음</p>')
    s.append('<h2 id="place">BEST/NEW 노출 (상위 20, 원래 위치)</h2>')
    s.append(table(places, [('brand', '브랜드'), ('list_kind', '영역'), ('list_name', '목록'), ('position', '위치'), ('name', '상품'), ('category', '분류'),
                            ('sale_price', '판매가'), ('sort', '정렬')], money=('sale_price',)))
    s.append('<h2 id="promo">공개 행사 (메인 화면·행사 메뉴 원문)</h2>')
    s.append(table(promos, [('brand', '브랜드'), ('source', '출처'), ('raw', '원문'), ('product_count', '상품 수'), ('observed_at', '확인 시각')]))
    s.append('<p class="note">문구를 그대로 옮긴 것이며 조건·기간은 원문에 적힌 것만 있다. 이미지에만 있는 행사 문구는 대체텍스트가 없으면 빠질 수 있다.</p>')
    s.append('<h2 id="chg">날짜별 변화</h2>')
    s.append(table(chg, [('brand', '브랜드'), ('change', '변화'), ('name', '상품'), ('category', '분류'), ('before', '이전'), ('after', '이후'), ('between', '확인 구간')])
             if chg else '<p>이전 날짜 수집이 없어 <b>비교 불가(기준선)</b>. 다음 수집부터 가격·할인·품절 표시·BEST/NEW 진입/이탈·최초 발견을 보여 준다.</p>')
    s.append('<h2 id="files">CSV (엑셀용)</h2><ul>' + ''.join(f'<li><a href="{n}">{n}</a></li>' for n in
             ('products.csv', 'category_prices.csv', 'detail_pairs.csv', 'placements.csv', 'promotions.csv', 'changes.csv', 'coverage.csv')) + '</ul>')
    s.append('<details><summary>목록별 수집 범위</summary>' + table(covs, [('brand', '브랜드'), ('list', '목록'), ('expected_count', '표시 수'),
                                                                     ('fetched_count', '읽은 수'), ('status', '상태'), ('reason', '사유')]) + '</details></body></html>')
    (OUT / 'index.html').write_text('\n'.join(s), encoding='utf-8')


if __name__ == '__main__':
    main()
