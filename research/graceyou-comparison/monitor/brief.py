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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import runs_by_date  # noqa: E402  먼저: collect가 tools/를 경로 앞에 넣어 같은 이름의 tools/build.py가 잡힌다
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

    # ---------- 핵심 수치 ----------
    h_gu = f['hearts'][WC_CD[REF]]
    stats = [
        (f'{sum(n.values()):,}', '모델', ''),
        (f'{h_gu[1]}', 'W컨셉 찜 순위', tip(f'찜 {h_gu[0]:,} · 여성 브랜드 5,871개 중', *[f'{name[b]} {f["hearts"][WC_CD[b]][1]:,}위' for b in ORDER if b in WC_CD and b != REF], '오르 미입점', '2026-10-27')),
        (f'{sum(1 for b in ORDER if not share[b])}/{len(ORDER)}', '정가 판매', tip(*[f'{name[b]} 할인 표시 {share[b]:.0f}%' for b in ORDER])),
    ]
    stat_html = ''.join(f'<div class="stat"{f" tabindex=0 data-tip={chr(34)}{t}{chr(34)}" if t else ""}><b>{v}</b><span>{l}</span></div>' for v, l, t in stats)

    # ---------- 가격 포지션: 판매가 Q1~Q3 띠 + 정가 중앙 ○ + 판매가 중앙 ● ----------
    lo, hi = 0, 400000
    pos = lambda v: (min(max(v, lo), hi) - lo) / (hi - lo) * 100  # noqa: E731
    ticks = ''.join(f'<span class="tick" style="left:{pos(v):.2f}%"><i>{man(v, 0)}</i></span>' for v in range(lo, hi + 1, 100000))
    order = [REF] + sorted([b for b in ORDER if b != REF], key=lambda b: -sale[b])
    rows_db = ''
    for i, b in enumerate(order):
        q1, q3 = num(tot[b]['sale_q1']), num(tot[b]['sale_q3'])
        s, r = pos(sale[b]), pos(reg[b])
        t = tip(name[b], f'판매가 중앙 {won(sale[b])}', f'정가 중앙 {won(reg[b])}' if reg[b] > sale[b] else '정가 = 판매가',
                f'가운데 50% {won(q1)} ~ {won(q3)}', f'할인 표시 {share[b]:.0f}%' + (f' · 폭 {dmed[b]:.0f}%' if share[b] else ''), f'모델 {n[b]}개')
        gap = f'<span class="gap" style="left:{s:.2f}%;width:{r - s:.2f}%"></span><span class="mk reg" style="left:{r:.2f}%"></span>' if reg[b] > sale[b] else ''
        rows_db += (f'<div class="pr{" me" if b == REF else ""}" style="--i:{i}" tabindex="0" data-tip="{t}"><span class="pn">{esc(name[b])}</span>'
                    f'<span class="lane"><span class="iqr" style="left:{pos(q1):.2f}%;width:{pos(q3) - pos(q1):.2f}%"></span>{gap}'
                    f'<span class="mk sale" style="left:{s:.2f}%"></span></span><span class="pv">{man(sale[b])}<small>{f"−{(1 - sale[b] / reg[b]) * 100:.0f}%" if reg[b] > sale[b] else ""}</small></span></div>')

    # ---------- 카테고리 × 브랜드: 판매가 중앙, 색 = 그레이스유 대비 ----------
    head = ''.join(f'<th scope="col">{esc(CAT_SHORT[c])}</th>' for c in CATS)
    body = ''
    for b in ORDER:
        cells = ''
        for c in CATS:
            r = by[b].get(c)
            k = int(r['n']) if r and r['n'] else 0
            if not k:
                cells += '<td class="nil">-</td>'
                continue
            v, g = num(r['sale_median']), num(by[REF][c]['sale_median'])
            ratio = v / g
            bg = MID if b == REF else diverge(ratio)
            rv = num(r['regular_median'])
            t = tip(f'{name[b]} · {CAT_SHORT[c]}', f'판매가 중앙 {won(v)}', f'정가 중앙 {won(rv)}' if rv and rv > v else '',
                    f'가운데 50% {won(num(r["sale_q1"]))} ~ {won(num(r["sale_q3"]))}', f'모델 {k}개 · 할인 표시 {num(r["discount_share_pct"]) or 0:.0f}%',
                    '' if b == REF else f'그레이스유 대비 {(ratio - 1) * 100:+.0f}%')
            cells += f'<td class="{"thin" if k < 5 else ""}" style="background:{bg};color:{ink_on(bg)}" tabindex="0" data-tip="{t}">{man(v)}</td>'
        body += f'<tr class="{"me" if b == REF else ""}"><th scope="row">{esc(name[b])}</th>{cells}</tr>'
    scale = ''.join(f'<i style="background:{diverge(x)}"></i>' for x in (1 / 1.8, 1 / 1.4, 1 / 1.15, 1, 1.15, 1.4, 1.8))

    # ---------- 할인 운영: x 할인 표시 비율, y 할인 폭 중앙 ----------
    ev = {}
    for e in f['events']:
        b = next(k for k, v in name.items() if v == e['brand'])
        if e['event'] != '프로모션 표시 없이 할인' and (e['models'] or '쿠폰' in e['event']):
            ev.setdefault(b, []).append(e['event'] + (f' {e["discount"]}' if e['discount'] and e['discount'] not in e['event'] else ''))
    W, H, PL, PB, PT, PR = 640, 300, 44, 34, 14, 18
    X = lambda v: PL + v / 100 * (W - PL - PR)  # noqa: E731
    Y = lambda v: H - PB - v / 50 * (H - PB - PT)  # noqa: E731
    grid = ''.join(f'<line x1="{X(v):.1f}" x2="{X(v):.1f}" y1="{PT}" y2="{H - PB}"/><text x="{X(v):.1f}" y="{H - PB + 18}" text-anchor="middle">{v}%</text>' for v in range(0, 101, 25))
    grid += ''.join(f'<line x1="{PL}" x2="{W - PR}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/><text x="{PL - 8}" y="{Y(v) + 4:.1f}" text-anchor="end">{v}%</text>' for v in range(0, 51, 10))
    pts = {}
    for b in ORDER:
        pts.setdefault((round(share[b]), round(dmed[b])), []).append(b)
    dots = ''
    LBL = {'kume': (-10, 4, 'end'), 'voyonn': (-10, -6, 'end'), 'lamerei': (-10, 4, 'end'), 'jj': (-10, 4, 'end'), 'nw': (10, 4, 'start')}
    for (sx, sy), bs in pts.items():
        me = REF in bs
        label = '·'.join(name[b] for b in bs)
        dx, dy, anc = LBL.get(bs[0], (10, -8, 'start'))
        t = tip(*[f'{name[b]} — 할인 표시 {share[b]:.0f}% · 폭 {dmed[b]:.0f}%' + (' · ' + ' / '.join(dict.fromkeys(ev[b]))[:140] if ev.get(b) else '') for b in bs])
        dots += (f'<g class="pt{" me" if me else ""}" tabindex="0" data-tip="{t}"><circle cx="{X(sx):.1f}" cy="{Y(sy):.1f}" r="{7 if me else 6}"/>'
                 f'<text x="{X(sx) + dx:.1f}" y="{Y(sy) + dy:.1f}" text-anchor="{anc}">{esc(label)}</text></g>')
    scatter = (f'<svg viewBox="0 0 {W} {H}" class="sc" role="img" aria-label="브랜드별 할인 표시 비율과 할인 폭"><g class="gr">{grid}</g>'
               f'<text class="ax" x="{W - PR}" y="{H - 4}" text-anchor="end">할인 표시 비율</text><text class="ax" x="{PL - 36}" y="{PT - 2}" text-anchor="start">할인 폭</text>{dots}</svg>')

    # ---------- 상품 구성: 카테고리 비중 ----------
    comp = ''
    for b in ORDER:
        ks = {c: int(by[b][c]['n'] or 0) if c in by[b] else 0 for c in CATS}
        s = sum(ks.values()) or 1
        cells = ''
        for c in CATS:
            p = ks[c] / s
            bg = mix(SEQ0, SEQ1, min(1, p / 0.45))
            cells += f'<td style="background:{bg};color:{ink_on(bg)}" tabindex="0" data-tip="{tip(f"{name[b]} · {CAT_SHORT[c]}", f"{ks[c]}개 · {p * 100:.0f}%")}">{p * 100:.0f}</td>'
        comp += f'<tr class="{"me" if b == REF else ""}"><th scope="row">{esc(name[b])}</th>{cells}<td class="tot">{s}</td></tr>'

    # ---------- 그레이스유 공식몰 ----------
    obs = [
        (f'{f["gu_sold"] / f["gu_pages"] * 100:.0f}%', '품절 노출',
         f'의류 {f["gu_pages"]}개 중 {f["gu_sold"]}개 품절 표시 상태로 목록 노출', '재입고 예정·단종 구분, 재입고 알림'),
        (f'{f["mat_newest_img"]}/{f["mat_newest"]}', '소재 텍스트 누락',
         f'최근 등록 {f["mat_newest"]}개 모델 중 {f["mat_newest_img"]}개는 혼용률이 이미지에만 · 이전 상품은 {f["mat_older"]}개 중 {f["mat_older_text"]}개 텍스트', '상세 상단에 혼용률·실측 텍스트'),
        (f'{f["gu_cer"]} · {f["gu_pre"]}', 'CEREMONY · PRE-ORDER',
         '비교 6개 브랜드에 없는 행사복·예약 판매 운영', '행사복 매출 비중 확인 후 비교군 확장'),
    ]
    obs_html = ''.join(f'<article class="ob" style="--i:{i}"><b>{esc(v)}</b><h3>{esc(t)}</h3><p>{esc(fact)}</p><p class="do">{esc(do)}</p></article>'
                       for i, (v, t, fact, do) in enumerate(obs))

    # ---------- 변화 ----------
    cnt = {}
    for c in f['changes']:
        b = next(k for k, v in name.items() if v == c['brand'])
        kind = re.sub(r'\(.*', '', c['change']).strip()
        cnt.setdefault(b, {}).setdefault(kind, []).append(c)
    log = ''
    for b in ORDER:
        if b not in cnt:
            continue
        kinds = {k: v for k, v in cnt[b].items() if not (k == '표시 할인율 변화' and '판매가 변화' in cnt[b])}
        for k, cs in sorted(kinds.items(), key=lambda kv: -len(kv[1])):
            ids = {c['product_id'] for c in cs}
            detail = [f'{c["name"]}  {won(float(c["before"]))} → {won(float(c["after"]))}' for c in cs if c['before'] and c['after'] and k == '판매가 변화'][:6]
            if k == '판매가 변화':
                ch = [(float(c['after']) - float(c['before'])) / float(c['before']) * 100 for c in cs if c['before'] and c['after']]
                k = f'판매가 {"인하" if max(ch) < 0 else "인상" if min(ch) > 0 else "변경"}'
                rng = f'{min(ch):+.0f}%' if len(set(round(x) for x in ch)) == 1 else f'{min(ch):+.0f}~{max(ch):+.0f}%'
            else:
                rng = ''
            note = CHANGE_NOTES.get((b, f['date'])) if k.startswith(('판매가', '목록')) else None
            log += (f'<li tabindex="0" data-tip="{tip(*detail) if detail else tip(note or k)}"><span class="lb">{esc(name[b])}</span><span class="lk">{esc(k)}</span>'
                    f'<span class="lc">{len(ids)}</span><span class="lr">{esc(rng)}</span><span class="ln">{esc(note or "")}</span></li>')
            if note:
                CHANGE_NOTES.pop((b, f['date']))

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

    d0, d1 = (f['prev'] or f['date']).replace('-', '.')[2:], f['date'].replace('-', '.')[2:]
    body_html = f'''<title>GRACE U 가격 분석</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=Noto+Serif+KR:wght@400;500;600&family=IBM+Plex+Sans+KR:wght@400;500;600&display=swap">
<style>{CSS}</style>
<div class="tipbox" id="tip" role="tooltip" hidden></div>
<main class="wrap">
<header class="mast">
  <h1><span>GRACE U</span></h1>
  <div class="stats">{stat_html}</div>
  <p class="date">{d1.replace(".", " . ")}</p>
</header>

<section class="sec" id="price">
  <h2>가격 포지션</h2>
  <div class="prices"><div class="axis">{ticks}</div>{rows_db}</div>
  <div class="key"><span><i class="k-sale"></i>판매가 중앙</span><span><i class="k-reg"></i>정가 중앙</span><span><i class="k-iqr"></i>가운데 50%</span><span class="unit">만 원</span></div>
</section>

<section class="sec" id="category">
  <h2>카테고리별 판매가</h2>
  <div class="scroll"><table class="hm"><thead><tr><th></th>{head}</tr></thead><tbody>{body}</tbody></table></div>
  <div class="key"><span class="ramp"><em>저가</em>{scale}<em>고가</em></span><span class="unit">만 원 · 그레이스유 대비</span></div>
</section>

<div class="pair">
<section class="sec" id="discount">
  <h2>할인 운영</h2>
  {scatter}
</section>

<section class="sec" id="mix">
  <h2>카테고리 구성</h2>
  <div class="scroll"><table class="hm mixt"><thead><tr><th></th>{head}<th>모델</th></tr></thead><tbody>{comp}</tbody></table></div>
  <div class="key"><span class="unit">%</span></div>
</section>
</div>

<section class="sec" id="graceu">
  <h2>GRACE U 공식몰</h2>
  <div class="obs">{obs_html}</div>
</section>

<div class="pair">
<section class="sec" id="change">
  <h2>변화 <small>{d0} → {d1}</small></h2>
  <ul class="log">{log}</ul>
</section>

<section class="sec small" id="ship">
  <h2>배송 · 반품</h2>
  <table class="st"><thead><tr><th></th><th>배송비</th><th>무료 기준</th><th>반품</th></tr></thead><tbody>{ship}</tbody></table>
</section>
</div>
</main>
<script>{JS}</script>'''
    if standalone:
        head_part, main_part = body_html.split('<div class="tipbox"', 1)
        return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
                f'{head_part}</head><body><div class="tipbox"{main_part}</body></html>')
    return body_html


