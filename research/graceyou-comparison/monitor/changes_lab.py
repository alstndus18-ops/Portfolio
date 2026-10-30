"""'변화' 섹션 시각화 시안을 한 페이지에 나란히. brief.py의 토큰·툴팁을 그대로 쓴다.
  python monitor/changes_lab.py   # monitor/out/changes-lab.html (thumbs/ 상대경로)
"""
import json
import math
import re
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# brief가 build를 collect보다 먼저 import한다(tools/build.py가 잡히지 않게)
from brief import CHANGE_NOTES, CSS, JS, ORDER, REF, SEQ0, SEQ1, esc, ink_on, man, mix, tip, won  # noqa: E402
from build import model_key, model_units, runs_by_date  # noqa: E402
from collect import BRANDS  # noqa: E402

OUT = Path(__file__).resolve().parent / 'out'
KINDS = (('down', '↓', '가격 인하', 'k-dn'), ('up', '↑', '가격 인상', 'k-up'), ('new', '+', '신규 등록', 'k-nw'), ('gone', '−', '목록에서 빠짐', 'k-gn'))
LAB = {k: lab for k, _, lab, _ in KINDS}
NAME = {b: BRANDS[b]['name'] for b in ORDER}
REPS = {b: runs_by_date(b) for b in ORDER}
DAYS = sorted({d for b in ORDER for d in REPS[b]})
COLS = DAYS[1:][-10:]
md = lambda d: d[5:].replace('-', '.')  # noqa: E731


def units(b, run):
    return model_units(b, [p for p in run['products'] if p['in_clothing_scope'] and p['sale_price']])


def model_prices(b, run):
    """상품(색상 묶음) → 가장 낮은 판매가의 상품 행."""
    return {model_key(b, p): p for p in units(b, run)}


def events(b, d):
    """(상태, 사건). 상태: ok / none(그날 수집 없음) / first / partial."""
    if d not in REPS[b]:
        return 'none', None
    prev = DAYS[DAYS.index(d) - 1]
    if prev not in REPS[b]:
        return 'first', None
    r0, r1 = REPS[b][prev], REPS[b][d]
    if r0['status'] != 'complete' or r1['status'] != 'complete':
        return 'partial', None
    m0, m1 = model_prices(b, r0), model_prices(b, r1)
    ev = {k: [] for k, *_ in KINDS}
    for k, p in m1.items():
        if k not in m0:
            ev['new'].append((None, p))
        elif p['sale_price'] != m0[k]['sale_price']:
            ev['down' if p['sale_price'] < m0[k]['sale_price'] else 'up'].append((m0[k], p))
    ev['gone'] = [(p, None) for k, p in m0.items() if k not in m1]
    return 'ok', ev


EV = {(b, d): events(b, d) for b in ORDER for d in COLS}
DIM = {'none': '-', 'first': '첫 수집', 'partial': '수집 불완전'}


def ev_lines(b, d, ev, per=3):
    lines = [f'{NAME[b]} · {md(d)}', CHANGE_NOTES.get((b, d), '')]
    for key, _, lab, _ in KINDS:
        if ev[key]:
            lines.append(f'{lab} {len(ev[key]):,}개')
            for p0, p1 in ev[key][:per]:
                p = p1 or p0
                lines.append(f'  {p["name"][:28]}  ' + (f'{won(p0["sale_price"])} → {won(p1["sale_price"])}' if p0 and p1 else won(p['sale_price'])))
    if not any(ev.values()):
        lines.append('바뀐 것 없음')
    return lines


# ---------- A 달력 (brief.py 현재 방식) ----------
def sec_a():
    head = ''.join(f'<span>{md(d)}</span>' for d in COLS)
    rows = ''
    for b in ORDER:
        cells = ''
        for d in COLS:
            s, ev = EV[(b, d)]
            if s != 'ok':
                cells += f'<div class="cell dim">{DIM[s]}</div>'
                continue
            chips = ''.join(f'<span class="chg {cls}"><i>{sym}</i>{len(ev[k]):,}</span>' for k, sym, _, cls in KINDS if ev[k]) or '<span class="chg none">·</span>'
            cells += f'<div class="cell" tabindex="0" data-tip="{tip(*ev_lines(b, d, ev))}">{chips}</div>'
        rows += f'<div class="clr{" me" if b == REF else ""}"><span class="cln">{esc(NAME[b])}</span>{cells}</div>'
    key = ''.join(f'<span class="{cls}"><i>{sym}</i>{lab}</span>' for _, sym, lab, cls in KINDS)
    return f'<div class="cal" style="--n:{len(COLS)}"><div class="clh"><span></span>{head}</div>{rows}</div><div class="key clk">{key}</div>'


