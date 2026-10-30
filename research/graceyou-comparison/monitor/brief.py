"""그레이스유 공식몰과 비교 브랜드의 가격·할인·구성 분석 페이지. build.py가 만든 out/*.csv와 최신 수집 원본만 읽는다.
  python monitor/brief.py                      # monitor/out/brief.html (파일 하나로 열리는 독립 HTML)
  python monitor/brief.py --artifact 경로.html  # 같은 내용을 문서 골격 없이 (Artifact 게시용)
화면 문구는 라벨만 둔다. 자세한 값은 마우스를 올렸을 때 툴팁(data-tip)으로 보인다.
"""
import csv
import html
import json
import math
import re
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import model_key, model_units, runs_by_date  # noqa: E402  먼저: collect가 tools/를 경로 앞에 넣어 같은 이름의 tools/build.py가 잡힌다
from collect import BRANDS, ROOT  # noqa: E402

OUT = Path(__file__).resolve().parent / 'out'
DATA = ROOT / 'data'
REF = 'graceu'
ORDER = ['graceu', 'kume', 'nw', 'jj', 'orr', 'lamerei', 'voyonn']
CATS = ['상의(니트 제외)', '니트·가디건', '원피스', '아우터', '스커트', '팬츠']
CAT_SHORT = {'상의(니트 제외)': '상의', '니트·가디건': '니트·가디건', '원피스': '원피스', '아우터': '아우터', '스커트': '스커트', '팬츠': '팬츠'}
POLICY_KEY = {'graceu': 'gu'}
WC_CD = {'graceu': 108809, 'kume': 102698, 'nw': 103899, 'jj': 113480, 'lamerei': 109224, 'voyonn': 105721}
# 데이터만으로는 이유를 알 수 없는 변화에 사람이 확인한 한 줄 (브랜드, 비교 끝 날짜)
CHANGE_NOTES = {
    ('orr', '2026-10-30'): '1차·2차·TIME SALE 종료',
    ('graceu', '2026-10-30'): 'HAZLE DOWN 33% OFF 종료',
}


def rows(name):
    return list(csv.DictReader(open(OUT / name, encoding='utf-8-sig')))


def esc(x):
    return html.escape(str(x), quote=True)


def man(v, d=1):
    """원 → '21.9' (만 원 단위 숫자만)."""
    t = f'{v / 10000:.{d}f}'
    return t.rstrip('0').rstrip('.') if '.' in t else t


def won(v):
    return f'{int(round(v)):,}원'


def num(x):
    return float(x) if x not in (None, '') else None


def tip(*lines):
    return esc('|'.join(x for x in lines if x))


def latest(brand):
    reps = runs_by_date(brand)
    return reps[max(reps)]


def collect_facts():
    name = {b: BRANDS[b]['name'] for b in ORDER}
    by = {}
    for r in rows('category_prices.csv'):
        b = next(k for k, v in name.items() if v == r['brand'])
        by.setdefault(b, {})[r['category']] = r
    runs = {b: latest(b) for b in ORDER}
    policy = json.loads((DATA / 'shop_policy.json').read_text(encoding='utf-8'))['brands']
    hearts = {int(r['brand_cd']): (int(r['heart_count']), int(r['rank'])) for r in csv.DictReader(open(DATA / 'wconcept-brand-hearts-2026-10-27.csv', encoding='utf-8-sig'))}
    gu = [p for p in runs[REF]['products'] if p['in_clothing_scope']]
    mats = json.loads((Path(__file__).resolve().parent / 'materials.json').read_text(encoding='utf-8'))[REF]
    text_ok = lambda r: r['status'] == 'observed' and (r.get('source') or '').startswith('detail_text')  # noqa: E731
    recs = sorted(mats.values(), key=lambda r: int(r['product_id']))
    days = sorted(runs_by_date(REF))
    return dict(name=name, by=by, runs=runs, policy=policy, hearts=hearts, gu_pages=len(gu),
                gu_sold=sum(p['availability'] == 'sold_out' for p in gu),
                gu_pre=sum('PRE-ORDER' in p['category_raw'] for p in gu), gu_cer=sum('CEREMONY' in p['category_raw'] for p in gu),
                mat_newest=len(recs[-30:]), mat_newest_img=sum(not text_ok(r) for r in recs[-30:]),
                mat_older=len(recs[:-30]), mat_older_text=sum(text_ok(r) for r in recs[:-30]),
                changes=rows('changes.csv'), date=days[-1], prev=days[-2] if len(days) > 1 else None, events=rows('events.csv'))


