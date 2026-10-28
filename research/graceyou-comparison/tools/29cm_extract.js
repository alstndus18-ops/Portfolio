async () => {
  // 29CM 브랜드 페이지(https://www.29cm.co.kr/store/brand/<id>)에 보이는 글을 읽어 브랜드 정보와 첫 화면 상품 카드를 돌려준다.
  // 화면에 표시된 내용(소개문·가격·할인율·좋아요·평점·배지)만 읽는다. 내부 API는 부르지 않는다.
  await new Promise(r => setTimeout(r, 2600));
  for (let i = 0; i < 6; i++) { window.scrollBy(0, 1400); await new Promise(r => setTimeout(r, 550)); }
  window.scrollTo(0, 0);
  const L = document.body.innerText.split("\n").map(s => s.trim()).filter(Boolean);
  const BADGE = new Set(["가을 필수","겨울 필수","봄 필수","여름 필수","신상품","품절","단독","BEST","쿠폰","조건부 무료배송","무료배송","실시간","일간","주간","월간","더보기","LOOKBOOK","NEW","예약주문","SALE","한정수량","재입고","마감임박"]);
  const isPrice = s => /^[0-9]{1,3}(,[0-9]{3})+$/.test(s);
  const num = s => { const m = String(s).match(/^([0-9.]+)\s*(k|K|천|만)?$/); if (!m) return null; const v = parseFloat(m[1]); return Math.round(/k|K|천/.test(m[2] || "") ? v * 1000 : m[2] === "만" ? v * 10000 : v); };
  const out = { url: location.href.split("?")[0], title: document.title.replace(/ - 모든 취향 곁에, 29CM/, "") };
  try { const nd = JSON.parse(document.getElementById("__NEXT_DATA__").textContent); const b = nd.props.pageProps.dehydratedState.queries[0].state.data; out.ko = b.nameKor; out.en = b.nameEng; out.sub = b.subCopy; out.est = b.establishedYear; out.heart = b.heartCount; out.intro = b.description; } catch (e) { out.err = "nodata"; }
  out.promo = L.slice(0, 45).filter(x => /혜택|쿠폰|적립|최대/.test(x) && x.length < 40).slice(0, 4);
  const cards = [];
  for (let i = 0; i < L.length; i++) {
    if (!isPrice(L[i])) continue;
    let j = i - 1, pct = null; while (j >= 0 && (BADGE.has(L[j]) || /^[0-9]+%$/.test(L[j]) || isPrice(L[j]))) { if (/^[0-9]+%$/.test(L[j])) pct = parseInt(L[j]); j--; }
    const rest = []; for (let k = i + 1; k < Math.min(L.length, i + 9) && !isPrice(L[k]); k++) { if (/^[0-9]+%$/.test(L[k])) break; rest.push(L[k]); if (/^[0-9.]+ \([0-9,]+\)$/.test(L[k])) break; }
    const rt = rest.find(x => /^[0-9.]+ \([0-9,]+\)$/.test(x));
    const tags = []; for (let k = i + 1; k < Math.min(L.length, i + 14); k++) { if (isPrice(L[k]) || /^[0-9]+%$/.test(L[k])) break; if (BADGE.has(L[k])) tags.push(L[k]); }
    cards.push({ n: L[j], p: parseInt(L[i].replace(/,/g, "")), d: pct, lk: rest.length ? num(rest[0]) : null, rt: rt ? parseFloat(rt) : null, rv: rt ? parseInt(rt.match(/\(([0-9,]+)\)/)[1].replace(/,/g, "")) : 0, t: tags });
  }
  const seen = new Set(), u = cards.filter(c => { const k = c.n + "|" + c.p; if (seen.has(k)) return false; seen.add(k); return true; });
  const q = (a, f) => a.length ? a[Math.min(a.length - 1, Math.floor(a.length * f))] : null;
  const ps = u.map(c => c.p).sort((a, b) => a - b);
  out.n = u.length; out.p = { min: ps[0], q1: q(ps, .25), med: q(ps, .5), q3: q(ps, .75), p90: q(ps, .9), max: ps[ps.length - 1], mean: ps.length ? Math.round(ps.reduce((a, b) => a + b, 0) / ps.length) : null };
  const ds = u.filter(c => c.d).map(c => c.d).sort((a, b) => a - b);
  out.disc = { n: ds.length, med: q(ds, .5), max: ds[ds.length - 1] };
  const lk = u.map(c => c.lk).filter(x => x != null).sort((a, b) => a - b); out.likes = { med: q(lk, .5), max: lk[lk.length - 1] };
  const rv = u.map(c => c.rv).sort((a, b) => a - b); out.rev = { total: rv.reduce((a, b) => a + b, 0), med: q(rv, .5), max: rv[rv.length - 1], rated: u.filter(c => c.rv > 0).length };
  const rated = u.filter(c => c.rt && c.rv); out.rate = rated.length ? +(rated.reduce((a, c) => a + c.rt * c.rv, 0) / rated.reduce((a, c) => a + c.rv, 0)).toFixed(2) : null;
  const tg = {}; u.forEach(c => c.t.forEach(t => tg[t] = (tg[t] || 0) + 1)); out.tags = tg;
  out.names = u.slice(0, 40).map(c => c.n);
  out.cards = u; // 매일 비교용: 상품 카드 전체(이름·가격·할인율·좋아요·평점·리뷰수·배지)
  return out;
}