# ---------- B 날짜별 피드: 큰 사건부터 ----------
def sec_b():
    out = ''
    for d in reversed(COLS):
        items = []
        for b in ORDER:
            s, ev = EV[(b, d)]
            if s != 'ok':
                continue
            note = CHANGE_NOTES.get((b, d))
            if note:
                items.append((10 ** 9, f'<div class="fd note{" me" if b == REF else ""}"><span class="fs">※</span><span class="ft"><b>{esc(NAME[b])}</b> · {esc(note)}</span><span class="fnn"></span></div>'))
            for k, sym, lab, cls in KINDS:
                n = len(ev[k])
                if n:
                    t = tip(f'{NAME[b]} · {lab} {n:,}개', *[f'{(p1 or p0)["name"][:28]}  ' + (f'{won(p0["sale_price"])} → {won(p1["sale_price"])}' if p0 and p1 else won((p1 or p0)['sale_price'])) for p0, p1 in ev[k][:6]])
                    items.append((n, f'<div class="fd{" me" if b == REF else ""}" tabindex="0" data-tip="{t}"><span class="fs {cls}">{sym}</span>'
                                     f'<span class="ft"><b>{esc(NAME[b])}</b> · 상품 {n:,}개 {lab}</span><span class="fnn {cls}">{n:,}</span></div>'))
        items.sort(key=lambda x: -x[0])
        body = ''.join(h for _, h in items) or '<div class="fd empty">-</div>'
        out += f'<div class="fday"><h3>{md(d)}</h3><div class="flist">{body}</div></div>'
    return f'<div class="feed">{out}</div>'


# ---------- C 가격이 바뀐 상품 카드 ----------
def sec_c():
    tix_path = OUT / 'thumbs' / 'index.json'
    tix = json.loads(tix_path.read_text(encoding='utf-8')) if tix_path.exists() else {'items': {}, 'cell': [180, 240], 'cols': 10}
    sheets = {}
    for fn, _, row in tix['items'].values():
        sheets[fn] = max(sheets.get(fn, 0), row + 1)
    cw, ch, co = tix['cell'][0], tix['cell'][1], tix['cols']
    clean = lambda t: re.sub(r'\s+', ' ', re.sub(r'\[[A-Z0-9-]{6,}\]|\s*\([A-Z]{2,}[0-9][A-Z0-9]*\)|-\d+color', '', t or '')).strip()  # noqa: E731
    panes, counts = '', {}
    for key in ('down', 'up'):
        cards = []
        for b in ORDER:
            for d in COLS:
                s, ev = EV[(b, d)]
                if s != 'ok':
                    continue
                for p0, p1 in ev[key]:
                    pct = (p1['sale_price'] / p0['sale_price'] - 1) * 100
                    mk = model_key(b, p1)  # 대표 색상에 썸네일이 없으면 같은 상품의 다른 색상 썸네일
                    hit = next((tix['items'][q['product_id'] + '|' + b] for q in [p1] + REPS[b][d]['products']
                                if (q is p1 or model_key(b, q) == mk) and q['product_id'] + '|' + b in tix['items']), None)
                    # 썸네일 시트는 셀 크기 그대로라 카드 폭(150px)에 맞게 줄인다
                    k = 150 / cw
                    img = (f'<div class="pi" style="background-image:url(thumbs/{hit[0]});background-size:{co * cw * k:.0f}px {sheets[hit[0]] * ch * k:.0f}px;'
                           f'background-position:-{hit[1] * cw * k:.0f}px -{hit[2] * ch * k:.0f}px"></div>') if hit else '<div class="pi nil">-</div>'
                    cards.append((-abs(pct), f'<a class="pc{" me" if b == REF else ""}" href="{esc(p1["url"])}" target="_blank" rel="noopener">{img}'
                                             f'<span class="pb">{esc(NAME[b])} · {md(d)}</span><span class="pn2">{esc(clean(p1["name"]))}</span>'
                                             f'<span class="pp"><s>{p0["sale_price"]:,}</s> → <b>{p1["sale_price"]:,}</b></span>'
                                             f'<span class="pct {"k-dn" if key == "down" else "k-up"}">{pct:+.0f}%</span></a>'))
        cards.sort(key=lambda x: x[0])
        counts[key] = len(cards)
        panes += f'<div class="pcs" data-k="{key}"{"" if key == "down" else " hidden"}>{"".join(h for _, h in cards) or "<div class=pnone>-</div>"}</div>'
    seg = (f'<div class="seg sk" role="group" aria-label="변화 종류"><button type="button" data-k="down" aria-pressed="true">인하 {counts["down"]:,}</button>'
           f'<button type="button" data-k="up" aria-pressed="false">인상 {counts["up"]:,}</button></div>')
    return seg + panes


