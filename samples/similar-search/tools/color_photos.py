"""상세 이미지에 인쇄된 색 이름을 OCR로 읽어 색상별 사진과 색상 모음 사진을 찾고 data.js에 넣는다.
analyze.py 다음에 돌린다. 옷을 오려 색을 재지 않고 글자로만 판단한다.

- 올리는 사람마다 글자 위치가 달라 위치를 미리 정하지 않는다. 줄인 이미지에서 글자 상자 위치만 찾고,
  짧은 상자만 읽어 색 이름을 찾는다(사진 위에 쓴 글자 포함). 옵션 색을 다 찾으면 그 상품은 멈춘다.
- 몰별 규칙(data/color-photo-rules.json)은 예외만: 끄기, 사진 밖 이름표의 사진 방향, 머리글 정규식.
- 글자 위치·읽은 글자는 cache/ocr.json에 쌓아 두므로 규칙만 바꿔 다시 돌리면 몇 초면 된다.

  python tools/color_photos.py              전체(data.js 갱신)
  python tools/color_photos.py --sample 5   몰마다 5개만 읽고 결과만 출력
"""
import difflib
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data.js"
RAW = ROOT / "data" / "products_raw.json"
RULES = ROOT / "data" / "color-photo-rules.json"
CACHE = ROOT / "cache" / "ocr.json"
SPEC = re.compile(r"사이즈|소재|제조|혼용|세탁|^\s*색상\s")  # 사양표 줄
HEADER = r"^\W*(\w{0,4}\s*)?\d?\s*colo\w*(\s+[vl]\w*)?\W*$|^\W*other\s*colou?rs?\W*$"  # 색상 모음 머리글(OCR 오타 허용)
DET_W = 480  # 글자 위치 찾기는 폭 480px로 줄여서
EN = {
    "black": "블랙", "white": "화이트", "ivory": "아이보리", "cream": "크림", "beige": "베이지", "oatmeal": "오트밀",
    "camel": "카멜", "mocha": "모카", "brown": "브라운", "gray": "그레이", "grey": "그레이", "charcoal": "차콜",
    "melange": "멜란지", "red": "레드", "wine": "와인", "burgundy": "버건디", "pink": "핑크", "coral": "코랄",
    "orange": "오렌지", "yellow": "옐로우", "lemon": "레몬", "mustard": "머스타드", "butter": "버터", "lime": "라임",
    "green": "그린", "khaki": "카키", "olive": "올리브", "mint": "민트", "sky": "스카이", "blue": "블루",
    "denim": "데님", "navy": "네이비", "indigo": "인디고", "purple": "퍼플", "lavender": "라벤더", "violet": "바이올렛",
    "lilac": "라일락", "peach": "피치", "aqua": "아쿠아", "brick": "브릭", "plum": "플럼", "taupe": "토프",
    "light": "라이트", "dark": "다크", "deep": "딥", "skyblue": "스카이블루", "lightgray": "라이트그레이",
    "lightgrey": "라이트그레이", "darkgray": "다크그레이", "darkbrown": "다크브라운", "oat": "오트",
}
KNOWN = set(EN.values()) | {"연두", "소라", "검정", "보라", "곤색", "먹색", "밤색", "살구", "청록", "자주"}