def mix(c1, c2, t):
    a, b = [int(c1[i:i + 2], 16) for i in (1, 3, 5)], [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return '#' + ''.join(f'{round(x + (y - x) * t):02x}' for x, y in zip(a, b))


# 그레이스유보다 싸면 청회색, 비싸면 클레이. 가운데는 바탕에 가까운 중립
LOW, MID, HIGH = '#5C7A99', '#F3F1EE', '#B5744A'
SEQ0, SEQ1 = '#F6F2F0', '#7A4E5C'


def diverge(r):
    t = max(-1, min(1, math.log(r) / math.log(1.8)))
    return mix(MID, HIGH, t) if t > 0 else mix(MID, LOW, -t)


def ink_on(bg):
    r, g, b = (int(bg[i:i + 2], 16) for i in (1, 3, 5))
    return '#FFFFFF' if (0.299 * r + 0.587 * g + 0.114 * b) < 150 else 'var(--ink)'


def page(f, standalone):
    name, by = f['name'], f['by']
    tot = {b: by[b]['전체'] for b in ORDER}
    sale = {b: num(tot[b]['sale_median']) for b in ORDER}
    reg = {b: num(tot[b]['regular_median']) or sale[b] for b in ORDER}
    share = {b: num(tot[b]['discount_share_pct']) or 0 for b in ORDER}
    dmed = {b: num(tot[b]['discount_median_pct']) or 0 for b in ORDER}
    n = {b: int(tot[b]['n']) for b in ORDER}
    pol = {b: f['policy'].get(POLICY_KEY.get(b, b), {}) for b in ORDER}

    # ---------- 가격 포지션: 0원부터 모든 브랜드 공통 눈금, 최저~최고 막대 + 가운데 50% 박스 + 중앙값 (할인가 / 정가 / 함께) ----------
    units = {b: sorted(model_units(b, [p for p in f['runs'][b]['products'] if p['in_clothing_scope'] and p['sale_price']]), key=lambda p: p['sale_price']) for b in ORDER}
    reg_of = lambda p: p['regular_price'] if p.get('regular_price') and p['regular_price'] > p['sale_price'] else p['sale_price']  # noqa: E731

    def qstats(vals):
        vs = sorted(vals)
        q = st.quantiles(vs, n=4, method='inclusive') if len(vs) >= 4 else [vs[0], st.median(vs), vs[-1]]
        return vs[0], q[0], q[1], q[2], vs[-1]
    S = {'sale': {b: qstats([p['sale_price'] for p in units[b]]) for b in ORDER}, 'reg': {b: qstats([reg_of(p) for p in units[b]]) for b in ORDER}}
    # 눈금: 기본은 모든 브랜드 중 가장 비싼 상품(현재 그레이스유 1,260만 원)을 기준으로 0원부터. 확대는 브랜드별 상위 5% 가격 중 가장 큰 값까지(그보다 비싼 소수는 화살표)
    pmax = max(max(S['sale'][b][4], S['reg'][b][4]) for b in ORDER)
    top95 = max(sorted(reg_of(p) for p in units[b])[min(len(units[b]) - 1, int(len(units[b]) * .95))] for b in ORDER)
    price_modes = ''
    for scale in ('full', 'zoom'):
        if scale == 'full':
            TS = next(t for t in (100000, 200000, 500000, 1000000, 2000000, 5000000) if math.ceil(pmax / t) <= 7)
            AX = pmax  # 여유 없이 최고가가 눈금의 끝
        else:
            TS = 100000 if top95 <= 1000000 else 200000
            AX = max(300000, math.ceil(top95 / TS) * TS)
        pos = lambda v, AX=AX: min(v, AX) / AX * 100  # noqa: E731
        ticks = list(range(0, AX + 1, TS))
        if scale == 'full':  # 끝 눈금은 최고가 자체. 바로 앞 눈금과 글자가 겹치면 앞 눈금을 비운다
            ticks = [t for t in ticks if t == 0 or AX - t >= AX * .08] + [AX]
        gl = ''.join(f'<i class="gl" style="left:{pos(t):.2f}%"></i>' for t in ticks if t)
        axis = ''.join(f'<i style="left:{pos(t):.2f}%">{t // 10000}</i>' for t in ticks)
        HEAD = f'<div class="ph"><span></span><div class="axis">{axis}</div><span class="pv">중앙값</span></div>'

        def bar(x, cls='', lab=False, ends=True, tag='', pos=pos, AX=AX):
            mn, q1, md, q3, mx = x
            over = mx > AX
            return (f'<span class="bar {cls}"><span class="rail" style="left:{pos(mn):.2f}%;width:{pos(mx) - pos(mn):.2f}%"></span>'
                    f'<i class="cap" style="left:{pos(mn):.2f}%"></i><i class="cap" style="left:{pos(mx):.2f}%"></i>'
                    f'<span class="box" style="left:{pos(q1):.2f}%;width:{max(pos(q3) - pos(q1), .5):.2f}%"></span>'
                    f'<span class="med" style="left:{pos(md):.2f}%"></span>' + (f'<span class="mdl" style="left:{pos(md):.2f}%">{man(md)}</span>' if lab else '') +
                    ((f'<span class="lo2" style="left:{pos(mx):.2f}%">{man(mn)} ~ {man(mx)}</span>' if pos(mx) - pos(mn) < 20 else
                      f'<span class="lo" style="left:{pos(mn):.2f}%">{man(mn)}</span>'
                      f'<span class="hi" style="left:{pos(mx):.2f}%">{man(mx)}{"<em>▸</em>" if over else ""}</span>') if ends else '')
                    + (f'<span class="tg">{tag}</span>' if tag else '') + '</span>')
        for mode, label in (('sale', '할인가'), ('reg', '정가')):
            sts = S[mode]
            order = [REF] + sorted([b for b in ORDER if b != REF], key=lambda b: -sts[b][2])
            rows_db = ''
            for i, b in enumerate(order):
                x = sts[b]
                mt = tip(f'{name[b]} · {label}', f'최저 {won(x[0])} · 최고 {won(x[4])}', f'가운데 50% {won(x[1])} ~ {won(x[3])}', f'중앙값 {won(x[2])}', f'상품 {len(units[b])}개')
                rows_db += (f'<div class="pr{" me" if b == REF else ""}" style="--i:{i}" tabindex="0" data-tip="{mt}"><span class="pn">{esc(name[b])}</span>'
                            f'<div class="plot">{gl}{bar(x, "", True)}</div><span class="pv">{man(x[2])}</span></div>')
            price_modes += (f'<div class="prices" data-mode="{mode}" data-scale="{scale}"{"" if (mode == "sale" and scale == "zoom") else " hidden"}>{HEAD}{rows_db}</div>')
        order = [REF] + sorted([b for b in ORDER if b != REF], key=lambda b: -S['sale'][b][2])
        rows_db = ''
        for i, b in enumerate(order):
            r, sl = S['reg'][b], S['sale'][b]
            mt = tip(name[b], f'정가 {won(r[0])} ~ {won(r[4])} · 중앙값 {won(r[2])}', f'정가 가운데 50% {won(r[1])} ~ {won(r[3])}',
                     f'할인가 {won(sl[0])} ~ {won(sl[4])} · 중앙값 {won(sl[2])}', f'할인가 가운데 50% {won(sl[1])} ~ {won(sl[3])}', f'상품 {len(units[b])}개')
            rows_db += (f'<div class="pr two{" me" if b == REF else ""}" style="--i:{i}" tabindex="0" data-tip="{mt}"><span class="pn">{esc(name[b])}</span>'
                        f'<div class="plot">{gl}{bar(r, "reg", False, False, "정가")}{bar(sl, "sale", False, True, "할인가")}</div>'
                        f'<span class="pv st"><em>{man(r[2])}</em><b>{man(sl[2])}</b></span></div>')
        price_modes += f'<div class="prices" data-mode="both" data-scale="{scale}" hidden>{HEAD}{rows_db}</div>'

    # ---------- 상품 갤러리: 브랜드 × 카테고리, 썸네일 시트 위치 ----------
    gallery, gdata = '', ''
    tix_path = OUT / 'thumbs' / 'index.json'
    if tix_path.exists():
        tix = json.loads(tix_path.read_text(encoding='utf-8'))
        clean = lambda t: re.sub(r'\s+', ' ', re.sub(r'\[[A-Z0-9-]{6,}\]|\s*\([A-Z]{2,}[0-9][A-Z0-9]*\)|-\d+color', '', t or '')).strip()  # noqa: E731
        gi, sheets = {b: {c: [] for c in CATS} for b in ORDER}, {}
        for b in ORDER:
            for p in units[b]:
                hit = tix['items'].get(p['product_id'] + '|' + b)
                if not hit or p['category'] not in CATS:
                    continue
                fn, col, row = hit
                sheets[fn] = max(sheets.get(fn, 0), row + 1)
                rv = p.get('regular_price')
                gi[b][p['category']].append([clean(p['name']), int(p['sale_price']), int(rv) if rv and rv > p['sale_price'] else 0, p['url'], fn, col, row])
            for c in CATS:
                gi[b][c].sort(key=lambda x: (x[6], x[5]))
        c_first = next(c for c in CATS if gi[REF][c])
        gdata = json.dumps({'cell': tix['cell'], 'cols': tix['cols'], 'sheets': sheets, 'items': gi, 'b0': REF, 'sel': [REF, 'kume'], 'c0': c_first,
                            'brands': [{'id': b, 'name': name[b]} for b in ORDER], 'cats': [{'id': c, 'name': CAT_SHORT[c]} for c in CATS]},
                           ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
        gallery = ('<section class="sec" id="gallery">\n  <h2>상품</h2>\n  <div class="gbar"><div class="chips" id="gb" role="group" aria-label="브랜드"></div>'
                   '<div class="chips" id="gc" role="group" aria-label="카테고리"></div><div class="garr"><button type="button" id="gl" aria-label="이전">←</button><button type="button" id="gr" aria-label="다음">→</button></div></div>\n  <div class="gwrap" id="gt"></div>\n</section>\n\n')
        gdata = f'<script type="application/json" id="gdata">{gdata}</script>'

    # ---------- 카테고리별 가격 순위: 중앙값 막대, 그레이스유 순위 (할인가 / 정가 / 함께) ----------
    def cat_bars(c, key, label):
        val = lambda r: num(r[key]) or num(r['sale_median'])  # noqa: E731
        rs = [(b, by[b][c]) for b in ORDER if c in by[b] and by[b][c]['n'] and int(by[b][c]['n'])]
        rs.sort(key=lambda x: -val(x[1]))
        top = val(rs[0][1])
        rank = next(i for i, (b, _) in enumerate(rs, 1) if b == REF)
        bars = ''
        for b, r in rs:
            v, k = val(r), int(r['n'])
            sv, rv = num(r['sale_median']), num(r['regular_median']) or num(r['sale_median'])
            t = tip(f'{name[b]} · {CAT_SHORT[c]} · {label}', f'할인가 중앙값 {won(sv)}', f'정가 중앙값 {won(rv)}',
                    f'할인가 가운데 50% {won(num(r["sale_q1"]))} ~ {won(num(r["sale_q3"]))}', f'상품 {k}개 · 할인 표시 {num(r["discount_share_pct"]) or 0:.0f}%',
                    '' if b == REF else f'그레이스유 대비 {(v / val(by[REF][c]) - 1) * 100:+.0f}%')
            bars += (f'<div class="br{" me" if b == REF else ""}{" thin" if k < 5 else ""}" tabindex="0" data-tip="{t}"><span class="bn">{esc(name[b])}</span>'
                     f'<span class="bt"><i style="width:{v / top * 100:.1f}%"></i></span><span class="bv">{man(v)}</span></div>')
        return bars, rank, len(rs)
    cards_html, cache = '', {}
    for mode, key, label in (('sale', 'sale_median', '할인가'), ('reg', 'regular_median', '정가')):
        cards = ''
        for ci, c in enumerate(CATS):
            bars, rank, nn = cache[(mode, c)] = cat_bars(c, key, label)
            cards += f'<article class="cg" style="--i:{ci}"><header><h3>{esc(CAT_SHORT[c])}</h3><b>{rank}<small>/{nn}</small></b></header>{bars}</article>'
        cards_html += f'<div class="cgs" data-mode="{mode}"{"" if mode == "sale" else " hidden"}>{cards}</div>'
    cards = ''
    for ci, c in enumerate(CATS):
        (b1, r1, n1), (b2, r2, n2) = cache[('sale', c)], cache[('reg', c)]
        cards += (f'<article class="cg two" style="--i:{ci}"><header><h3>{esc(CAT_SHORT[c])}</h3><div class="rk"><span><em>할인가</em><b>{r1}<small>/{n1}</small></b></span>'
                  f'<span><em>정가</em><b>{r2}<small>/{n2}</small></b></span></div></header>'
                  f'<div class="cols"><div class="col"><div class="ct">할인가</div>{b1}</div><div class="col"><div class="ct">정가</div>{b2}</div></div></article>')
    cards_html += f'<div class="cgs two" data-mode="both" hidden>{cards}</div>'

    # ---------- 할인 진행: 할인 중인 상품 비중 · 할인 상품 평균 할인율 · 최소~최대 할인(글자) ----------
    ev = {}
    for e in f['events']:
        b = next(k for k, v in name.items() if v == e['brand'])
        if e['event'] != '프로모션 표시 없이 할인' and (e['models'] or '쿠폰' in e['event']):
            ev.setdefault(b, []).append(e['event'] + (f' {e["discount"]}' if e['discount'] and e['discount'] not in e['event'] else ''))
    drec = {}
    for b in ORDER:
        us = units[b]
        regs = [reg_of(p) for p in us]
        on = [(1 - p['sale_price'] / r) * 100 for p, r in zip(us, regs) if r > p['sale_price']]
        drec[b] = dict(n=len(us), on=len(on), share=len(on) / len(us) * 100, eff=(1 - sum(p['sale_price'] for p in us) / sum(regs)) * 100,
                       avg=(sum(on) / len(on)) if on else 0, mn=min(on) if on else 0, mx=max(on) if on else 0)
    order_d = [REF] + sorted([b for b in ORDER if b != REF], key=lambda b: (-drec[b]['share'], -drec[b]['avg']))
    drows = ''
    for b in order_d:
        d = drec[b]
        t = tip(name[b], f'할인 중 {d["on"]:,}/{d["n"]:,}개 ({d["share"]:.0f}%)', f'할인 상품 평균 {d["avg"]:.1f}% · 최소 {d["mn"]:.0f}% · 최대 {d["mx"]:.0f}%' if d['on'] else '',
                f'전체 상품 기준 평균 {d["eff"]:.1f}%' if d['on'] else '', *list(dict.fromkeys(ev.get(b, [])))[:6])
        drows += (f'<div class="dr{" me" if b == REF else ""}" tabindex="0" data-tip="{t}"><span class="dn">{esc(name[b])}</span>'
                  f'<div class="dsc"><span class="dbar"><i style="width:{d["share"]:.1f}%"></i></span><span class="dsh">{d["share"]:.0f}<small>%</small></span></div>'
                  f'<span class="dv{"" if d["on"] else " nil"}">{f"{d["avg"]:.0f}<small>%</small>" if d["on"] else "-"}</span>'
                  f'<span class="dm{"" if d["on"] else " nil"}">{f"{d["mn"]:.0f}% ~ {d["mx"]:.0f}%" if d["on"] else "-"}</span></div>')

    # ---------- 카테고리 구성: 의류 아이콘 크기 = 브랜드 안에서의 비중 ----------
    D = 'fill="none" stroke="var(--bg)" stroke-linecap="round" stroke-linejoin="round"'
    ICONS = {
        # 잘록한 허리의 블라우스(캡 슬리브, 둥근 네크라인)
        '상의(니트 제외)': ('<path d="M18 6 C16 8 11 9 8 12 L6 19 L12 21 L14 19 C14 25 15 28 15 31 L13 42 H35 L33 31 C33 28 34 25 34 19 L36 21 L42 19 L40 12 C37 9 32 8 30 6 C28 10 20 10 18 6 Z"/>'
                        f'<path d="M24 11 V17" {D} stroke-width="1.4"/>'),
        # 단추 달린 크롭 가디건, 골지 밑단
        '니트·가디건': ('<path d="M17 6 L7 11 L5 29 L11 30 L13 19 L14 40 H34 L35 19 L37 30 L43 29 L41 11 L31 6 C29 9.5 19 9.5 17 6 Z"/>'
                        f'<path d="M24 9 V40 M14 35 H34" {D} stroke-width="1.5"/><circle cx="24" cy="15" r="1.2" fill="var(--bg)"/><circle cx="24" cy="21" r="1.2" fill="var(--bg)"/>'
                        '<circle cx="24" cy="27" r="1.2" fill="var(--bg)"/>'),
        # V넥 핏앤플레어 원피스
        '원피스': ('<path d="M16 4 H19 L24 12 L29 4 H32 V17 C32 20 31 22 30 24 L40 43 H8 L18 24 C17 22 16 20 16 17 Z"/>'
                   f'<path d="M18 24 H30" {D} stroke-width="1.5"/>'),
        # 허리 벨트와 라펠이 있는 코트
        '아우터': ('<path d="M17 5 L6 11 L7 24 L10 28 L6 44 H42 L38 28 L41 24 L42 11 L31 5 L24 16 Z"/>'
                   f'<path d="M10 28 H38 M24 16 V44 M17 5 L24 27 L31 5" {D} stroke-width="1.5"/>'),
        # 플리츠 플레어 미디 스커트
        '스커트': ('<path d="M15 5 H33 V10 L42 43 H6 L15 10 Z"/>'
                   f'<path d="M15 10 H33 M20 10 L16 43 M24 10 V43 M28 10 L32 43" {D} stroke-width="1.3"/>'),
        # 하이웨이스트 와이드 팬츠
        '팬츠': ('<path d="M14 4 H34 L36 14 L41 43 H26 L24 20 L22 43 H7 L12 14 Z"/>'
                 f'<path d="M14 8 H34 M19 8 L18 22 M29 8 L30 22" {D} stroke-width="1.4"/>'),
    }
    cnts = {b: {c: (int(by[b][c]['n'] or 0) if c in by[b] else 0) for c in CATS} for b in ORDER}
    shares = {b: {c: cnts[b][c] / (sum(cnts[b].values()) or 1) for c in CATS} for b in ORDER}
    smax = max(v for b in ORDER for v in shares[b].values()) or 1
    mrows = ''
    for b in ORDER:
        topc = max(CATS, key=lambda c: shares[b][c])
        cells = ''
        for c in CATS:
            sh = shares[b][c]
            h = 46  # 아이콘 크기는 모두 같게, 비중은 색(가장 큰 카테고리 강조)과 숫자로만 표시
            cls = (' top' if c == topc else '') + ('' if cnts[b][c] else ' nil')
            t = tip(f'{name[b]} · {CAT_SHORT[c]}', f'{cnts[b][c]}개 · {sh * 100:.0f}%')
            cells += (f'<div class="mc{cls}" tabindex="0" data-tip="{t}"><svg class="ic" viewBox="0 0 48 48" style="width:{h:.0f}px" aria-hidden="true" fill="currentColor">{ICONS[c]}</svg>'
                      f'<b>{sh * 100:.0f}<small>%</small></b></div>')
        mrows += f'<div class="mr{" me" if b == REF else ""}"><span class="mn">{esc(name[b])}</span>{cells}</div>'
    mhead = ''.join(f'<span>{esc(CAT_SHORT[c])}</span>' for c in CATS)

    # ---------- 변화: 브랜드 × 날짜 달력 (상품 단위, 연속한 두 날짜 비교) ----------
    def model_prices(b, run):
        d = {}
        for p in run['products']:
            if p['in_clothing_scope'] and p['sale_price']:
                k = model_key(b, p)
                if k not in d or p['sale_price'] < d[k][0]:
                    d[k] = (p['sale_price'], p['name'])
        return d
    reps = {b: runs_by_date(b) for b in ORDER}
    all_days = sorted({d for b in ORDER for d in reps[b]})
    cols = all_days[1:][-10:]
    KINDS = (('down', '↓', '가격 인하', 'k-dn'), ('up', '↑', '가격 인상', 'k-up'), ('new', '+', '신규 등록', 'k-nw'), ('gone', '−', '목록에서 빠짐', 'k-gn'))
    clhead = ''.join(f'<span>{d[5:].replace("-", ".")}</span>' for d in cols)
    clrows = ''
    for b in ORDER:
        cells = ''
        for d in cols:
            prev_day = all_days[all_days.index(d) - 1]
            if d not in reps[b]:
                cells += '<div class="cell dim">-</div>'
                continue
            if prev_day not in reps[b]:
                cells += '<div class="cell dim">첫 수집</div>'
                continue
            r0, r1 = reps[b][prev_day], reps[b][d]
            if r0['status'] != 'complete' or r1['status'] != 'complete':
                cells += '<div class="cell dim">수집 불완전</div>'
                continue
            m0, m1 = model_prices(b, r0), model_prices(b, r1)
            ev = {k: [] for k, *_ in KINDS}
            for k, (pr, nm) in m1.items():
                if k not in m0:
                    ev['new'].append((nm, None, pr))
                elif pr < m0[k][0]:
                    ev['down'].append((nm, m0[k][0], pr))
                elif pr > m0[k][0]:
                    ev['up'].append((nm, m0[k][0], pr))
            for k, (pr, nm) in m0.items():
                if k not in m1:
                    ev['gone'].append((nm, pr, None))
            note = CHANGE_NOTES.get((b, d))
            lines = [f'{name[b]} · {d[5:].replace("-", ".")}', note or '']
            chips = ''
            for key, sym, lab, cls in KINDS:
                n = len(ev[key])
                if not n:
                    continue
                chips += f'<span class="chg {cls}"><i>{sym}</i>{n:,}</span>'
                lines.append(f'{lab} {n:,}개')
                for nm, p0, p1 in ev[key][:3]:
                    lines.append(f'  {nm[:28]}  ' + (f'{won(p0)} → {won(p1)}' if p0 and p1 else won(p0 or p1)))
            if not chips:
                chips, lines = '<span class="chg none">·</span>', lines + ['바뀐 것 없음']
            cells += f'<div class="cell" tabindex="0" data-tip="{tip(*lines)}">{chips}</div>'
        clrows += f'<div class="clr{" me" if b == REF else ""}"><span class="cln">{esc(name[b])}</span>{cells}</div>'
    clkey = ''.join(f'<span class="{cls}"><i>{sym}</i>{lab}</span>' for _, sym, lab, cls in KINDS)

    # 변화 시안 A~G를 모두 보여 주고 고른다(changes_lab.py). 순환 import라 여기서 불러온다
    import changes_lab as L
    change_vars = ''.join(f'<div class="lab-sec" id="v-{i}"><h3 class="vt"><b>{k}</b>{t}</h3>{fn()}</div>' for i, k, t, fn in L.VARIANTS)

    # ---------- 배송·반품 ----------
    def fee(b):
        p = pol[b]
        if p.get('free_min') == 0:
            return '무료', '-'
        return (won(p['fee']) if p.get('fee') else '-'), (f'{man(p["free_min"], 0)}만 원 이상' if p.get('free_min') else '-')
    ship = ''
    for b in ORDER:
        a, m = fee(b)
        ret = pol[b].get('ret', '')
        short = '7일' if pol[b].get('return_days') == 7 else '-'
        ship += (f'<tr class="{"me" if b == REF else ""}" tabindex="0" data-tip="{tip(pol[b].get("ship", ""), ret)}"><th scope="row">{esc(name[b])}</th>'
                 f'<td>{esc(a)}</td><td>{esc(m)}</td><td>{esc(short)}</td></tr>')

    body_html = f'''<title>GRACE U 가격 분석</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=Noto+Serif+KR:wght@400;500;600&family=IBM+Plex+Sans+KR:wght@400;500;600&display=swap">
<style>{CSS}{L.LAB_CSS}</style>
<div class="tipbox" id="tip" role="tooltip" hidden></div>
<nav class="fnav" id="fnav" aria-label="구역"><a href="#price">가격</a><a href="#gallery">상품</a><a href="#category">카테고리</a><a href="#discount">할인</a><a href="#mix">구성</a><a href="#change">변화</a><a href="#ship">배송</a></nav>
<main class="wrap">
<header class="mast">
  <h1><span>GRACE U</span></h1>
</header>

<section class="sec" id="price" data-m="sale">
  <div class="hd"><h2>가격 포지션</h2><div class="segs"><div class="seg" role="group" aria-label="가격 기준"><button type="button" data-m="sale" aria-pressed="true">할인가</button><button type="button" data-m="reg" aria-pressed="false">정가</button><button type="button" data-m="both" aria-pressed="false">비교</button></div><div class="seg sx" role="group" aria-label="눈금"><button type="button" data-s="zoom" aria-pressed="true">확대</button><button type="button" data-s="full" aria-pressed="false">최고가 기준</button></div></div></div>
  {price_modes}
  <div class="key"><span><i class="k-rail"></i>최저~최고</span><span><i class="k-iqr"></i>가운데 50%</span><span><i class="k-med"></i>중앙값</span><span class="kb"><i class="k-r"></i>정가</span><span class="kb"><i class="k-s"></i>할인가</span><span class="unit">만 원</span></div>
</section>

{gallery}<section class="sec" id="category">
  <div class="hd"><h2>카테고리별 가격</h2><div class="seg sc" role="group" aria-label="가격 기준"><button type="button" data-m="sale" aria-pressed="true">할인가</button><button type="button" data-m="reg" aria-pressed="false">정가</button><button type="button" data-m="both" aria-pressed="false">비교</button></div></div>
  {cards_html}
</section>

<section class="sec" id="discount">
  <h2>할인 진행</h2>
  <div class="drs"><div class="dh"><span></span><span>할인 중인 상품</span><span>평균 할인율</span><span>최소 ~ 최대</span></div>{drows}</div>
</section>

<section class="sec" id="mix">
  <h2>카테고리 구성</h2>
  <div class="mx"><div class="mh"><span></span>{mhead}</div>{mrows}</div>
</section>

<section class="sec" id="change">
  <h2>변화</h2>
{change_vars}</section>

<section class="sec small" id="ship">
  <h2>배송 · 반품</h2>
  <table class="st"><thead><tr><th></th><th>배송비</th><th>무료 기준</th><th>반품</th></tr></thead><tbody>{ship}</tbody></table>
</section>
</main>
{gdata}
<script>{JS}{L.LAB_JS}</script>'''
    if standalone:
        head_part, main_part = body_html.split('<div class="tipbox"', 1)
        return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
                f'{head_part}</head><body><div class="tipbox"{main_part}</body></html>')
    return body_html


CSS = r'''
/* 한 열 편집 레이아웃: 큰 세리프 표제 아래 차트가 숨 쉬듯 이어진다. 밝은 단일 테마(그레이스유 공식몰의 흰 바탕·세리프 톤) */
:root{color-scheme:light;--bg:#FBFAF8;--paper:#FFFFFF;--ink:#2B2725;--muted:#6B635E;--line:#E4DDD8;--accent:#7A4E5C;--accent-soft:#F4ECEE;--iqr:#D3C4BF;--reg:#85796F;
--serif-en:"Cormorant Garamond","Noto Serif KR",Georgia,serif;--serif:"Noto Serif KR","Cormorant Garamond",serif;--sans:"IBM Plex Sans KR","Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif;
--ease:cubic-bezier(.16,1,.3,1)}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:400 14px/1.6 var(--sans);word-break:keep-all;overflow-wrap:anywhere;-webkit-font-smoothing:antialiased}
body::after{content:"";position:fixed;inset:0;pointer-events:none;z-index:1;opacity:.035;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;background:radial-gradient(60vw 50vw at 88% -5%,rgba(122,78,92,.08),transparent 70%)}
html,body{overflow-x:hidden}
.wrap{position:relative;z-index:2;max-width:1120px;margin:0 auto;padding-block:72px 96px;padding-left:max(20px,env(safe-area-inset-left,0px));padding-right:max(20px,env(safe-area-inset-right,0px));display:grid;gap:88px}
.mast{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:end;gap:24px 48px;padding-bottom:28px;border-bottom:1px solid var(--ink)}
h1{margin:0;font:500 clamp(64px,11vw,148px)/.86 var(--serif-en);letter-spacing:-.035em}
h1 span{display:inline-block;background:linear-gradient(100deg,var(--ink) 40%,var(--accent) 100%);-webkit-background-clip:text;background-clip:text;color:transparent}
.stats{display:flex;gap:36px;padding-bottom:10px}
.stat{display:grid;gap:2px;cursor:default;outline:none}
.stat b{font:500 40px/1 var(--serif-en);font-variant-numeric:lining-nums tabular-nums;letter-spacing:-.01em}
.stat span{font-size:12px;color:var(--muted);letter-spacing:.04em}
.stat[data-tip]{border-bottom:1px dotted var(--reg)}
.date{grid-column:1/-1;margin:0;font:italic 400 16px/1 var(--serif-en);color:var(--muted);letter-spacing:.08em}
.sec{display:grid;gap:22px;min-width:0}
h2{margin:0;font:500 22px/1.3 var(--serif);letter-spacing:-.01em;display:flex;align-items:baseline;gap:12px}
h2 small{font:italic 400 15px var(--serif-en);color:var(--muted);letter-spacing:.04em}
.key{display:flex;flex-wrap:wrap;gap:18px;align-items:center;font-size:12px;color:var(--muted)}
.key span{display:inline-flex;align-items:center;gap:7px}
.key .unit{margin-left:auto;font:italic 13px var(--serif-en);letter-spacing:.06em}
.key i{display:inline-block}
.ramp{gap:0!important}.ramp i{width:22px;height:10px}.ramp em{font-style:normal;margin:0 8px}
/* 가격 포지션 */
.prices{display:grid}
.ph,.pr{display:grid;grid-template-columns:9.5em minmax(0,1fr) 5.4em;align-items:center;column-gap:12px}
.ph{height:36px;font-size:12.5px;color:var(--muted)}
.axis{position:relative;height:100%;margin:0 76px 0 52px}
.axis i{position:absolute;top:50%;transform:translate(-50%,-50%);white-space:nowrap;font:italic 500 15px var(--serif-en);color:var(--ink)}
.pr{height:80px;border-top:1px solid var(--line);outline:none;transition:background .25s var(--ease)}
.pr.two{height:116px}
.pr:hover,.pr:focus-visible{background:rgba(122,78,92,.05)}
.pn{font-size:16px;padding-left:10px;color:var(--ink)}
.pr.me .pn{font-weight:600;color:var(--accent)}
.plot{position:relative;height:100%;margin:0 76px 0 52px}
.gl{position:absolute;top:0;bottom:0;border-left:1px solid #E7DFD9}
.plot::before{content:"";position:absolute;left:0;top:0;bottom:0;width:2px;background:#B7AAA2}
.bar{position:absolute;left:0;right:0;top:0;bottom:0}
.pr.two .bar{height:44px;bottom:auto}
.pr.two .bar.reg{top:10px}
.pr.two .bar.sale{top:62px}
.rail{position:absolute;top:50%;height:2px;margin-top:-1px;background:#C2B3AA}
.cap{position:absolute;top:50%;width:10px;height:10px;margin:-5px 0 0 -5px;border-radius:50%;background:var(--bg);border:2px solid #AE9D93;box-sizing:border-box}
.box{position:absolute;top:50%;height:36px;margin-top:-18px;border-radius:8px;background:linear-gradient(180deg,#BEAEA4,#9A887E);box-shadow:inset 0 1px 0 rgba(255,255,255,.42),0 12px 18px -14px rgba(60,40,40,.6)}
.pr.two .box{height:30px;margin-top:-15px}
.bar.reg .box{background:linear-gradient(180deg,#E0D6CF,#D2C6BE);box-shadow:inset 0 1px 0 rgba(255,255,255,.55)}
.pr.me .box{background:linear-gradient(180deg,#D08AA0,#9A5470)}
.pr.me .bar.reg .box{background:linear-gradient(180deg,#EDD3DC,#E2C0CC)}
.pr.me .cap{border-color:#C79BAA}
.med{position:absolute;top:50%;width:3px;height:36px;margin:-18px 0 0 -1.5px;border-radius:2px;background:#fff;box-shadow:0 0 0 1px rgba(60,40,40,.2)}
.pr.two .med{height:30px;margin-top:-15px}
.bar.reg .med{background:#8F847D;box-shadow:none}
.lo,.hi{position:absolute;top:50%;transform:translateY(-50%);font:500 19px/1 var(--serif-en);font-variant-numeric:lining-nums tabular-nums;color:var(--ink);white-space:nowrap}
.lo{margin-right:13px}
.hi{margin-left:13px}
.hi em{font:400 12px var(--sans);color:var(--accent);margin-left:4px;font-style:normal}
.pr.two .bar.reg .lo,.pr.two .bar.reg .hi{color:var(--muted);font-size:16px}
.pv{text-align:right;padding-right:12px;font:500 34px/1 var(--serif-en);font-variant-numeric:lining-nums tabular-nums;color:var(--ink)}
.ph .pv{font:400 12.5px var(--sans);color:var(--muted)}
.pr.me .pv{color:var(--accent)}
.pv.st{display:grid;gap:9px;align-content:center}
.pv.st em{font:400 19px/1 var(--serif-en);font-style:normal;color:var(--muted)}
.pv.st b{font:500 32px/1 var(--serif-en)}
.k-rail{width:26px;height:2px;background:#AE9D93;position:relative}
.k-iqr{width:26px;height:14px;border-radius:4px;background:linear-gradient(180deg,#BEAEA4,#9A887E)}
.k-med{width:14px;height:14px;border-radius:3px;background:#9A887E;position:relative}
.k-med::after{content:"";position:absolute;left:50%;top:0;bottom:0;width:3px;margin-left:-1.5px;background:#fff}
.kb{display:none}
#price[data-m="both"] .kb{display:inline-flex}
.k-r{width:26px;height:14px;border-radius:4px;background:#D6CAC2}
.k-s{width:26px;height:14px;border-radius:4px;background:#A5948A}
/* 가격 포지션: 얇은 박스, 중앙값 선, 큰 눈금 숫자 */
.box{height:18px;margin-top:-9px;border-radius:5px}
.pr.two .box{height:16px;margin-top:-8px}
.med{width:3px;height:38px;margin:-19px 0 0 -1.5px;border-radius:2px;background:var(--ink);box-shadow:0 0 0 2px var(--bg)}
.pr.two .med{height:30px;margin-top:-15px}
.pr.me .med{background:#4A2433}
.bar.reg .med{background:#8F847D;box-shadow:0 0 0 2px var(--bg)}
.mdl{position:absolute;top:50%;transform:translate(-50%,-100%);margin-top:-23px;font:500 16px/1 var(--serif-en);color:var(--ink);white-space:nowrap;font-variant-numeric:lining-nums}
.pr.me .mdl{color:var(--accent)}
.ph{height:44px}
.axis i{font:500 19px var(--serif-en);font-style:normal;color:var(--ink)}
.k-med{width:3px;height:16px;border-radius:2px;background:var(--ink)}
.k-med::after{display:none}
.k-iqr{height:10px}
/* 최저·최고 숫자: 막대 끝 아래, 보조선과 겹치지 않게 */
.lo,.hi{top:calc(50% + 12px);transform:none;margin:0;padding:0 2px;font-size:17px;text-shadow:0 0 3px var(--bg),0 0 3px var(--bg),0 0 4px var(--bg),0 0 4px var(--bg)}
.lo{margin-left:-5px}
.hi{transform:translateX(calc(-100% + 5px))}
.pr.two .bar .lo,.pr.two .bar .hi{top:calc(50% + 10px)}
.pr.two .bar.reg .lo,.pr.two .bar.reg .hi{font-size:15px}
/* 카테고리별 순위 막대 */
.cgs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:40px 48px}
.cg{display:grid;gap:7px;align-content:start}
.cg header{display:flex;align-items:baseline;justify-content:space-between;border-bottom:1px solid var(--ink);padding-bottom:8px;margin-bottom:6px}
.cg h3{margin:0;font:500 17px var(--serif)}
.cg header b{font:500 30px/1 var(--serif-en);color:var(--accent);font-variant-numeric:lining-nums}
.cg header small{font-size:15px;color:var(--muted);margin-left:2px}
.br{display:grid;grid-template-columns:6.6em minmax(0,1fr) 3.2em;align-items:center;gap:10px;height:24px;outline:none;border-radius:4px}
.br:hover,.br:focus-visible{background:rgba(122,78,92,.06)}
.bn{font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bt{height:12px;background:transparent}
.bt i{display:block;height:100%;background:#BFB3AD;border-radius:0 3px 3px 0}
.br.me .bn{color:var(--accent);font-weight:600}
.br.me .bt i{background:var(--accent)}
.br.thin{opacity:.45}
.bv{text-align:right;font:500 16px/1 var(--serif-en);font-variant-numeric:lining-nums tabular-nums}
.br.me .bv{color:var(--accent)}
/* 카테고리 구성 */
.mx{display:grid}
.mh,.mr{display:grid;grid-template-columns:8em repeat(6,minmax(0,1fr));column-gap:6px}
.mh{height:38px;align-items:center;font-size:15px;color:var(--ink);text-align:center}
.mr{height:100px;border-top:1px solid var(--line);align-items:stretch}
.mn{font-size:17px;padding-left:8px;align-self:center}
.mr.me .mn{color:var(--accent);font-weight:600}
.mc{display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:6px;padding-bottom:9px;outline:none;color:#B8AAA0;transition:color .3s var(--ease)}
.mc:hover,.mc:focus-visible{color:var(--ink)}
.ic{display:block;height:auto;max-width:100%;transition:transform .35s var(--ease)}
.mc:hover .ic{transform:translateY(-4px)}
.mc b{font:500 22px/1 var(--serif-en);color:var(--ink);font-variant-numeric:lining-nums}
.mc b small{font:400 13px var(--sans);color:var(--muted);margin-left:1px}
.mc.top{color:#8A5568}
.mc.top b{color:var(--accent);font-size:28px}
.mc.nil{opacity:.35}
/* 히트맵 표 */
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.hm{width:100%;border-collapse:separate;border-spacing:3px;font-variant-numeric:lining-nums tabular-nums}
.hm th{font-weight:400;font-size:12px;color:var(--muted);text-align:center;padding:4px 6px;white-space:nowrap}
.hm tbody th{text-align:left;font-size:14px;color:var(--ink);padding-right:14px}
.hm tr.me th{color:var(--accent);font-weight:600}
.hm td{height:46px;min-width:72px;text-align:center;font:500 17px/1 var(--serif-en);border-radius:4px;cursor:default;outline:none;transition:transform .2s var(--ease),box-shadow .2s var(--ease)}
.hm td:hover,.hm td:focus-visible{transform:translateY(-2px) scale(1.04);box-shadow:0 8px 20px -10px rgba(60,40,40,.35);position:relative;z-index:1}
.hm tr.me td{box-shadow:inset 0 0 0 1.5px var(--accent)}
.hm td.thin{opacity:.55}
.hm td.nil{background:transparent;color:var(--reg)}
.mixt td{font-size:15px;min-width:44px;height:40px}
.mixt td.tot{background:transparent;color:var(--muted);font:400 13px var(--sans)}
/* 2열 묶음 */
.pair{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:56px;align-items:start}
.sc{width:100%;height:auto;overflow:visible}
.sc .gr line{stroke:var(--line)}
.sc .gr text,.sc .ax{fill:var(--muted);font:italic 12px var(--serif-en)}
.sc .ax{font:400 11px var(--sans)}
.pt{cursor:default;outline:none}
.pt circle{fill:var(--ink);stroke:var(--bg);stroke-width:3;transition:r .25s var(--ease)}
.pt.me circle{fill:var(--accent)}
.pt text{fill:var(--ink);font:400 12px var(--sans)}
.pt.me text{fill:var(--accent);font-weight:600}
.pt:hover circle,.pt:focus-visible circle{r:9}
/* 변화 기록 */
.log{margin:0;padding:0;list-style:none;border-top:1px solid var(--line)}
.log li{display:grid;grid-template-columns:7em 6em 3em 6em minmax(0,1fr);gap:10px;align-items:baseline;padding:12px 6px;border-bottom:1px solid var(--line);outline:none;transition:background .2s var(--ease)}
.log li:hover,.log li:focus-visible{background:rgba(122,78,92,.05)}
.lb{font-weight:500}
.lk{color:var(--muted);font-size:13px}
.lc{font:500 20px/1 var(--serif-en);text-align:right;font-variant-numeric:lining-nums tabular-nums}
.lr{font-size:12px;color:var(--accent);font-variant-numeric:tabular-nums}
.ln{font-size:12px;color:var(--muted)}
/* 배송·반품: 작게 */
.small h2{font-size:17px}
.st{width:100%;border-collapse:collapse;font-size:12px;font-variant-numeric:tabular-nums}
.st th,.st td{padding:7px 6px;border-bottom:1px solid var(--line);text-align:left;font-weight:400;white-space:nowrap}
.st thead th{color:var(--muted);font-size:11px}
.st tbody th{color:var(--ink)}
.st tr{outline:none}.st tr:hover td,.st tr:hover th,.st tr:focus-visible td{background:rgba(122,78,92,.05)}
.st tr.me th{color:var(--accent);font-weight:600}
[hidden]{display:none!important}
.hd{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}
.seg{display:inline-flex;border:1px solid #D6CDC7;border-radius:999px;padding:3px;background:transparent}
.seg button{font:inherit;font-size:13.5px;padding:5px 18px;border:0;border-radius:999px;background:transparent;color:var(--muted);cursor:pointer;transition:background .25s var(--ease),color .25s var(--ease)}
.seg button[aria-pressed="true"]{background:var(--ink);color:#fff}
/* 첫 화면 숫자·메뉴·갤러리 화살표 */
.stat b small{font:400 18px var(--sans);color:var(--muted);margin-left:2px}
.stats{gap:44px}
.sec{scroll-margin-top:72px}
.fnav{position:fixed;top:calc(14px + env(safe-area-inset-top,0px));left:50%;transform:translate(-50%,-90px);z-index:15;display:flex;gap:2px;padding:5px;border-radius:999px;background:rgba(251,250,248,.82);-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);border:1px solid var(--line);box-shadow:0 12px 32px -20px rgba(60,40,40,.5);transition:transform .7s var(--ease);max-width:calc(100vw - 24px);overflow-x:auto;scrollbar-width:none}
.fnav::-webkit-scrollbar{display:none}
.fnav.on{transform:translate(-50%,0)}
.fnav a{font-size:13px;padding:7px 14px;border-radius:999px;color:var(--muted);text-decoration:none;white-space:nowrap;transition:background .3s var(--ease),color .3s var(--ease)}
.fnav a:hover{color:var(--ink)}
.fnav a.act{background:var(--ink);color:#fff}
.gbar{position:relative}
.garr{position:absolute;right:0;top:0;display:flex;gap:8px}
.garr button{width:38px;height:38px;border-radius:50%;border:1px solid #D6CDC7;background:transparent;color:var(--ink);font:400 17px/1 var(--sans);cursor:pointer;transition:background .25s var(--ease),color .25s var(--ease),transform .2s var(--ease)}
.garr button:hover{background:var(--ink);color:#fff}
.garr button:active{transform:scale(.94)}
/* 할인 진행 */
.drs{display:grid;max-width:840px}
.dh,.dr{display:grid;grid-template-columns:8.5em minmax(0,1fr) 5.5em 8.5em;align-items:center;column-gap:20px}
.dh{height:30px;font-size:12.5px;color:var(--muted);white-space:nowrap}
.dh span:nth-child(3),.dh span:nth-child(4){text-align:right}
.dr{height:54px;border-top:1px solid var(--line);outline:none;transition:background .25s var(--ease)}
.dr:hover,.dr:focus-visible{background:rgba(122,78,92,.05)}
.dn{font-size:15.5px;padding-left:8px}
.dr.me .dn{color:var(--accent);font-weight:600}
.dsc{display:flex;align-items:center;gap:14px;min-width:0}
.dbar{flex:1;height:16px;border-radius:5px;background:#E9E2DD;overflow:hidden}
.dbar i{display:block;height:100%;border-radius:0 5px 5px 0;background:#8A5568}
.dsh{flex:0 0 3.6em;text-align:right;font:500 22px/1 var(--serif-en);font-variant-numeric:lining-nums;color:var(--ink)}
.dsh small,.dv small{font:400 12px var(--sans);margin-left:1px;color:var(--muted)}
.dv{text-align:right;font:500 28px/1 var(--serif-en);font-variant-numeric:lining-nums;color:var(--accent)}
.dm{text-align:right;font:500 17px/1 var(--serif-en);font-variant-numeric:lining-nums;color:var(--ink);white-space:nowrap}
.dv.nil,.dm.nil{color:var(--muted)}
.sec>.hd{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}
.seg{width:max-content;flex:0 0 auto}
.cgs.two{grid-template-columns:repeat(2,minmax(0,1fr));gap:44px 56px}
.cg.two .cols{display:grid;grid-template-columns:1fr 1fr;gap:26px}
.cg.two .col{display:grid;gap:7px;align-content:start}
.ct{font-size:12.5px;color:var(--muted);letter-spacing:.04em;padding-bottom:5px;border-bottom:1px solid var(--line);margin-bottom:2px}
.cg header .rk{display:flex;gap:24px}
.rk span{display:flex;align-items:baseline;gap:7px}
.rk em{font:400 12.5px var(--sans);font-style:normal;color:var(--muted)}
.cg header .rk b{font:500 30px/1 var(--serif-en);color:var(--accent)}
.rk small{font-size:14px;color:var(--muted);margin-left:1px}
.cg.two .br{grid-template-columns:7.2em minmax(0,1fr) 3.2em;gap:8px}
/* 상품 갤러리 */
.gbar{display:grid;gap:10px}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{font:inherit;font-size:13px;color:var(--ink);background:transparent;border:1px solid #D6CDC7;border-radius:999px;padding:5px 14px;cursor:pointer;transition:background .2s var(--ease),color .2s var(--ease),border-color .2s var(--ease)}
.chip small{margin-left:5px;font-size:11px;color:var(--muted)}
.chip:hover:not(:disabled){border-color:var(--ink)}
.chip[aria-pressed="true"]{background:var(--ink);border-color:var(--ink);color:#fff}
.chip[aria-pressed="true"] small{color:#CFC6C0}
.chip.me:not([aria-pressed="true"]){color:var(--accent);border-color:#D9BCC6}
.chip:disabled{opacity:.35;cursor:default}
.gtrack{display:flex;gap:16px;overflow-x:auto;padding:6px 2px 20px;cursor:grab;user-select:none;-webkit-user-select:none;scrollbar-width:thin;scrollbar-color:#CFC6C0 transparent;outline:none;-webkit-mask-image:linear-gradient(90deg,#000 94%,transparent);mask-image:linear-gradient(90deg,#000 94%,transparent)}
.gtrack.drag{cursor:grabbing}
.gc{flex:0 0 180px;display:grid;gap:9px;align-content:start;color:inherit;text-decoration:none}
.gi{width:180px;height:240px;border-radius:3px;background-color:#EEE9E5;background-repeat:no-repeat;transition:transform .35s var(--ease),box-shadow .35s var(--ease);-webkit-user-drag:none}
.gc:hover .gi{transform:translateY(-4px);box-shadow:0 18px 26px -18px rgba(60,40,40,.5)}
.gn{font-size:12.5px;line-height:1.4;height:2.8em;overflow:hidden;color:var(--muted)}
.gp{font:500 19px/1 var(--serif-en);font-variant-numeric:lining-nums tabular-nums;white-space:nowrap}
.gp s{margin-left:7px;font:400 12px var(--sans);color:var(--muted)}
.gp em{margin-left:6px;font:500 12px var(--sans);font-style:normal;color:var(--accent)}
.gwrap{display:grid;gap:30px}
.grow{display:grid;gap:10px;min-width:0}
.gh{display:flex;align-items:baseline;gap:9px;font:500 19px var(--serif);color:var(--ink)}
.gh small{font:400 13px var(--sans);color:var(--muted)}
.grow.me .gh{color:var(--accent)}
.gnone{color:var(--muted);padding:48px 0;font-size:22px}
.garr{top:auto;bottom:calc(100% + 0px)}
/* 툴팁 */
.tipbox{position:fixed;z-index:20;max-width:320px;padding:12px 14px;background:rgba(43,39,37,.94);color:#F7F3F0;border-radius:8px;font-size:12px;line-height:1.55;pointer-events:none;box-shadow:0 14px 34px -14px rgba(43,39,37,.6);transform:translateY(4px);opacity:0;transition:opacity .15s var(--ease),transform .15s var(--ease)}
.tipbox.on{opacity:1;transform:none}
.tipbox b{display:block;font:500 13px var(--serif);margin-bottom:3px;color:#fff}
[data-tip]{cursor:default}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
/* 가독성 */
:root{--muted:#544C47;--line:#DDD5CF;--iqr:#C9BCB5}
body{font-size:15px}
.stat b{font-size:44px}
.stat span{font-size:13px;color:var(--muted)}
h2{font-size:25px}
.key{font-size:13px;color:var(--muted)}
.cg h3{font-size:19px}
.cg header b{font-size:36px}
.br{height:30px;grid-template-columns:7em minmax(0,1fr) 3.6em}
.bn{font-size:14.5px}
.bt{height:16px}
.bt i{background:#A99B94;border-radius:0 4px 4px 0}
.br.me .bt i{background:var(--accent)}
.br.thin{opacity:.62}
.bv{font-size:20px}
.lb{font-size:15px}.lk{font-size:14px}.ln,.lr{font-size:13px}.lc{font-size:22px}
.gn{font-size:13.5px;color:#4A433E}
@supports (animation-timeline:view()){@media (prefers-reduced-motion:no-preference){
 .bt i,.dbar i,.cbar i,.box,.med{transform-origin:left center;animation:grow linear both;animation-timeline:view();animation-range:entry 5% entry 70%}
 @keyframes grow{from{transform:scaleX(0)}}
}}
/* 가독성 2차: 글자 크기·굵기·대비 */
:root{--muted:#4A433E;--line:#D8CFC9}
body{font-size:16px;line-height:1.6}
h2{font-size:28px;font-weight:600}
.key{font-size:14.5px}
.key .unit{font-size:15px;font-style:normal;color:var(--muted)}
.seg button{font-size:15px;padding:6px 20px;color:var(--ink)}
.seg button[aria-pressed="true"]{color:#fff}
.chip{font-size:14.5px;padding:6px 16px}
.chip small{font-size:12.5px;color:var(--muted)}
.fnav a{font-size:14.5px;color:var(--ink)}
.fnav a.act{color:#fff}
.ph{font-size:14px}
.pn{font-size:17.5px;font-weight:500}
.axis i{font-weight:600;font-size:20px}
.lo,.hi{font-weight:600;font-size:19px}
.mdl{font-weight:600;font-size:18px}
.pv{font-weight:600;font-size:40px}
.pv.st em{font-size:20px;font-weight:500}
.pv.st b{font-size:34px;font-weight:600}
.pr.two .bar.reg .lo,.pr.two .bar.reg .hi{font-size:16px}
.cg h3{font-size:21px;font-weight:600}
.cg header b{font-weight:600;font-size:42px}
.cg header b small{font-size:17px}
.ct{font-size:14px}
.rk em{font-size:14px;color:var(--ink)}
.cg header .rk b{font-size:34px;font-weight:600}
.br{height:32px}
.bn{font-size:16px}
.bv{font-weight:600;font-size:22px}
.dh{font-size:14px;color:var(--ink)}
.dn{font-size:17px}
.dsh{font-weight:600;font-size:27px}
.dv{font-weight:600;font-size:34px}
.dm{font-weight:600;font-size:20px}
.mh{font-size:16px;font-weight:500}
.mn{font-size:18px}
.mc b{font-weight:600;font-size:24px}
.mc b small{font-size:14px}
.mc.top b{font-size:30px}
.gh{font-size:22px;font-weight:600}
.gh small{font-size:14px}
.gn{font-size:14.5px;color:var(--ink)}
.gp{font-weight:600;font-size:22px}
.gp s{font-size:14px}
.gp em{font-size:14px}
.lb{font-size:16.5px}
.lk{font-size:15px;color:var(--ink)}
.ln,.lr{font-size:14px}
.lc{font-weight:600;font-size:25px}
.st{font-size:14px}
.st thead th{font-size:13px;color:var(--ink)}
.tipbox{font-size:14px;max-width:340px}
.tipbox b{font-size:15px}
/* 비교 보기·구분선·중앙값 숫자 크기 */
:root{--rule:#B3A69D}
.pv{font-size:28px;font-weight:600}
.pv.st em{font:600 26px/1 var(--serif-en);font-style:normal;color:#7B6F67}
.pv.st b{font:600 26px/1 var(--serif-en)}
.tg{position:absolute;right:calc(100% + 8px);top:50%;transform:translateY(-50%);font:500 13px/1 var(--sans);color:#7B6F67;white-space:nowrap}
.bar.sale .tg{color:var(--ink);font-weight:600}
.pr.me .bar.sale .tg{color:var(--accent)}
@media (max-width:640px){.tg{display:none}}
.pr.two{height:100px}
.pr.two .bar{height:30px}
.pr.two .bar.reg{top:12px}
.pr.two .bar.sale{top:42px}
.pr.two .box{height:14px;margin-top:-7px}
.pr.two .med{height:26px;margin-top:-13px}
.pr.two .bar.sale .lo,.pr.two .bar.sale .hi{top:calc(50% + 11px)}
.pv.st{gap:6px}
.segs{display:flex;gap:10px;flex-wrap:wrap;align-items:center;justify-content:flex-end}
.box{min-width:8px}
.mdl{text-shadow:0 0 3px var(--bg),0 0 3px var(--bg),0 0 4px var(--bg)}
.lo2{position:absolute;top:50%;transform:translateY(-50%);margin-left:14px;font:600 19px/1 var(--serif-en);font-variant-numeric:lining-nums;color:var(--ink);white-space:nowrap;text-shadow:0 0 3px var(--bg),0 0 3px var(--bg),0 0 4px var(--bg)}
.pr.two .bar.sale .lo2{top:50%}
.pr,.dr,.mr{border-top:1px solid var(--rule)}
.prices .pr:last-child,.drs .dr:last-child,.mx .mr:last-child{border-bottom:1px solid var(--rule)}
.st th,.st td{border-bottom-color:var(--rule)}
.log,.log li{border-color:var(--rule)}
.mr{height:92px}
.gtrack{scrollbar-width:auto;scrollbar-color:auto;padding-bottom:10px}
.gtrack::-webkit-scrollbar{height:14px}
.gtrack::-webkit-scrollbar-track{background:#EFE9E4;border-radius:7px}
.gtrack::-webkit-scrollbar-thumb{background:#B3A59B;border-radius:7px;border:3px solid #EFE9E4}
.gtrack::-webkit-scrollbar-thumb:hover{background:#8F8077}
@supports (-moz-appearance:none){.gtrack{scrollbar-width:auto;scrollbar-color:#B3A59B #EFE9E4}}
/* 변화 달력 */
.cal{display:grid;overflow-x:auto}
.clh,.clr{display:grid;grid-template-columns:7.5em repeat(var(--n),minmax(132px,1fr));align-items:center;column-gap:10px;min-width:max-content}
.clh{height:34px;font-size:14.5px;color:var(--ink);font-variant-numeric:tabular-nums}
.clh span{text-align:center}
.clr{min-height:64px;border-top:1px solid var(--rule)}
.clr:last-child{border-bottom:1px solid var(--rule)}
.cln{font-size:17px;padding-left:6px}
.clr.me .cln{color:var(--accent);font-weight:600}
.cell{display:flex;gap:14px;flex-wrap:wrap;justify-content:center;align-items:center;min-height:52px;padding:6px 4px;border-radius:6px;outline:none;transition:background .25s var(--ease)}
.cell:hover,.cell:focus-visible{background:rgba(122,78,92,.07)}
.cell.dim{color:var(--muted);font-size:14px}
.chg{display:inline-flex;align-items:baseline;gap:3px;font:600 23px/1 var(--serif-en);font-variant-numeric:lining-nums}
.chg i{font:600 18px var(--sans);font-style:normal}
.chg.none{color:var(--muted)}
.k-dn{color:#8A5568}.k-up{color:#4F6D8A}.k-nw{color:var(--ink)}.k-gn{color:#85766D}
.clk span{display:inline-flex;align-items:center;gap:6px}
.clk i{font:600 18px var(--sans);font-style:normal}
/* 등장 */
@media (prefers-reduced-motion:no-preference){
 @keyframes fade{from{opacity:0}}
 .gc{animation:rise .55s var(--ease) backwards;animation-delay:calc(var(--k)*28ms)}
 @keyframes rise{from{opacity:0;transform:translateY(12px)}}
}
@media (max-width:900px){.cgs.two{grid-template-columns:1fr}.cgs{grid-template-columns:repeat(2,minmax(0,1fr))}.pair{grid-template-columns:1fr;gap:88px}}
@media (max-width:640px){.dh,.dr{grid-template-columns:4.8em minmax(0,1fr) 3.4em 6em;column-gap:6px}.drs{max-width:none}.dsh{font-size:18px;flex-basis:3em}.dv{font-size:20px}.dm{font-size:13px}.dn{font-size:12.5px;padding-left:2px}.mh,.mr{grid-template-columns:4.2em repeat(6,minmax(0,1fr));column-gap:2px}.mh{font-size:11px;line-height:1.2}.mr{height:88px}.mn{font-size:12.5px;padding-left:2px}.mc b{font-size:15px}.mc b small{font-size:9px}.mc.top b{font-size:18px}.cgs{grid-template-columns:1fr}.wrap{padding-block:44px 64px;gap:64px}.mast{grid-template-columns:1fr}.stats{gap:24px}.stat b{font-size:30px}
 .ph,.pr{grid-template-columns:4.8em minmax(0,1fr) 3.6em;column-gap:6px}.plot,.axis{margin:0 40px 0 30px}.lo,.hi{font-size:14px}.pn{font-size:12.5px;padding-left:2px;line-height:1.25}.pv{font-size:23px;padding-right:2px}.pv.st b{font-size:21px}.pv.st em{font-size:14px}.axis i{font-size:14px}
 .log li{grid-template-columns:6em minmax(0,1fr) 2.5em;row-gap:2px}.lr{grid-column:2}.ln{grid-column:2/-1}}
'''

JS = r'''
(()=>{const box=document.getElementById('tip');let cur=null;
function show(el,x,y){const p=el.dataset.tip.split('|');box.innerHTML='<b>'+p[0].replace(/</g,'&lt;')+'</b>'+p.slice(1).map(s=>s.replace(/</g,'&lt;')).join('<br>');box.hidden=false;place(x,y);requestAnimationFrame(()=>box.classList.add('on'))}
function place(x,y){const w=box.offsetWidth,h=box.offsetHeight;let l=x+16,t=y+18;if(l+w>innerWidth-8)l=x-w-16;if(t+h>innerHeight-8)t=y-h-14;box.style.left=Math.max(8,l)+'px';box.style.top=Math.max(8,t)+'px'}
function hide(){box.classList.remove('on');box.hidden=true;cur=null}
document.addEventListener('pointerover',e=>{const el=e.target.closest('[data-tip]');if(el&&el!==cur){cur=el;show(el,e.clientX,e.clientY)}else if(!el&&cur)hide()});
document.addEventListener('pointermove',e=>{if(cur)place(e.clientX,e.clientY)});
document.addEventListener('focusin',e=>{const el=e.target.closest('[data-tip]');if(el){cur=el;const r=el.getBoundingClientRect();show(el,r.left+r.width/2,r.bottom)}});
document.addEventListener('focusout',hide);addEventListener('scroll',()=>{if(cur&&!cur.matches(':focus'))hide()},{passive:true});})();

(()=>{const el=document.getElementById('gdata');if(!el)return;const d=JSON.parse(el.textContent),CW=d.cell[0],CH=d.cell[1],CO=d.cols;
const gb=document.getElementById('gb'),gc=document.getElementById('gc'),gt=document.getElementById('gt');let SEL=d.sel.slice(),C=d.c0;
const esc=t=>String(t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const f=v=>v.toLocaleString('ko-KR');
const chip=(label,n,on,dis,me,k,v)=>'<button class="chip'+(me?' me':'')+'" type="button" aria-pressed="'+on+'" '+(dis?'disabled':'')+' data-'+k+'="'+esc(v)+'">'+esc(label)+'<small>'+n+'</small></button>';
const card=(x,i)=>{const n=x[0],s=x[1],r=x[2],u=x[3],fn=x[4],col=x[5],row=x[6],rows=d.sheets[fn];
return '<a class="gc" href="'+esc(u)+'" target="_blank" rel="noopener" draggable="false" style="--k:'+Math.min(i,14)+'"><div class="gi" style="background-image:url(thumbs/'+fn+');background-size:'+CO*CW+'px '+rows*CH+'px;background-position:-'+col*CW+'px -'+row*CH+'px"></div><div class="gn">'+esc(n)+'</div><div class="gp">'+f(s)+(r?'<s>'+f(r)+'</s><em>-'+Math.round((1-s/r)*100)+'%</em>':'')+'</div></a>'};
function draw(){
gb.innerHTML=d.brands.map(b=>chip(b.name,d.items[b.id][C].length,SEL.includes(b.id),false,b.id===d.b0,'b',b.id)).join('');
gc.innerHTML=d.cats.map(c=>{const n=SEL.reduce((a,b)=>a+d.items[b][c.id].length,0);return chip(c.name,n,c.id===C,!n,false,'c',c.id)}).join('');
gt.innerHTML=d.brands.filter(b=>SEL.includes(b.id)).map(b=>{const list=d.items[b.id][C]||[];
return '<div class="grow'+(b.id===d.b0?' me':'')+'"><div class="gh">'+esc(b.name)+'<small>'+list.length+'</small></div><div class="gtrack" tabindex="0">'+(list.length?list.map(card).join(''):'<div class="gnone">-</div>')+'</div></div>'}).join('')}
gb.addEventListener('click',e=>{const x=e.target.closest('[data-b]');if(!x)return;const id=x.dataset.b;
if(SEL.includes(id)){if(SEL.length>1)SEL=SEL.filter(v=>v!==id)}else SEL=d.brands.map(b=>b.id).filter(v=>SEL.includes(v)||v===id);
if(!SEL.some(b=>d.items[b][C].length)){const c=d.cats.find(c=>SEL.some(b=>d.items[b][c.id].length));if(c)C=c.id}draw()});
gc.addEventListener('click',e=>{const x=e.target.closest('[data-c]');if(!x||x.disabled)return;C=x.dataset.c;draw()});
let down=null,sx=0,sl=0,moved=0,vx=0,lx=0,raf=0;
gt.addEventListener('pointerdown',e=>{const t=e.target.closest('.gtrack');if(!t||e.pointerType==='touch')return;down=t;moved=0;sx=lx=e.clientX;sl=t.scrollLeft;vx=0;cancelAnimationFrame(raf)});
addEventListener('pointermove',e=>{if(!down)return;const dx=e.clientX-sx;if(Math.abs(dx)>4){moved=1;down.classList.add('drag')}down.scrollLeft=sl-dx;vx=e.clientX-lx;lx=e.clientX});
addEventListener('pointerup',()=>{if(!down)return;const t=down;down=null;t.classList.remove('drag');let v=-vx;const step=()=>{if(Math.abs(v)<.4)return;t.scrollLeft+=v;v*=.94;raf=requestAnimationFrame(step)};if(moved)step()});
gt.addEventListener('click',e=>{if(moved){e.preventDefault();moved=0}},true);
draw()})();

(()=>{const sec=document.getElementById('price');if(!sec)return;let M='sale',S='zoom';
const apply=()=>{sec.dataset.m=M;sec.querySelectorAll('.prices').forEach(p=>{p.hidden=!(p.dataset.mode===M&&p.dataset.scale===S)});
sec.querySelectorAll('.seg [data-m]').forEach(x=>x.setAttribute('aria-pressed',x.dataset.m===M));sec.querySelectorAll('.seg [data-s]').forEach(x=>x.setAttribute('aria-pressed',x.dataset.s===S))};
sec.addEventListener('click',e=>{const b=e.target.closest('.seg [data-m],.seg [data-s]');if(!b)return;if(b.dataset.m)M=b.dataset.m;if(b.dataset.s)S=b.dataset.s;apply()})})();

(()=>{const nav=document.getElementById('fnav');if(!nav)return;const links=[...nav.querySelectorAll('a')],secs=links.map(a=>document.querySelector(a.getAttribute('href')));
const upd=()=>{nav.classList.toggle('on',scrollY>360);let k=-1;secs.forEach((el,i)=>{if(el&&el.getBoundingClientRect().top<innerHeight*.4)k=i});links.forEach((a,i)=>a.classList.toggle('act',i===k))};
addEventListener('scroll',upd,{passive:true});upd()})();
(()=>{const g=document.getElementById('gt'),l=document.getElementById('gl'),r=document.getElementById('gr');if(!g||!l)return;
const go=x=>g.querySelectorAll('.gtrack').forEach(t=>t.scrollBy({left:x,behavior:'smooth'}));l.onclick=()=>go(-560);r.onclick=()=>go(560)})();

(()=>{const seg=document.querySelector('.seg.sc');if(!seg)return;seg.addEventListener('click',e=>{const b=e.target.closest('[data-m]');if(!b)return;
seg.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',x===b));document.querySelectorAll('#category .cgs').forEach(p=>{p.hidden=p.dataset.mode!==b.dataset.m})})})();
'''

if __name__ == '__main__':
    facts = collect_facts()
    if '--artifact' in sys.argv:
        p = Path(sys.argv[sys.argv.index('--artifact') + 1])
        p.write_text(page(facts, False), encoding='utf-8')
    else:
        p = OUT / 'brief.html'
        p.write_text(page(facts, True), encoding='utf-8')
    print(p)