# ---------- D 히트맵: 칸 농도 = 변화한 상품 수 ----------
def sec_d():
    tot = {k: sum(len(v) for v in ev.values()) for k, (s, ev) in EV.items() if s == 'ok'}
    top = max(tot.values(), default=0)
    head = ''.join(f'<span>{md(d)}</span>' for d in COLS)
    rows = ''
    for b in ORDER:
        cells = ''
        for d in COLS:
            s, ev = EV[(b, d)]
            if s != 'ok':
                cells += f'<div class="hc dim">{DIM[s]}</div>'
                continue
            n = tot[(b, d)]
            bg = mix(SEQ0, SEQ1, math.log1p(n) / math.log1p(top)) if top else SEQ0
            cells += f'<div class="hc" tabindex="0" style="background:{bg};color:{ink_on(bg)}" data-tip="{tip(*ev_lines(b, d, ev, 5))}">{n:,}</div>'
        rows += f'<div class="clr{" me" if b == REF else ""}"><span class="cln">{esc(NAME[b])}</span>{cells}</div>'
    ramp = ''.join(f'<i style="background:{mix(SEQ0, SEQ1, t / 4)}"></i>' for t in range(5))
    return (f'<div class="cal hm2" style="--n:{len(COLS)}"><div class="clh"><span></span>{head}</div>{rows}</div>'
            f'<div class="key"><span class="ramp"><em>0</em>{ramp}<em>{top:,}</em></span><span>변화한 상품 수</span></div>')


# ---------- E 브랜드별 추이 미니 차트 ----------
def snap(b, d):
    us = units(b, REPS[b][d])
    if not us:
        return None
    on = sum(1 for p in us if p.get('regular_price') and p['regular_price'] > p['sale_price'])
    return dict(share=on / len(us) * 100, med=st.median(p['sale_price'] for p in us), n=len(us), ok=REPS[b][d]['status'] == 'complete')


def sec_e():
    S = {(b, d): snap(b, d) for b in ORDER for d in DAYS if d in REPS[b]}
    S = {k: v for k, v in S.items() if v}
    METS = (('share', '할인 중인 상품', lambda v: f'{v:.0f}%'), ('med', '판매가 중앙값', lambda v: f'{man(v)}만'), ('n', '상품 수', lambda v: f'{v:,}'))
    W, H, PX, PY = 240, 64, 10, 10
    x = lambda i: PX + (W - 2 * PX) * (i / (len(DAYS) - 1) if len(DAYS) > 1 else .5)  # noqa: E731
    head = ''.join(f'<span>{lab}</span>' for _, lab, _ in METS)
    rows = ''
    for b in ORDER:
        cells = ''
        for key, lab, fmt in METS:
            pts = [(i, d, S[(b, d)]) for i, d in enumerate(DAYS) if (b, d) in S]
            vs = [s[key] for _, _, s in pts]
            lo, hi = (0, 100) if key == 'share' else (min(vs), max(vs)) if vs else (0, 1)  # 비중은 0~100% 고정: 작은 차이가 크게 보이지 않게
            pad = (hi - lo) * .15 or max(abs(hi) * .05, 1)
            y = lambda v: PY + (H - 2 * PY) * (1 - (v - lo + pad) / (hi - lo + 2 * pad))  # noqa: E731
            line = ' '.join(f'{x(i):.1f},{y(s[key]):.1f}' for i, _, s in pts)
            dots = ''.join(f'<circle cx="{x(i):.1f}" cy="{y(s[key]):.1f}" r="4.5" data-tip="{tip(f"{NAME[b]} · {md(d)}", f"{lab} {fmt(s[key])}", "" if s["ok"] else "수집 불완전")}"/>' for i, d, s in pts)
            base = ''.join(f'<line x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{H - 2}" y2="{H}"/>' for i in range(len(DAYS)))
            last = fmt(vs[-1]) if vs else '-'
            delta = ''
            if len(vs) > 1 and fmt(abs(vs[-1] - vs[-2])).strip('0%만') not in ('', '.'):
                dv = vs[-1] - vs[-2]
                delta = f'<em>{"+" if dv > 0 else "−"}{fmt(abs(dv))}</em>'
            cells += (f'<div class="mini"><svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true"><g class="tk">{base}</g>'
                      f'{f"<polyline points={chr(34)}{line}{chr(34)}/>" if len(pts) > 1 else ""}{dots}</svg><b>{last}{delta}</b></div>')
        rows += f'<div class="mrw{" me" if b == REF else ""}"><span class="cln">{esc(NAME[b])}</span>{cells}</div>'
    axis = f'<span class="mdays">{md(DAYS[0])} ~ {md(DAYS[-1])}</span>' if DAYS else ''
    return f'<div class="minis"><div class="mhd"><span></span>{head}</div>{rows}</div><div class="key">{axis}</div>'


