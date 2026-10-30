"""한 장 비교 자료(친구가 보여 주며 설명하는 요약본). build.py가 만든 out/*.csv와 최신 수집 원본만 읽는다.
  python monitor/brief.py                      # monitor/out/brief.html (파일 하나로 열리는 독립 HTML)
  python monitor/brief.py --artifact 경로.html  # 같은 내용을 문서 골격 없이 (Artifact 게시용)
숫자는 전부 데이터에서 계산한다. 문장 중 해석·제안은 이 파일의 TEXT에만 있고, 사실 숫자와 섞지 않는다.
"""
import csv
import html
import json
import re
import statistics as st
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
# 비교 이유는 기획서 §10-23·25와 후보 README의 표현을 줄인 것
ROLE = {
    'graceu': ('기준', '우리 브랜드', 'graceu.co.kr'),
    'kume': ('확정', '페미닌 일상복·니트', 'kume-studio.co.kr'),
    'nw': ('확정', '클래식 일상복, 비슷한 예산', 'nothing-written.com'),
    'jj': ('확정', '여성스러운 원피스·블라우스, 할인 운영', '바바더닷컴 JJ지고트관'),
    'orr': ('확정', '테일러링·소재, 드레시한 상의', 'orr.store'),
    'lamerei': ('추천', '절제된 여성미·소재, W컨셉 기사에 함께 언급', 'lamerei.com'),
    'voyonn': ('추천', '엘레강스·클래식, 퀸잇 기사에 함께 언급', 'voyonn.com'),
}
POLICY_KEY = {'graceu': 'gu'}
WC_CD = {'graceu': 108809, 'kume': 102698, 'nw': 103899, 'jj': 113480, 'lamerei': 109224, 'voyonn': 105721}
# 데이터만으로는 이유를 알 수 없는 변화에 사람이 확인한 설명을 붙인다 (브랜드, 비교 끝 날짜)
CHANGE_NOTES = {
    ('orr', '2026-10-30'): '10-29에 열려 있던 1차·2차·TIME SALE 컬렉션 26개가 10-30에 비워졌다(사이트에 "상품이 없습니다"). 삭제가 아니라 세일 종료로 보인다.',
    ('graceu', '2026-10-30'): "10-29 메뉴에 있던 'HAZLE DOWN 33% OFF'가 10-30에 사라지고 해당 다운이 정가로 돌아갔다.",
}


def rows(name):
    return list(csv.DictReader(open(OUT / name, encoding='utf-8-sig')))


def esc(x):
    return html.escape(str(x))


def man(v, d=1):
    """원 → '21.9만' (만 원 단위)."""
    t = f'{v / 10000:.{d}f}'
    return (t.rstrip('0').rstrip('.') if '.' in t else t) + '만'


def won(v):
    return f'{int(v):,}원'


def num(x):
    return float(x) if x not in (None, '') else None


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

    # 그레이스유 공식몰 관찰
    gu = [p for p in runs[REF]['products'] if p['in_clothing_scope']]
    sold = sum(p['availability'] == 'sold_out' for p in gu)
    pre = sum('PRE-ORDER' in p['category_raw'] for p in gu)
    cer = sum('CEREMONY' in p['category_raw'] for p in gu)
    mats = json.loads((Path(__file__).resolve().parent / 'materials.json').read_text(encoding='utf-8'))[REF]
    text_ok = lambda r: r['status'] == 'observed' and (r.get('source') or '').startswith('detail_text')  # noqa: E731
    recs = sorted(mats.values(), key=lambda r: int(r['product_id']))
    newest = recs[-30:]
    older = recs[:-30]

    # 날짜별 변화
    changes = rows('changes.csv')
    days = sorted(runs_by_date(REF))
    cdate, pdate = days[-1], (days[-2] if len(days) > 1 else None)
    first = min(min(runs_by_date(b)) for b in ORDER)
    under = sum(1 for p in gu if p['sale_price'] and p['sale_price'] < 100000)
    return dict(name=name, by=by, runs=runs, policy=policy, hearts=hearts, gu_pages=len(gu), gu_sold=sold, gu_pre=pre, gu_cer=cer,
                mat_newest=len(newest), mat_newest_img=sum(not text_ok(r) for r in newest), mat_older=len(older), mat_older_text=sum(text_ok(r) for r in older),
                changes=changes, date=cdate, prev=pdate, first=first, gu_under=under, events=rows('events.csv'))


