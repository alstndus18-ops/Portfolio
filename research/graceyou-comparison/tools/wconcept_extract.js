async () => {
  // W컨셉 브랜드관(https://display.wconcept.co.kr/rn/brand/<id>)에 보이는 글을 읽어 브랜드 소개와 첫 화면 상품 카드를 돌려준다.
  // 화면에 표시된 내용만 읽는다. 가격은 W컨셉 화면 판매가(화면 할인율 반영).
  await new Promise(r => setTimeout(r, 2500));
  for (let i = 0; i < 6; i++) { window.scrollBy(0, 1400); await new Promise(r => setTimeout(r, 600)); }
  window.scrollTo(0, 0);
  const L = document.body.innerText.split("\n").map(s => s.trim()).filter(Boolean);
  const isPrice = s => /^[0-9]{1,3}(,[0-9]{3})+$/.test(s);
  const out = { url: location.href.split("?")[0], title: document.title };
  // 제목은 "한글명(영문명) | W컨셉(W CONCEPT)" 형태. 메뉴의 '브랜드관' 글자와 헷갈리지 않게 제목의 한글명이 나오는 줄을 찾는다.
  const tm = document.title.match(/^(.+?)\((.+?)\)\s*\|/);
  if (tm) { out.ko = tm[1].trim(); out.en = tm[2].trim(); }
  const bi = tm ? L.findIndex((x, i) => x === out.ko && i > 5) : -1;
  if (bi >= 0) {
    const mi = L.indexOf("더보기", bi);
    out.intro = L.slice(bi + 2, mi > bi ? mi : bi + 6).join(" ").slice(0, 600);
  }
  const cards = [];
  for (let i = 0; i < L.length; i++) {
    if (!isPrice(L[i])) continue;
    let j = i - 1, pct = null;
    while (j >= 0 && (/^[0-9]+%$/.test(L[j]) || /^[0-9]{1,2}$/.test(L[j]))) { if (/%$/.test(L[j])) pct = parseInt(L[j]); j--; }
    if (j < 0) continue;
    cards.push({ n: L[j], p: parseInt(L[i].replace(/,/g, "")), d: pct });
  }
  const seen = new Set(), u = cards.filter(c => { const k = c.n + "|" + c.p; if (seen.has(k)) return false; seen.add(k); return true; });
  const q = (a, f) => a.length ? a[Math.min(a.length - 1, Math.floor(a.length * f))] : null;
  const ps = u.map(c => c.p).sort((a, b) => a - b);
  out.n = u.length;
  out.p = { min: ps[0], q1: q(ps, .25), med: q(ps, .5), q3: q(ps, .75), p90: q(ps, .9), max: ps[ps.length - 1], mean: ps.length ? Math.round(ps.reduce((a, b) => a + b, 0) / ps.length) : null };
  const ds = u.filter(c => c.d).map(c => c.d).sort((a, b) => a - b);
  out.disc = { n: ds.length, med: q(ds, .5), max: ds[ds.length - 1] };
  out.names = u.slice(0, 40).map(c => c.n);
  out.cards = u;
  return out;
}