# ---------- F 요약 숫자 타일: 최근 기간 ----------
def sec_f():
    d = COLS[-1] if COLS else None
    tiles = ''
    for b in ORDER:
        s, ev = EV.get((b, d), ('none', None))
        nums = ''.join(f'<span class="tn {cls}"><i>{sym}</i><b>{len(ev[k]):,}</b><small>{lab}</small></span>' if ev else
                       f'<span class="tn nil"><i>{sym}</i><b>-</b><small>{lab}</small></span>' for k, sym, lab, cls in KINDS)
        note = CHANGE_NOTES.get((b, d), '') or (DIM[s] if s != 'ok' else '')
        tiles += f'<div class="tile{" me" if b == REF else ""}"><h3>{esc(NAME[b])}</h3><div class="tns">{nums}</div><div class="tnote">{esc(note) or "&nbsp;"}</div></div>'
    period = f'{md(DAYS[DAYS.index(d) - 1])} → {md(d)}' if d else '-'
    return f'<div class="key"><span class="per">{period}</span></div><div class="tiles">{tiles}</div>'


# ---------- G 상품 수 증감: 신규(오른쪽) · 빠짐(왼쪽) ----------
def sec_g():
    d = COLS[-1] if COLS else None
    vals = {b: EV[(b, d)][1] for b in ORDER if d and EV[(b, d)][0] == 'ok'}
    top = max([max(len(e['new']), len(e['gone'])) for e in vals.values()] or [0]) or 1
    rows = ''
    for b in ORDER:
        e = vals.get(b)
        if not e:
            rows += f'<div class="gr2{" me" if b == REF else ""}"><span class="cln">{esc(NAME[b])}</span><span class="gv l">-</span><div class="gbars"></div><span class="gv">-</span><span class="gnet">-</span></div>'
            continue
        nn, ng = len(e['new']), len(e['gone'])
        t = tip(f'{NAME[b]} · {md(d)}', f'신규 등록 {nn:,}개', f'목록에서 빠짐 {ng:,}개', CHANGE_NOTES.get((b, d), ''))
        rows += (f'<div class="gr2{" me" if b == REF else ""}" tabindex="0" data-tip="{t}"><span class="cln">{esc(NAME[b])}</span><span class="gv l">{ng:,}</span>'
                 f'<div class="gbars"><i class="gg" style="width:{ng / top * 50:.1f}%"></i><i class="gn2" style="width:{nn / top * 50:.1f}%"></i></div>'
                 f'<span class="gv">{nn:,}</span><span class="gnet">{f'{nn - ng:+,}' if nn != ng else 0}</span></div>')
    period = f'{md(DAYS[DAYS.index(d) - 1])} → {md(d)}' if d else '-'
    return (f'<div class="gh2"><span></span><span class="gv l">빠짐</span><span></span><span class="gv">신규</span><span class="gnet">순증감</span></div>{rows}'
            f'<div class="key"><span class="per">{period}</span></div>')


PAGE_CSS = r'''
body{font-size:16px}
.wrap{gap:72px}
h1{font-size:clamp(48px,7vw,88px)}
.key{font-size:15px}
'''