def promo_type(share, med):
    if not share:
        return '정가 유지', 'flat'
    if share >= 85:
        return ('상시 소폭 할인', 'soft') if med <= 20 else ('상시 큰 폭 할인', 'deep')
    return '일부 할인(아울렛·행사)', 'part'


def page(f, standalone):
    name, by = f['name'], f['by']
    tot = {b: by[b]['전체'] for b in ORDER}
    sale = {b: num(tot[b]['sale_median']) for b in ORDER}
    reg = {b: num(tot[b]['regular_median']) or sale[b] for b in ORDER}
    share = {b: num(tot[b]['discount_share_pct']) or 0 for b in ORDER}
    dmed = {b: num(tot[b]['discount_median_pct']) or 0 for b in ORDER}
    models = sum(int(tot[b]['n']) for b in ORDER)
    no_disc = [name[b] for b in ORDER if not share[b]]
    pol = {b: f['policy'].get(POLICY_KEY.get(b, b), {}) for b in ORDER}
    free = {b: pol[b].get('free_min') for b in ORDER}
    others_free = sorted({v for b, v in free.items() if b != REF and v is not None})
    h_gu = f['hearts'][WC_CD[REF]]
    rank_rows = sorted(((f['hearts'][WC_CD[b]][1], b) for b in ORDER if b in WC_CD))

    # ---------- 1. 한눈에 ----------
    keys = [
        (f'{len(no_disc)}곳', '할인 없이 파는 브랜드',
         f'{"·".join(no_disc)}만 정가 그대로 판다. 나머지 {len(ORDER) - len(no_disc)}곳은 의류의 {min(v for v in share.values() if v):.0f}~{max(share.values()):.0f}%에 할인이 붙어 있다. 정가로는 비슷해도 고객이 보는 가격은 꽤 다르다.'),
        (man(free[REF], 0) + ' 원', '그레이스유 무료배송 기준',
         f'비교한 곳 중 가장 높다. 라메레이·보연은 금액과 상관없이 무료, 낫띵리튼·제이제이지고트는 {man(50000, 0)} 원 이상 무료. 다만 그레이스유 의류는 판매가 중앙이 {man(sale[REF])} 원이고 10만 원 미만은 {f["gu_under"] / f["gu_pages"] * 100:.0f}%뿐이라, 한 벌만 사도 대부분 기준을 넘는다.'),
        (f'{h_gu[1]}위', 'W컨셉 여성 브랜드 찜 순위',
         f'5,871개 브랜드 중 상위 {h_gu[1] / 5871 * 100:.0f}%대(찜 {h_gu[0]:,}). 비교군에서는 ' + ', '.join(f'{name[b]} {r:,}위' for r, b in rank_rows if b != REF) + '. 오르는 W컨셉에 입점하지 않았다.'),
    ]
    key_html = ''.join(f'<div class="key"><div class="kv">{esc(v)}</div><div class="kl">{esc(l)}</div><p>{esc(t)}</p></div>' for v, l, t in keys)

    # ---------- 2. 비교 브랜드 ----------
    brand_rows = ''.join(
        f'<tr class="{"ref" if b == REF else ""}"><th scope="row">{esc(name[b])}</th><td><span class="tag t-{ {"기준": "ref", "확정": "fix", "추천": "rec"}[ROLE[b][0]] }">{ROLE[b][0]}</span></td>'
        f'<td>{esc(ROLE[b][1])}</td><td class="n">{int(tot[b]["n"]):,}</td><td class="site">{esc(ROLE[b][2])}</td></tr>' for b in ORDER)

    # ---------- 3. 가격: 정가 중앙 → 판매가 중앙 ----------
    lo, hi = 50000, 250000
    pos = lambda v: (min(max(v, lo), hi) - lo) / (hi - lo) * 100  # noqa: E731
    ticks = ''.join(f'<span class="tick" style="left:{pos(v):.2f}%"><i>{man(v, 0)}</i></span>' for v in range(lo, hi + 1, 50000))
    order = [REF] + sorted([b for b in ORDER if b != REF], key=lambda b: -sale[b])
    db = ''
    for b in order:
        a, s = pos(sale[b]), pos(reg[b])
        gap = f'<span class="bar" style="left:{a:.2f}%;width:{s - a:.2f}%"></span>' if reg[b] > sale[b] else ''
        ring = f'<span class="dot reg" style="left:{s:.2f}%" title="정가 중앙 {won(reg[b])}"></span>' if reg[b] > sale[b] else ''
        val = f'{man(reg[b])} → <b>{man(sale[b])}</b>' if reg[b] > sale[b] else f'<b>{man(sale[b])}</b> 정가 그대로'
        db += (f'<div class="db{" ref" if b == REF else ""}"><span class="dn">{esc(name[b])}</span><span class="track">{ticks if b == order[0] else ""}{gap}{ring}'
               f'<span class="dot sale" style="left:{a:.2f}%" title="판매가 중앙 {won(sale[b])}"></span></span><span class="dv">{val}</span></div>')

    cat_head = ''.join(f'<th scope="col" class="n">{esc(c)}</th>' for c in CATS)
    cat_body = ''
    for b in ORDER:
        cells = ''
        for c in CATS:
            r = by[b].get(c)
            n = int(r['n']) if r and r['n'] else 0
            if not n:
                cells += '<td class="n dim">없음</td>'
                continue
            v = num(r['sale_median'])
            small = n < 5
            cells += f'<td class="n{" dim" if small else ""}">{man(v)}<small>{n}개{" · 적음" if small else ""}</small></td>'
        cat_body += f'<tr class="{"ref" if b == REF else ""}"><th scope="row">{esc(name[b])}</th>{cells}</tr>'

    # ---------- 4. 할인·행사 ----------
    ev = {}
    for e in f['events']:
        b = next(k for k, v in name.items() if v == e['brand'])
        if e['event'] == '프로모션 표시 없이 할인' or not (e['models'] or '쿠폰' in e['event']):
            continue
        ev.setdefault(b, []).append(e['event'] + (f' {e["discount"]}' if e['discount'] and e['discount'] not in e['event'] else ''))
    plain = {next(k for k, v in name.items() if v == e['brand']): e for e in f['events'] if e['event'] == '프로모션 표시 없이 할인'}
    seen_note = {
        'graceu': "10-29 'HAZLE DOWN 33% OFF'(다운 1개 모델) 진행 → 10-30 종료. W컨셉 브랜드관에서는 첫 화면 160개 중 83개가 할인(중앙 13%, 10-29)",
        'orr': '10-29 1차·2차·TIME SALE 컬렉션 진행 → 10-30 종료',
    }
    promo = ''
    for b in sorted(ORDER, key=lambda b: (b != REF, share[b], dmed[b])):
        label, cls = promo_type(share[b], dmed[b])
        evs = list(dict.fromkeys(ev.get(b, [])))
        what = seen_note.get(b) or (' · '.join(evs[:4]) + (f' 외 {len(evs) - 4}개' if len(evs) > 4 else ''))
        if b in plain and b not in seen_note:
            what = (what + ' · ' if what else '') + f'행사 문구 없이 할인 표시 {plain[b]["discount"]}'
        promo += (f'<tr class="{"ref" if b == REF else ""}"><th scope="row">{esc(name[b])}</th><td><span class="tag p-{cls}">{label}</span></td>'
                  f'<td class="n">{share[b]:.0f}%</td><td class="n">{(f"{dmed[b]:.0f}%" if share[b] else "-")}</td><td class="what">{esc(what)}</td></tr>')

    # ---------- 5. 배송·반품 ----------
    def fee(b):
        p = pol[b]
        if p.get('free_min') == 0:
            return '무료', '금액 상관없이 무료'
        f_ = won(p['fee']) if p.get('fee') else '확인 안 됨'
        m = f'{man(p["free_min"], 0)} 원 이상 무료' if p.get('free_min') else '확인 안 됨'
        return f_, m
    ship = ''
    for b in ORDER:
        f_, m = fee(b)
        ret = pol[b].get('ret', '')
        ret = ret.split(' · ')[0] + (' · ' + ret.split(' · ')[1] if len(ret.split(' · ')) > 1 else '')
        ship += (f'<tr class="{"ref" if b == REF else ""}"><th scope="row">{esc(name[b])}</th><td class="n{" dim" if "확인" in f_ else ""}">{esc(f_)}</td>'
                 f'<td class="{"dim" if "확인" in m else ""}">{esc(m)}</td><td class="what">{esc(ret)}</td></tr>')

    # ---------- 6. 우리 공식몰 관찰 ----------
    obs = [
        ('품절 표시가 목록의 ' + f'{f["gu_sold"] / f["gu_pages"] * 100:.0f}%',
         f'여성 의류 상품 페이지 {f["gu_pages"]}개 중 {f["gu_sold"]}개에 품절 표시가 붙은 채 목록에 남아 있다.',
         '고객이 목록을 넘길 때 살 수 없는 상품을 자주 만나면 "살 게 없다"는 인상을 줄 수 있다. 잘 팔려서 품절된 것인지, 시즌이 끝난 상품인지는 화면만으로는 알 수 없다.',
         '재입고 예정과 단종을 나눠 표시하고, 재입고 예정 상품에는 알림 신청을 받는다. 단종 상품은 목록 뒤로 보낸다.',
         '품절 상품별 재생산 계획, 재입고 알림을 받았을 때의 수요'),
        (f'최근 상품일수록 소재가 이미지 안에만',
         f'가장 최근에 등록된 {f["mat_newest"]}개 모델 중 {f["mat_newest_img"]}개는 혼용률이 글자로 없고 상세 이미지 안에만 있다. 그 이전 상품은 {f["mat_older"]}개 중 {f["mat_older_text"]}개가 글자로 적혀 있다.',
         '21만 원대 옷에서 소재는 가격의 이유가 된다. 글자로 없으면 검색·필터·플랫폼 상품정보에 잘 잡히지 않고, 고객은 이미지 끝까지 내려야 찾는다.',
         '상세 상단에 혼용률·실측·세탁 방법을 글자로 3줄 요약한다. 이미지는 그대로 둔다.',
         '소재·사이즈 관련 문의 비율, 반품 사유 중 소재·사이즈 비중'),
        ('비교군에 없는 행사복·예약 운영',
         f'의류 중 CEREMONY 메뉴 상품이 {f["gu_cer"]}개, PRE-ORDER(예약 주문) 상품이 {f["gu_pre"]}개 있다. 공식몰 메타 키워드에도 셀프웨딩·하객룩이 있다. 비교한 6곳은 일상복 중심이다.',
         '이 수요가 매출의 큰 축이라면 일상복 브랜드만으로는 비교 기준이 부족하다. 예약 주문은 재고 부담을 줄이는 운영일 수 있다.',
         '행사복 매출 비중을 먼저 확인하고, 크면 웨딩·하객복 브랜드를 비교군에 한 겹 더한다.',
         'CEREMONY·예약 상품의 매출 비중과 시즌(봄·가을 웨딩)'),
    ]
    obs_html = ''.join(
        f'<article class="obs"><h3>{esc(t)}</h3><dl><dt>본 것</dt><dd>{esc(fact)}</dd><dt>왜 볼 만한가</dt><dd>{esc(why)}</dd>'
        f'<dt>해 볼 수 있는 것</dt><dd>{esc(do)}</dd><dt>회사에서 확인할 것</dt><dd>{esc(chk)}</dd></dl></article>' for t, fact, why, do, chk in obs)

    # ---------- 7. 매일 쌓이는 것 ----------
    cnt = {}
    for c in f['changes']:
        b = next(k for k, v in name.items() if v == c['brand'])
        kind = re.sub(r'\(.*', '', c['change']).strip()
        cnt.setdefault(b, {}).setdefault(kind, set()).add(c['product_id'])
    drops = []
    for c in f['changes']:
        if c['change'] == '판매가 변화' and c['before'] and c['after']:
            bf, af = float(c['before']), float(c['after'])
            drops.append(((af - bf) / bf, c))
    drops.sort(key=lambda x: x[0])
    ex = [c for _, c in drops if c['brand'] == '제이제이지고트'][:1] + [c for _, c in sorted(drops, key=lambda x: -x[0]) if c['brand'] == '그레이스유'][:1]
    chg = ''
    for b in ORDER:
        if b not in cnt:
            continue
        kinds = {k: v for k, v in cnt[b].items() if not (k == '표시 할인율 변화' and v <= cnt[b].get('판매가 변화', set()))}  # 같은 상품의 가격·할인율 변화는 한 번만
        parts = ' · '.join(f'{k} {len(v)}개' for k, v in sorted(kinds.items(), key=lambda kv: -len(kv[1])))
        note = CHANGE_NOTES.get((b, f['date']))
        chg += f'<li><b>{esc(name[b])}</b> {esc(parts)}' + (f'<span class="note">{esc(note)}</span>' if note else '') + '</li>'
    quiet = [name[b] for b in ORDER if b not in cnt and len(runs_by_date(b)) > 1]
    first = [name[b] for b in ORDER if len(runs_by_date(b)) < 2]
    chg += (f'<li class="quiet">{esc("·".join(quiet))}: 바뀐 것 없음</li>' if quiet else '') + (f'<li class="quiet">{esc("·".join(first))}: 10-30 첫 수집이라 비교는 다음 날부터</li>' if first else '')
    ex_html = ''.join(f'<li>{esc(c["brand"])} · {esc(c["name"])} <span class="n">{won(float(c["before"]))} → {won(float(c["after"]))}</span></li>' for c in ex)

    dates = [f['first'], f['date']]
    regs = [reg[b] for b in ORDER]
    css = CSS
    body = f'''<title>그레이스유 비교 노트</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@400;700&family=IBM+Plex+Sans+KR:wght@400;500;600&display=swap">
<style>{css}</style>
<main class="wrap">
<header class="mast">
  <p class="eyebrow">MD 참고 자료 · 공개 화면 기준</p>
  <h1>그레이스유와 비교 브랜드 6곳</h1>
  <p class="lede">그레이스유 공식몰과 비교 브랜드 6곳의 공식몰에서 여성 의류 {models:,}개 모델을 같은 기준으로 읽었다. 가격·할인·행사·배송 조건을 한 장에 놓고, 매일 바뀌는 것을 계속 쌓는다.</p>
  <p class="stamp">수집 {esc(dates[0])}{(" ~ " + esc(dates[-1])) if dates[0] != dates[-1] else ""} · 매일 20:00 자동 갱신 중 · 라메레이·보연은 10-30부터</p>
</header>

<section class="sec"><h2>한눈에</h2><div class="keys">{key_html}</div></section>

<section class="sec"><h2>누구와 비교했나</h2><div>
  <div class="scroll"><table class="t"><thead><tr><th scope="col">브랜드</th><th scope="col">구분</th><th scope="col">비교 이유</th><th scope="col" class="n">의류 모델</th><th scope="col">판매처</th></tr></thead><tbody>{brand_rows}</tbody></table></div>
  <p class="fine">확정 = 비교 기준으로 정한 곳, 추천 = "그레이스유 대신 살 만한가" 기준으로 고른 후보(아직 확정 전). 추천 후보 베스띠벨리는 공식숍이 네이버 브랜드스토어라 자동 수집할 수 없어 뺐다.</p>
</div></section>

<section class="sec"><h2>가격</h2><div>
  <h3 class="sub">의류 전체 · 정가 중앙과 판매가 중앙</h3>
  <div class="legend"><span><i class="dot reg"></i>정가 중앙</span><span><i class="dot sale"></i>판매가 중앙(누구나 보는 가격)</span></div>
  <div class="dbs">{db}</div>
  <p class="fine">정가 중앙은 {man(min(regs), 0)}~{man(max(regs), 0)} 원 안에 모여 있다. 차이는 할인에서 난다. 판매가는 로그인·쿠폰 없이 화면에 보이는 가격이며 쿠폰가는 넣지 않았다.</p>
  <h3 class="sub">카테고리별 판매가 중앙</h3>
  <div class="scroll"><table class="t cats"><thead><tr><th scope="col">브랜드</th>{cat_head}</tr></thead><tbody>{cat_body}</tbody></table></div>
  <p class="fine">작은 숫자는 모델 수. 색상만 다른 상품은 한 모델로 센다. 5개 미만은 흐리게 표시했다(비교하기엔 표본이 적다).</p>
</div></section>

<section class="sec"><h2>할인·행사 운영</h2><div>
  <div class="scroll"><table class="t"><thead><tr><th scope="col">브랜드</th><th scope="col">운영 방식</th><th scope="col" class="n">할인 표시 비율</th><th scope="col" class="n">할인 폭(중앙)</th><th scope="col">이번에 본 행사</th></tr></thead><tbody>{promo}</tbody></table></div>
  <p class="fine">운영 방식은 공개 화면 숫자로 나눈 것이다(할인 표시 0% = 정가 유지, 85% 이상이면 상시, 할인 폭 20% 이하면 소폭). 행사 문구는 모두 가격 할인형이었다. 적립·사은품 같은 혜택은 아직 수집하지 않아 "없음"이 아니라 "확인 전"이다.</p>
</div></section>

<section class="sec"><h2>배송·반품</h2><div>
  <div class="scroll"><table class="t"><thead><tr><th scope="col">브랜드</th><th scope="col" class="n">배송비</th><th scope="col">무료배송</th><th scope="col">단순 변심 교환·반품</th></tr></thead><tbody>{ship}</tbody></table></div>
  <p class="fine">각 공식몰 상품 상세·이용 안내에 공개된 문구를 줄여 적었다(10-29~30 확인). 화면에서 찾지 못한 값은 "확인 안 됨"으로 둔다.</p>
</div></section>

<section class="sec"><h2>우리 공식몰에서 보인 것</h2><div class="obss">{obs_html}</div></section>

<section class="sec"><h2>매일 쌓이는 것</h2><div>
  <h3 class="sub">바뀐 것 ({esc(f["prev"] or "-")} → {esc(f["date"])}, 상품 페이지 수)</h3>
  <ul class="chg">{chg}</ul>
  <ul class="ex">{ex_html}</ul>
  <p class="fine">목록에서 사라진 상품은 삭제나 판매 종료로 단정하지 않는다. 2~3주 쌓이면 할인이 시작·종료되는 주기, 신상 등록 리듬, BEST 진입·이탈, 품절 → 재입고를 브랜드별로 볼 수 있다.</p>
</div></section>

<footer class="foot">
  <h2>이 자료의 범위</h2>
  <ul>
    <li>각 브랜드 공식몰의 공개 화면만 읽었다. 판매량·재고·매출은 알 수 없고 추정하지 않았다.</li>
    <li>소재는 상품 페이지에 글자로 적힌 것만 썼고, 사진으로 짐작하지 않았다.</li>
    <li>숫자는 수집 시점의 화면 기준이며 사이트 사정에 따라 바뀐다. 원자료와 계산 방법은 함께 보관하고 있다.</li>
  </ul>
</footer>
</main>'''
    if standalone:
        return f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">{body.split("<main", 1)[0]}</head><body><main{body.split("<main", 1)[1]}</body></html>'
    return body


