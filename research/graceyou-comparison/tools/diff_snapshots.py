"""날짜별 스냅샷 사이의 변화를 보여 준다(신상·삭제·가격·할인·품절 변화, 지표 추이).
  python tools/diff_snapshots.py official kume               # 가장 최근 두 날짜 비교
  python tools/diff_snapshots.py official kume 2026-10-29 2026-11-02
  python tools/diff_snapshots.py 29cm 1939 --series          # 날짜별 지표 표(5일치 추이 등)
  python tools/diff_snapshots.py official --all --series     # 공식몰 4곳 지표 표
종류: official = snapshots/official/<브랜드>/<날짜>.json , 29cm = snapshots/29cm/<브랜드ID>/<날짜>.json
"""
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "snapshots"


def load(kind, key, day):
    d = json.loads((ROOT / kind / key / f"{day}.json").read_text(encoding="utf-8"))
    items = {}
    if kind == "official":
        for p in d["products"]:
            items[p["id"]] = {"name": p["name"], "list": p["list"], "sale": p["sale"], "soldout": p["soldout"], "pos": p.get("pos")}
    else:
        for c in d.get("cards", []):
            lst = round(c["p"] / (1 - c["d"] / 100)) if c.get("d") else c["p"]
            items[c["n"]] = {"name": c["n"], "list": lst, "sale": c["p"], "soldout": "품절" in c.get("t", []), "pos": None, "lk": c.get("lk"), "rv": c.get("rv")}
    return d, items


def days(kind, key):
    return sorted(p.stem for p in (ROOT / kind / key).glob("*.json"))


def metrics(items):
    v = list(items.values())
    if not v:
        return {}
    lst, sale = [x["list"] for x in v], [x["sale"] for x in v]
    return {"n": len(v), "정가중앙": round(statistics.median(lst)), "판매가중앙": round(statistics.median(sale)),
            "할인비율": round(sum(1 for x in v if x["sale"] < x["list"]) / len(v), 2), "품절": sum(1 for x in v if x["soldout"])}


def diff(kind, key, a, b):
    _, A = load(kind, key, a)
    _, B = load(kind, key, b)
    new = [B[k] for k in B if k not in A]
    gone = [A[k] for k in A if k not in B]
    price, sold = [], []
    for k in A.keys() & B.keys():
        x, y = A[k], B[k]
        if x["list"] != y["list"] or x["sale"] != y["sale"]:
            price.append((y["name"], x["list"], x["sale"], y["list"], y["sale"]))
        if x["soldout"] != y["soldout"]:
            sold.append((y["name"], "품절됨" if y["soldout"] else "재입고"))
    print(f"## {kind}/{key}  {a} → {b}")
    ma, mb = metrics(A), metrics(B)
    for k in ma:
        print(f"- {k}: {ma[k]} → {mb.get(k)}")
    print(f"- 신상 {len(new)} · 삭제 {len(gone)} · 가격 변경 {len(price)} · 품절 변동 {len(sold)}")
    for t, items in (("신상", [(x["name"], x["list"], x["sale"]) for x in new]), ("삭제", [(x["name"], x["list"], x["sale"]) for x in gone])):
        for n, l, s in items[:15]:
            print(f"  [{t}] {n} {l:,}→{s:,}")
    for n, l0, s0, l1, s1 in price[:25]:
        print(f"  [가격] {n}: 정가 {l0:,}→{l1:,} / 판매가 {s0:,}→{s1:,}")
    for n, w in sold[:15]:
        print(f"  [{w}] {n}")


def series(kind, key):
    ds = days(kind, key)
    print(f"## {kind}/{key} 지표 추이")
    print("| 날짜 | 상품수 | 정가중앙 | 판매가중앙 | 할인비율 | 품절 |")
    print("|---|---|---|---|---|---|")
    for d in ds:
        m = metrics(load(kind, key, d)[1])
        print(f"| {d} | {m.get('n')} | {m.get('정가중앙'):,} | {m.get('판매가중앙'):,} | {m.get('할인비율')} | {m.get('품절')} |")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    kind = a[0]
    keys = [p.name for p in sorted((ROOT / kind).iterdir())] if "--all" in sys.argv else [a[1]]
    for key in keys:
        ds = days(kind, key)
        if "--series" in sys.argv:
            series(kind, key)
        elif len(ds) >= 2:
            x, y = (a[2], a[3]) if len(a) >= 4 else (ds[-2], ds[-1])
            diff(kind, key, x, y)
        else:
            print(f"{kind}/{key}: 스냅샷 {len(ds)}개뿐이라 비교할 수 없다 ({', '.join(ds)})")