LAB_CSS = r'''
.lab-sec{display:grid;gap:22px;min-width:0;padding-top:28px;border-top:1px solid var(--rule)}
.lab-sec h2{font-size:28px}
.lab-sec h2 b{font:600 34px/1 var(--serif-en);color:var(--accent)}
.lab-sec .vt{margin:0;font:600 22px var(--serif);display:flex;gap:10px;align-items:baseline}
.lab-sec .vt b{font:600 28px/1 var(--serif-en);color:var(--accent)}
#change{gap:56px}
.per{font:600 20px var(--serif-en);color:var(--ink)}
/* B 피드 */
.feed{display:grid;gap:30px}
.fday{display:grid;grid-template-columns:5em minmax(0,1fr);gap:18px;align-items:start}
.fday h3{margin:0;font:600 30px/1 var(--serif-en);font-variant-numeric:lining-nums}
.flist{display:grid;gap:8px}
.fd{display:grid;grid-template-columns:2em minmax(0,1fr) auto;align-items:center;gap:12px;padding:12px 16px;background:var(--paper);border:1px solid var(--line);border-radius:8px;font-size:17px;outline:none}
.fd:hover,.fd:focus-visible{border-color:var(--accent)}
.fd b{font-weight:600}
.fd.me b{color:var(--accent)}
.fd.note{background:var(--accent-soft);border-color:#E3D0D6}
.fd.empty{display:block;color:var(--muted)}
.fs{font:600 22px var(--sans);text-align:center}
.fnn{font:600 30px/1 var(--serif-en);font-variant-numeric:lining-nums tabular-nums}
/* C 상품 카드 */
.sk button{font-size:16px}
.pcs{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:22px 16px}
.pc{display:grid;gap:5px;align-content:start;color:inherit;text-decoration:none;position:relative}
.pi{width:150px;height:200px;border-radius:3px;background-color:#EEE9E5;background-repeat:no-repeat}
.pi.nil{display:grid;place-items:center;color:var(--muted);font-size:20px}
.pb{font-size:14px;color:var(--muted)}
.pc.me .pb{color:var(--accent);font-weight:600}
.pn2{font-size:14.5px;line-height:1.4;height:2.8em;overflow:hidden}
.pp{font:500 17px/1.2 var(--serif-en);font-variant-numeric:lining-nums}
.pp s{color:var(--muted)}
.pp b{font-weight:600;font-size:21px}
.pct{position:absolute;top:8px;left:8px;padding:3px 8px;border-radius:999px;background:rgba(255,255,255,.92);font:600 18px/1 var(--serif-en)}
.pnone{color:var(--muted);font-size:22px}
/* D 히트맵 */
.hm2 .clr{min-height:70px}
.hc{display:grid;place-items:center;min-height:58px;margin:5px 0;border-radius:6px;font:600 28px/1 var(--serif-en);font-variant-numeric:lining-nums;outline:none;transition:transform .2s var(--ease)}
.hc:hover,.hc:focus-visible{transform:scale(1.03)}
.hc.dim{background:transparent;border:1px dashed var(--line);color:var(--muted);font:400 15px var(--sans)}
/* E 미니 차트 */
.minis{display:grid;overflow-x:auto}
.mhd,.mrw{display:grid;grid-template-columns:7.5em repeat(3,minmax(0,1fr));column-gap:18px;align-items:center;min-width:720px}
.mhd{font-size:15px;color:var(--muted);height:34px}
.mrw{border-top:1px solid var(--rule);min-height:88px}
.mrw:last-child{border-bottom:1px solid var(--rule)}
.mrw.me .cln{color:var(--accent);font-weight:600}
.mini{display:grid;grid-template-columns:minmax(60px,1fr) auto;align-items:center;gap:12px}
.mini svg{width:100%;height:64px;overflow:visible}
.mini polyline{fill:none;stroke:#9A887E;stroke-width:2;vector-effect:non-scaling-stroke}
.mrw.me .mini polyline{stroke:var(--accent)}
.mini circle{fill:var(--ink);stroke:var(--bg);stroke-width:2;vector-effect:non-scaling-stroke}
.mrw.me .mini circle{fill:var(--accent)}
.mini .tk line{stroke:var(--rule);vector-effect:non-scaling-stroke}
.mini b{font:600 24px/1.1 var(--serif-en);font-variant-numeric:lining-nums;text-align:right;min-width:3.6em}
.mini b em{display:block;font:500 14px var(--sans);font-style:normal;color:var(--muted)}
.mdays{font:500 16px var(--serif-en)}
/* F 타일 */
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
.tile{display:grid;gap:12px;padding:18px 18px 14px;background:var(--paper);border:1px solid var(--line);border-radius:10px}
.tile.me{border-color:var(--accent);box-shadow:inset 0 3px 0 var(--accent)}
.tile h3{margin:0;font:600 19px var(--serif)}
.tile.me h3{color:var(--accent)}
.tns{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}
.tn{display:grid;justify-items:center;gap:2px}
.tn i{font:600 16px var(--sans);font-style:normal}
.tn b{font:600 30px/1 var(--serif-en);font-variant-numeric:lining-nums}
.tn small{font-size:12.5px;color:var(--muted);text-align:center;line-height:1.25}
.tn.nil{color:var(--muted)}
.tnote{font-size:14.5px;color:var(--muted)}
/* G 증감 */
.gh2,.gr2{display:grid;grid-template-columns:7.5em 4em minmax(0,1fr) 4em 4.5em;column-gap:12px;align-items:center}
.gh2{font-size:15px;color:var(--muted)}
.gr2{min-height:56px;border-top:1px solid var(--rule);outline:none}
.gr2:last-of-type{border-bottom:1px solid var(--rule)}
.gr2:hover,.gr2:focus-visible{background:rgba(122,78,92,.05)}
.gr2.me .cln{color:var(--accent);font-weight:600}
.gv{font:600 22px var(--serif-en);font-variant-numeric:lining-nums}
.gv.l{text-align:right}
.gnet{font:600 22px var(--serif-en);text-align:right;font-variant-numeric:lining-nums}
.gbars{position:relative;height:22px}
.gbars::before{content:"";position:absolute;left:50%;top:-6px;bottom:-6px;border-left:1px solid var(--ink)}
.gbars i{position:absolute;top:0;bottom:0}
.gg{right:50%;background:#B3A59B;border-radius:4px 0 0 4px}
.gn2{left:50%;background:var(--accent);border-radius:0 4px 4px 0}
@media (max-width:640px){.fday{grid-template-columns:1fr}.fd{font-size:15px}.gh2,.gr2{grid-template-columns:4.6em 2.8em minmax(0,1fr) 2.8em 3.4em;column-gap:6px}.gv,.gnet{font-size:17px}.tns{gap:2px}}
'''