def panels(im, limit=80):
    """세로로 긴 상세 이미지를 컷별 (위, 아래) 좌표로 나눈다. 8줄 이상 거의 한 색인 가로 여백을 경계로 보고,
    여백 없이 길게 붙은 덩어리는 폭의 1.3배 높이로 나눈다. 글자 띠처럼 납작한 조각(폭의 0.3배 미만)은 뺀다."""
    a = np.asarray(im.convert("L"), dtype=np.float32)
    W = a.shape[1]
    busy = np.convolve(a.std(1) >= 4, np.ones(8), "same") > 0  # 8줄 미만의 여백은 컷 안쪽으로 본다
    edges = np.flatnonzero(np.diff(np.r_[0, busy.astype(int), 0]))
    out = []
    for y0, y1 in zip(edges[::2], edges[1::2]):
        h = y1 - y0
        if h < W * 0.3:  # 색상 모음 사진은 가로로 넓고 낮은 경우가 많다
            continue
        k = max(1, round(h / (W * 1.3))) if h > W * 1.8 else 1
        out += [(int(y0 + h * i // k), int(y0 + h * (i + 1) // k)) for i in range(k)]
    return out[:limit]


def jamo(s):
    out = []
    for ch in s:
        c = ord(ch) - 0xAC00
        out += [chr(0x1100 + c // 588), chr(0x1161 + c % 588 // 28), chr(0x11A7 + c % 28)] if 0 <= c < 11172 else [ch]
    return "".join(out)


def to_korean(text):
    """띠 글자를 한글 낱말 목록으로. 영어 색 이름은 한글로 바꾸고 모르는 영어(워터마크 등)는 버린다."""
    out = []
    for w in re.findall(r"[A-Za-z]+|[가-힣]+", text):
        if w.isascii():
            k = EN.get(w.lower()) or next(iter(difflib.get_close_matches(w.lower(), EN, 1, 0.75)), None)
            if k:
                out.append(k)
        else:
            out.append(w)
    return out


def targets(opts):
    """옵션 색을 찾을 이름 [(이름, pal)], 긴 이름 먼저. 옵션 이름과 색 이름표 이름 둘 다 쓴다."""
    t = {}
    for o in opts:
        if "pal" not in o:
            continue
        m = re.search(r"\[(.+?)\]", o["name"])
        name = re.sub(r"\(.*?\)|\s", "", m.group(1) if m else o["name"])
        for k in (name, o["pal"]):
            if len(k) >= 2:
                t.setdefault(k, o["pal"])
    return sorted(t.items(), key=lambda x: -len(x[0]))


def is_label(text, tg):
    """색 이름표로 볼 만큼 짧은 글자인가. 색 이름 말고 붙은 말이 한글 2자·영어 4자 이하일 때만
    ('차분한 브라운', '복숭아빛 컬러 핑크' 같은 설명 문장은 여러 벌을 함께 찍은 컷에 붙는 일이 많다)."""
    names = sorted(KNOWN | {n for n, _ in tg}, key=len, reverse=True)
    ko = en = 0
    for w in re.findall(r"[A-Za-z]+|[가-힣]+", text):
        if w.isascii():
            if not (EN.get(w.lower()) or difflib.get_close_matches(w.lower(), EN, 1, 0.75)):
                en += len(w)
        else:
            for n in names:
                w = w.replace(n, "")
            ko += len(w)
    return ko <= 2 and en <= 4


def find_colors(words, tg, fuzzy=True):
    s = "".join(words)
    found = []
    for name, pal in tg:
        if name in s:
            s = s.replace(name, "|")
            if pal not in found:
                found.append(pal)
    # OCR 오타(불렉→블랙): 남은 낱말을 자모로 비교해 가장 가까운 이름이 둘째보다 뚜렷하게 가까울 때만
    for w in re.findall(r"[가-힣]{2,}", s) if fuzzy else []:
        if w in KNOWN:
            continue
        sc = sorted(((difflib.SequenceMatcher(None, jamo(w), jamo(n)).ratio(), pal) for n, pal in tg), reverse=True)
        rival = next((r for r, pal in sc if pal != sc[0][1]), 0)
        if sc and sc[0][0] >= 0.66 and sc[0][0] - rival >= 0.1 and sc[0][1] not in found:
            found.append(sc[0][1])
    return found


def near(pans, y0, y1, W, prefer=None):
    """사진 밖 글자 상자에 딸린 컷: 위아래로 폭의 0.3배 안에 있는 컷. 몰 규칙 방향(prefer)이 있으면 그쪽만
    (반대쪽은 사이즈표 같은 다른 컷일 수 있다), 없으면 더 가까운 쪽."""
    up = next(((y0 - q[1], q) for q in reversed(pans) if q[1] <= y1 and y0 - q[1] <= W * 0.3), None)
    down = next(((q[0] - y1, q) for q in pans if q[0] >= y0 and q[0] - y1 <= W * 0.3), None)
    if prefer:
        c = up if prefer == "above" else down
        return c[1] if c else None
    return min([c for c in (up, down) if c], default=(0, None))[1]


def find(paths, rule, tg, boxes, read):
    """(색별 컷 {pal: (경로, 위, 아래)}, 색상 모음 컷, 읽은 글자). 위치를 미리 정하지 않고 이미지의 글자 상자를
    위에서부터 본다. 색 이름이 사진 안에 있으면 그 컷, 밖에 있으면 가장 가까운 컷. 한 컷에 색 이름이 2개 이상
    붙거나 'Color View' 같은 머리글 바로 아래 컷이면 색상 모음 사진."""
    head = re.compile(rule.get("lineup_header") or HEADER)
    n_pal = len({pal for _, pal in tg})
    shots, lineup, seen = {}, None, []
    for path in paths:
        if len(shots) == n_pal:
            break
        im = Image.open(ROOT / path).convert("RGB")
        W = im.width
        pans = panels(im)
        marks = {}  # 컷 -> 붙은 색(pal) 집합, "*" = 색 이름 나열, "H" = 머리글 바로 아래
        for b in boxes(path, im):
            x0, x1, y0, y1 = b
            if x1 - x0 > W * 0.8:  # 설명 문단 줄
                continue
            t = read(path, im, b)
            if not t or SPEC.search(t):
                continue
            if head.search(t.lower()):
                seen.append(f"{path[-14:]}@{y0}:머리글 {t}")
                q = next((q for q in pans if q[0] >= y0 and q[0] - y1 <= W * 0.4), None)
                if q:
                    marks.setdefault(q, set()).add("H")
                continue
            # '#화이트'처럼 해시태그가 있으면 해시태그 낱말만 색으로 본다(설명 문장의 다른 낱말 오인 방지)
            # 비슷한 글자 맞추기(OCR 오타)는 해시태그에서만: 그 밖에서는 깨진 글자를 색으로 잘못 맞추는 일이 많다
            tags = re.findall(r"#\s*([^\s#]+)", t)
            if not tags and not is_label(t, tg):
                continue
            cols = find_colors(to_korean(" ".join(tags) if tags else t), tg, fuzzy=bool(tags))
            if not cols:
                continue
            if not rule.get("color_shots", True):  # 색별 단독 사진이 없는 몰: 색 이름은 색상 모음 표시로만
                cols = cols + ["*"]
            q = next((q for q in pans if q[0] <= (y0 + y1) / 2 <= q[1]), None) or near(pans, y0, y1, W, rule.get("label_photo"))
            if q:
                marks.setdefault(q, set()).update(cols if len(cols) == 1 else cols + ["*"])
                seen.append(f"{path[-14:]}@{y0}:{t} → {q}")
        # 머리글(H) 아래 컷이라도 색 이름표가 하나만 붙어 있으면 그 색 사진('COLOR VIEW' 아래 색별 사진이 이어지는 경우)
        for q, s in sorted(marks.items()):
            cols = s - {"H", "*"}
            if "*" in s or len(cols) >= 2 or not cols:
                lineup = lineup or (path, *q)
            else:
                shots.setdefault(next(iter(cols)), (path, *q))
    return shots, lineup, seen


def save(cut, out):
    path, y0, y1 = cut
    im = Image.open(ROOT / path).convert("RGB")
    im = im.crop((0, y0, im.width, y1))
    im.thumbnail((800, 800))
    im.save(ROOT / out, "JPEG", quality=88)
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sample = int(sys.argv[sys.argv.index("--sample") + 1]) if "--sample" in sys.argv else 0
    t0 = time.time()
    text = DATA.read_text(encoding="utf-8")
    data = json.loads(text[text.index("{"):text.rindex("}") + 1])
    raw = {p["id"]: p for p in json.loads(RAW.read_text(encoding="utf-8"))}
    rules = json.loads(RULES.read_text(encoding="utf-8"))["malls"]
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    if "boxes" not in cache:
        cache = {"boxes": {}, "text": {}}
    reader = []

    def ocr():
        if not reader:
            import easyocr
            reader.append(easyocr.Reader(["ko", "en"], gpu=True, verbose=False))
        return reader[0]

    def boxes(path, im):
        """글자 상자 [x0, x1, y0, y1] 위에서부터. 줄인 이미지에서 위치만 찾는다(읽지 않음)."""
        if path not in cache["boxes"]:
            s = min(1.0, DET_W / im.width)
            small = np.asarray(im.resize((round(im.width * s), round(im.height * s))))
            hl, _ = ocr().detect(small, min_size=8, canvas_size=max(small.shape[:2]) + 32, mag_ratio=1.0)
            cache["boxes"][path] = sorted(([round(v / s) for v in b] for b in hl[0]), key=lambda b: b[2])
        return cache["boxes"][path]

    def read(path, im, b):
        key = f"{path}|{','.join(map(str, b))}"
        if key not in cache["text"]:
            x0, x1, y0, y1 = b
            crop = im.crop((max(0, x0 - 3), max(0, y0 - 3), x1 + 3, y1 + 3)).convert("L")
            cache["text"][key] = " ".join(ocr().recognize(np.asarray(crop), detail=0))
        return cache["text"][key]

    if not sample:
        for f in (ROOT / "images").glob("*_*.jpg"):  # 지난번 색상별 사진(상품 id에는 '_'가 없다)
            f.unlink()
        for p in data["products"]:
            p.pop("lineup", None)
            for o in p["opts"]:
                o.pop("img", None)
    done, stat = Counter(), Counter()
    for p in data["products"]:
        rule, tg = rules.get(p["mall"], {}), targets(p["opts"])
        pals = list(dict.fromkeys(pal for _, pal in tg))
        if not rule.get("enabled") or len(pals) < 2 or p["id"] not in raw or (sample and done[p["mall"]] >= sample):
            continue
        done[p["mall"]] += 1
        r = raw[p["id"]]
        shots, lineup, seen = find(r["cands"] + r.get("more", []), rule, tg, boxes, read)
        shots = {k: v for k, v in shots.items() if f"{p['id']}/{k}" not in rule.get("exclude", [])}
        stat[p["mall"], "색별"] += len(shots)
        stat[p["mall"], "모음"] += lineup is not None
        stat[p["mall"], "색 수"] += len(pals)
        if sample:
            print(p["id"], pals, "→ 색별", list(shots), "| 모음", bool(lineup))
            print("   ", seen[:8])
            continue
        for pal, cut in shots.items():
            img = save(cut, f"images/{p['id']}_c{pals.index(pal)}.jpg")
            for o in p["opts"]:
                if o.get("pal") == pal:
                    o["img"] = img
        if lineup:
            p["lineup"] = save(lineup, f"images/{p['id']}_lineup.jpg")
        if done.total() % 50 == 0:
            CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    for m, n in done.items():
        print(f"{m}: 상품 {n}개, 색 {stat[m, '색 수']}개 중 색별 사진 {stat[m, '색별']}, 색상 모음 사진 {stat[m, '모음']}개")
    print(f"{time.time() - t0:.0f}초")
    if not sample:
        DATA.write_text("window.SS = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n",
                        encoding="utf-8")


if __name__ == "__main__":
    main()