CSS = r'''
/* 레이아웃: 왼쪽 좁은 칸에 절 제목, 오른쪽에 내용. 메모처럼 위에서 아래로 읽는다 */
:root{--bg:#F6F6F4;--paper:#FFFFFF;--ink:#1C1F2B;--muted:#5E6271;--line:#E2E1DD;--accent:#7A2C4A;--accent-soft:#F4E7EC;--reg:#A4A8B4;--fix:#2F4A6B;--fix-soft:#E6ECF3;
--warn:#8A5A12;--warn-soft:#F6EEDD;
--display:"Gowun Batang","Noto Serif KR","Apple SD Gothic Neo",serif;--body:"IBM Plex Sans KR","Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#14151B;--paper:#1C1E26;--ink:#ECEBE7;--muted:#A3A6B3;--line:#2E313C;--accent:#E092B0;--accent-soft:#3A2330;--reg:#6C7182;--fix:#9DB7D8;--fix-soft:#243041;--warn:#E3B66A;--warn-soft:#3A2E1A;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#14151B;--paper:#1C1E26;--ink:#ECEBE7;--muted:#A3A6B3;--line:#2E313C;--accent:#E092B0;--accent-soft:#3A2330;--reg:#6C7182;--fix:#9DB7D8;--fix-soft:#243041;--warn:#E3B66A;--warn-soft:#3A2E1A;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:400 15px/1.65 var(--body);-webkit-font-smoothing:antialiased;word-break:keep-all;overflow-wrap:anywhere}
.wrap{max-width:1080px;margin:0 auto;padding-block:48px 64px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));display:grid;gap:44px}
.mast{display:grid;gap:10px;max-width:760px}
.eyebrow{margin:0;font-size:12px;letter-spacing:.12em;color:var(--accent);font-weight:600}
h1{margin:0;font:700 clamp(30px,4.6vw,44px)/1.2 var(--display);letter-spacing:-.01em;text-wrap:balance}
.lede{margin:0;font-size:16px;color:var(--muted);max-width:64ch}
.stamp{margin:4px 0 0;font-size:13px;color:var(--muted);font-variant-numeric:tabular-nums}
.sec{display:grid;grid-template-columns:168px minmax(0,1fr);gap:28px;padding-top:28px;border-top:1px solid var(--line)}
.sec>div{min-width:0;display:grid;gap:14px;align-content:start}
h2{margin:0;font:700 19px/1.35 var(--display);text-wrap:balance}
h3{margin:0;font-weight:600}
.sub{font-size:14px;color:var(--muted);font-weight:600;margin-top:6px}
.keys{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}
.key{display:grid;gap:4px;align-content:start}
.kv{font:700 34px/1.1 var(--display);color:var(--accent);font-variant-numeric:tabular-nums}
.kl{font-size:13px;font-weight:600}
.key p{margin:4px 0 0;font-size:14px;color:var(--muted)}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.t{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums;background:var(--paper)}
.t th,.t td{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.t thead th{font-size:12px;font-weight:600;color:var(--muted);background:var(--bg);border-bottom:1px solid var(--ink);white-space:nowrap}
.t tbody th{font-weight:600;white-space:nowrap}
.t .n{text-align:right;white-space:nowrap}
.t tr.ref th,.t tr.ref td{background:var(--accent-soft)}
.t tr.ref th{color:var(--accent)}
.t .site{color:var(--muted);font-size:13px;white-space:nowrap}
.t .what{color:var(--muted);font-size:13px;min-width:16em}
.t .dim{color:var(--muted);opacity:.7}
.cats td small{display:block;font-size:11px;color:var(--muted)}
.tag{display:inline-block;font-size:12px;font-weight:600;padding:1px 8px;border-radius:999px;white-space:nowrap}
.t-ref{background:var(--accent);color:var(--paper)}
.t-fix{background:var(--fix-soft);color:var(--fix)}
.t-rec{background:var(--warn-soft);color:var(--warn)}
.p-flat{background:var(--accent-soft);color:var(--accent)}
.p-soft{background:var(--fix-soft);color:var(--fix)}
.p-part{background:var(--bg);color:var(--ink);border:1px solid var(--line)}
.p-deep{background:var(--warn-soft);color:var(--warn)}
.fine{margin:0;font-size:13px;color:var(--muted);max-width:72ch}
.legend{display:flex;gap:18px;flex-wrap:wrap;font-size:13px;color:var(--muted)}
.legend span{display:inline-flex;align-items:center;gap:6px}
.legend .dot{position:static;transform:none}
.dbs{display:grid;gap:2px;background:var(--paper);padding:30px 14px 12px;border:1px solid var(--line)}
.db{display:grid;grid-template-columns:7.5em minmax(0,1fr) 10.5em;align-items:center;gap:14px;min-height:34px}
.db.ref .dn{color:var(--accent);font-weight:700}
.dn{font-size:14px;font-weight:600;white-space:nowrap}
.dv{font-size:13px;color:var(--muted);text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.dv b{color:var(--ink);font-weight:600}
.db.ref .dv b{color:var(--accent)}
.track{position:relative;height:34px;background:linear-gradient(var(--line),var(--line)) center/100% 1px no-repeat}
.tick{position:absolute;top:-22px;bottom:-400px;width:0;border-left:1px dashed var(--line);pointer-events:none}
.tick i{position:absolute;top:0;left:0;transform:translateX(-50%);font-style:normal;font-size:11px;color:var(--muted);white-space:nowrap;background:var(--paper);padding:0 3px}
.dbs{overflow:hidden}
.bar{position:absolute;top:50%;height:4px;margin-top:-2px;background:var(--reg);opacity:.55;border-radius:2px}
.dot{position:absolute;top:50%;width:13px;height:13px;border-radius:50%;transform:translate(-50%,-50%);display:inline-block}
.dot.sale{background:var(--ink)}
.db.ref .dot.sale{background:var(--accent)}
.dot.reg{background:var(--paper);border:2px solid var(--reg)}
.legend .dot.sale{background:var(--ink)}
.obss{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}
.obs{background:var(--paper);border:1px solid var(--line);border-top:3px solid var(--accent);padding:18px 18px 16px;display:grid;gap:12px;align-content:start;min-width:0}
.obs h3{font:700 17px/1.4 var(--display);text-wrap:balance}
.obs dl{margin:0;display:grid;gap:4px}
.obs dt{font-size:11px;letter-spacing:.06em;color:var(--accent);font-weight:600;margin-top:8px}
.obs dt:first-child{margin-top:0}
.obs dd{margin:0;font-size:14px}
.chg,.ex{margin:0;padding:0;list-style:none;display:grid;gap:8px}
.chg li{padding:10px 14px;background:var(--paper);border:1px solid var(--line);font-size:14px}
.chg li b{margin-right:8px}
.chg .note{display:block;margin-top:4px;font-size:13px;color:var(--muted)}
.chg .quiet{background:transparent;border-style:dashed;color:var(--muted)}
.ex li{font-size:13px;color:var(--muted)}
.ex .n{font-variant-numeric:tabular-nums;color:var(--ink);margin-left:6px;white-space:nowrap}
.foot{display:grid;gap:8px;padding-top:24px;border-top:1px solid var(--ink)}
.foot h2{font-size:15px}
.foot ul{margin:0;padding-left:18px;font-size:13px;color:var(--muted);display:grid;gap:2px}
@media (max-width:860px){.sec{grid-template-columns:1fr;gap:14px}.keys,.obss{grid-template-columns:1fr}}
@media (max-width:520px){.db{grid-template-columns:5.2em minmax(0,1fr);row-gap:0}.dv{grid-column:2;text-align:left;margin-top:-6px}.kv{font-size:30px}.wrap{padding-block:28px 48px}}
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