LAB_JS = r'''
(()=>{const seg=document.querySelector('.seg.sk');if(!seg)return;seg.addEventListener('click',e=>{const b=e.target.closest('[data-k]');if(!b)return;
seg.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',x===b));document.querySelectorAll('.pcs').forEach(p=>{p.hidden=p.dataset.k!==b.dataset.k})})})();
'''


VARIANTS = [('a', 'A', '달력', sec_a), ('b', 'B', '피드', sec_b), ('c', 'C', '상품 카드', sec_c), ('d', 'D', '히트맵', sec_d),
            ('e', 'E', '추이', sec_e), ('f', 'F', '숫자 타일', sec_f), ('g', 'G', '신규·빠짐', sec_g)]


def page():
    secs = VARIANTS
    nav = ''.join(f'<a href="#v-{i}">{L} {t}</a>' for i, L, t, _ in secs)
    body = ''.join(f'<section class="lab-sec" id="v-{i}"><h2><b>{L}</b>{t}</h2>{fn()}</section>\n' for i, L, t, fn in secs)
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>변화 시안</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=Noto+Serif+KR:wght@400;500;600&family=IBM+Plex+Sans+KR:wght@400;500;600&display=swap">
<style>{CSS}{PAGE_CSS}{LAB_CSS}</style></head><body>
<div class="tipbox" id="tip" role="tooltip" hidden></div>
<nav class="fnav" id="fnav" aria-label="시안">{nav}</nav>
<main class="wrap">
<header class="mast"><h1><span>변화 시안</span></h1></header>
{body}</main>
<script>{JS}{LAB_JS}</script></body></html>'''


if __name__ == '__main__':
    assert DAYS, 'snapshots/monitor에 날짜가 없다'
    html_ = page()
    assert html_.count('<section class="lab-sec"') == 7
    p = OUT / 'changes-lab.html'
    p.write_text(html_, encoding='utf-8')
    print(p, f'days={DAYS}')