CSS = r'''
/* 한 열 편집 레이아웃: 큰 세리프 표제 아래 차트가 숨 쉬듯 이어진다. 밝은 단일 테마(그레이스유 공식몰의 흰 바탕·세리프 톤) */
:root{color-scheme:light;--bg:#FBFAF8;--paper:#FFFFFF;--ink:#2B2725;--muted:#8A827D;--line:#ECE7E3;--accent:#7A4E5C;--accent-soft:#F4ECEE;--iqr:#E9E2DE;--reg:#B9AFA9;
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
.k-sale{width:10px;height:10px;border-radius:50%;background:var(--ink)}
.k-reg{width:10px;height:10px;border-radius:50%;border:1.5px solid var(--reg);background:var(--paper)}
.k-iqr{width:22px;height:8px;border-radius:4px;background:var(--iqr)}
.ramp{gap:0!important}.ramp i{width:22px;height:10px}.ramp em{font-style:normal;margin:0 8px}
/* 가격 포지션 */
.prices{position:relative;display:grid;gap:4px;padding-top:30px}
.axis{position:absolute;inset:0 0 0 9.5em;margin-right:5.5em;pointer-events:none}
.tick{position:absolute;top:0;bottom:0;border-left:1px solid var(--line)}
.tick i{position:absolute;top:4px;left:0;transform:translateX(-50%);white-space:nowrap;overflow-wrap:normal;font:italic 13px var(--serif-en);color:var(--muted);background:var(--bg);padding:0 4px}
.pr{position:relative;display:grid;grid-template-columns:9.5em minmax(0,1fr) 5.5em;align-items:center;height:42px;border-radius:6px;outline:none;transition:background .25s var(--ease)}
.pr:hover,.pr:focus-visible{background:rgba(122,78,92,.05)}
.pn{font-size:14px;padding-left:10px}
.pr.me .pn{font-weight:600;color:var(--accent)}
.lane{position:relative;height:100%}
.iqr{position:absolute;top:50%;height:10px;margin-top:-5px;border-radius:5px;background:var(--iqr)}
.gap{position:absolute;top:50%;height:2px;margin-top:-1px;background:var(--reg)}
.mk{position:absolute;top:50%;width:13px;height:13px;border-radius:50%;transform:translate(-50%,-50%)}
.mk.sale{background:var(--ink);box-shadow:0 0 0 3px var(--bg)}
.pr.me .mk.sale{background:var(--accent);width:15px;height:15px}
.mk.reg{background:var(--paper);border:1.5px solid var(--reg)}
.pv{text-align:right;padding-right:10px;font:500 20px/1 var(--serif-en);font-variant-numeric:lining-nums tabular-nums}
.pv small{display:block;margin-top:3px;font:500 11px/1 var(--sans);color:var(--muted)}
.pr.me .pv{color:var(--accent)}
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
/* 공식몰 관찰 */
.obs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border-top:1px solid var(--line)}
.ob{padding:26px 26px 6px 0;display:grid;gap:6px;align-content:start}
.ob+.ob{padding-left:26px;border-left:1px solid var(--line)}
.ob b{font:500 52px/1 var(--serif-en);color:var(--accent);font-variant-numeric:lining-nums;letter-spacing:-.02em}
.ob h3{margin:6px 0 0;font:500 15px/1.4 var(--serif)}
.ob p{margin:0;font-size:13px;color:var(--muted);max-width:34ch}
.ob .do{color:var(--ink);margin-top:6px}
.ob .do::before{content:"→ ";color:var(--accent)}
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
/* 툴팁 */
.tipbox{position:fixed;z-index:20;max-width:320px;padding:12px 14px;background:rgba(43,39,37,.94);color:#F7F3F0;border-radius:8px;font-size:12px;line-height:1.55;pointer-events:none;box-shadow:0 14px 34px -14px rgba(43,39,37,.6);transform:translateY(4px);opacity:0;transition:opacity .15s var(--ease),transform .15s var(--ease)}
.tipbox.on{opacity:1;transform:none}
.tipbox b{display:block;font:500 13px var(--serif);margin-bottom:3px;color:#fff}
[data-tip]{cursor:default}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
/* 등장 */
@media (prefers-reduced-motion:no-preference){
 .pr .iqr,.pr .gap{transform-origin:left;animation:grow .9s var(--ease) backwards;animation-delay:calc(var(--i)*60ms)}
 @keyframes grow{from{transform:scaleX(.6);opacity:.5}}
}
@media (max-width:900px){.pair{grid-template-columns:1fr;gap:88px}.obs{grid-template-columns:1fr}.ob+.ob{padding-left:0;border-left:0;border-top:1px solid var(--line)}.ob{padding-right:0}}
@media (max-width:640px){.wrap{padding-block:44px 64px;gap:64px}.mast{grid-template-columns:1fr}.stats{gap:24px}.stat b{font-size:30px}
 .pr{grid-template-columns:5.6em minmax(0,1fr) 4em}.axis{left:5.6em;margin-right:4em}.pn{font-size:12px;padding-left:4px;line-height:1.25}
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
