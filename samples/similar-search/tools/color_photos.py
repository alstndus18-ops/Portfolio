"""상세 이미지에 인쇄된 색 이름을 OCR로 읽어 색상별 사진과 색상 모음 사진을 찾고 data.js에 넣는다.
analyze.py 다음에 돌린다. 옷을 오려 색을 재지 않고 글자로만 판단한다.

- 올리는 사람마다 글자 위치가 달라 위치를 미리 정하지 않는다. 줄인 이미지에서 글자 상자 위치만 찾고,
  짧은 상자만 읽어 색 이름을 찾는다(사진 위에 쓴 글자 포함). 옵션 색을 다 찾으면 그 상품은 멈춘다.
- 몰별 규칙(data/color-photo-rules.json)은 예외만: 끄기, 사진 밖 이름표의 사진 방향, 머리글 정규식.
- 옵션 색마다 근거 단계(ev)를 data.js에 적는다: label(그 색 이름표 사진) → lineup(색상 모음·여러 벌이 함께 찍힌 사진도 허용)
  → representative(대표 사진, 그 색인지 확인 안 됨). 몰 규칙의 evidence 목록에 없는 단계는 쓰지 않는다.
- --match: 글자(OCR) 없이, 이미 색별 사진이 있는 옵션은 두고 나머지 옵션 색만 사진 속 옷 색으로 찾는다(match_photos). 전제: 사진에
  보이는 옷 색은 모두 그 옷의 옵션 색 안에 있다. 사람이 입었든 옷만 놓였든 가리지 않고 옵션 색 중 가장 가까운 색으로 나눈다.
  분할 결과는 cache/seg_colors.json에, 몰별로 사진이 나오는 위치는 data/color-photo-learned.json에 쌓아 다음 실행을 빠르게 한다.
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


M_RGB2XYZ = np.array([[0.4124564, 0.2126729, 0.0193339], [0.3575761, 0.7151522, 0.1191920], [0.1804375, 0.0721750, 0.9503041]])


def rgb2lab(a):
    """sRGB(0~255) 배열 [..., 3]을 CIE Lab으로."""
    c = a.astype(np.float64) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    xyz = (c @ M_RGB2XYZ) / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


SEG = []  # 옷 분할 모델(처음 쓸 때만 불러온다)
GARMENT = [4, 7]  # 분할 라벨: 상의, 원피스(상의를 원피스로 읽는 일이 있다)
SEG_SIDE = 256  # 분할에 넣는 컷의 긴 변. 색만 보면 되므로 작게(384에서 컷당 1.3초 → 256에서 0.6초, CPU 기준)


def garment_colors(cut):
    """컷에서 옷 픽셀의 색을 센다. 사람이 입었든 옷만 놓였든 가리지 않는다.
    (옷이 컷에서 차지하는 비율, [(L, a, b, 비율), ...] 많은 순 6개)."""
    if not SEG:
        import torch
        from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation
        name = "mattmdjaga/segformer_b2_clothes"
        SEG.append((torch, AutoImageProcessor.from_pretrained(name), AutoModelForSemanticSegmentation.from_pretrained(name).eval()))
    torch, proc, model = SEG[0]
    s = SEG_SIDE / max(cut.size)
    w, h = (max(64, round(v * s / 32) * 32) for v in cut.size)
    with torch.no_grad():
        am = model(**proc(images=cut, size={"height": h, "width": w}, return_tensors="pt")).logits[0].argmax(0).numpy()
    mask = np.isin(am, GARMENT)
    if mask.sum() < 30:
        return 0.0, []
    small = np.asarray(cut.resize((am.shape[1], am.shape[0])))
    return round(float(mask.mean()), 3), lab_clusters(rgb2lab(small[mask]))


def lab_clusters(lab):
    """Lab 픽셀을 거친 칸으로 나눠 많은 칸 순 6개: [(L, a, b, 비율), ...]."""
    keys = np.floor(lab / [12, 10, 10]).astype(int)
    _, inv, cnt = np.unique(keys, axis=0, return_inverse=True, return_counts=True)
    out = []
    for i in np.argsort(-cnt)[:6]:
        m = lab[inv.ravel() == i].mean(axis=0)
        out.append((round(float(m[0]), 1), round(float(m[1]), 1), round(float(m[2]), 1), round(float(cnt[i] / len(lab)), 3)))
    return out


def flat_colors(cut):
    """분할 모델이 옷을 못 찾은 컷(옷걸이·평면으로 놓인 모음 사진)용 보조. 배경이 단순하면(테두리 색과 비슷한 픽셀 35% 이상) 배경과
    다른 픽셀을 옷으로 보고 색을 센다. 분할이 옷을 찾은 사진에는 쓰지 않아 모델 사진의 청바지·바닥이 옷 색으로 섞이지 않는다.
    (옷 비율, 색 덩어리, 서로 다른 색 계열 수) 또는 (0.0, [], 0)."""
    small = np.asarray(cut.resize((240, max(8, round(cut.height * 240 / cut.width)))))
    ring = np.concatenate([small[0], small[-1], small[:, 0], small[:, -1]])
    dist = np.abs(small.astype(float) - np.median(ring, axis=0)).max(axis=2)
    fg = dist > 30
    if (dist <= 20).mean() < 0.35 or fg.mean() < 0.1:
        return 0.0, [], 0
    lab = rgb2lab(small[fg])
    chroma = np.hypot(lab[:, 1], lab[:, 2])  # 채도가 낮으면 어두움·중간·밝음 3가지, 아니면 색상 45도 구간 8가지로 계열을 나눈다
    hue = (np.degrees(np.arctan2(lab[:, 2], lab[:, 1])) % 360 // 45).astype(int)
    fam = np.where(chroma < 12, np.where(lab[:, 0] < 35, 0, np.where(lab[:, 0] < 70, 1, 2)), 3 + hue)
    n = int((np.bincount(fam, minlength=11) / len(fam) >= 0.04).sum())
    return round(float(fg.mean()), 3), lab_clusters(lab), n


def de94(lab, centers):
    """Lab 색 하나와 옵션 색들(centers) 사이 CIE ΔE94(기준은 옵션 색). 기준색이 선명할수록 채도·색상 차이를 덜 따진다.
    사진 속 옷 색은 대개 옵션 색의 대표색보다 흐려서(선명한 레드 옵션이 분홍으로 찍힘) 유클리드 거리보다 알맞다."""
    L, a, b = lab
    L2, a2, b2 = centers[:, 0], centers[:, 1], centers[:, 2]
    c1, c2 = np.hypot(a2, b2), np.hypot(a, b)
    dL, dC = L - L2, c2 - c1
    dH2 = np.maximum((a - a2) ** 2 + (b - b2) ** 2 - dC ** 2, 0)
    return np.sqrt(dL ** 2 + (dC / (1 + 0.045 * c1)) ** 2 + dH2 / (1 + 0.015 * c1) ** 2)


def color_shares(clusters, centers, cap=20, margin=10, sure=10, norm_min=0):
    """옷 색 덩어리를 옵션 색 중 가장 가까운 색으로 나눈 비율. 전제: 사진에 보이는 옷 색은 모두 그 옷의 옵션 색 안에 있다.
    그래서 옵션 색의 대표색과 사진 속 색이 달라도 가장 가까운 옵션으로 본다. 다만 틀린 사진을 내놓는 것이 대표 사진보다 해로우므로
    cap(Lab 거리 20)보다 먼 덩어리, 그리고 가장 가까운 옵션이 두 번째 옵션보다 margin(10)만큼 확실히 가깝지 않은 덩어리(sure 이하로
    아주 가까우면 예외)는 어느 옵션에도 넣지 않아 비율이 낮아진다. 사라172 12개 상품을 눈으로 본 결과로 고른 값이다
    (틀린 사진 6개 → 2개, 맞는 사진 16개 → 15개; 값은 data/color-photo-learned.json 옆 learning_log에 기록)."""
    shares = np.zeros(len(centers))
    for L, a, b, share in clusters:
        d = de94((L, a, b), centers)
        o = np.argsort(d)
        k = int(o[0])
        if d[k] <= cap and (len(o) < 2 or d[o[1]] - d[k] >= margin or d[k] <= sure):
            shares[k] += share
    tot = shares.sum()
    # norm_min > 0이면 옵션 색에 분류된 픽셀 안에서의 상대 비율로 본다(분류된 픽셀이 norm_min보다 적은 컷은 제외). 사라172 눈 판정에서는
    # 켜도 결과가 거의 같아 꺼 둔다(0).
    return shares / tot if norm_min and tot >= norm_min else np.zeros(len(centers)) if norm_min else shares


def match_photos(paths, opts, cache, order=None, need=None):
    """글자 없이 사진 속 옷 색으로 옵션 색마다 가장 잘 보이는 컷을 고른다. {pal: (경로, 위, 아래, 비율, 옷 크기)}.
    비율 0.6 이상이면 그 색이 대부분인 사진(match), 그보다 낮아도 옵션 수에 맞는 기준(옵션 3개 이하 0.2, 그 이상은 0.7÷옵션 수, 최소 0.08)
    이상이면 여러 색이 함께 보이는 사진(lineup). 옵션 색을 모두 0.7 넘게 찾으면
    멈춘다. order: 사진 목록을 볼 순서(몰별로 배운 순서)."""
    want = {}
    for o in opts:
        if o.get("lab") and o.get("pal"):
            want.setdefault(o["pal"], o["lab"])
    if len(want) < 2:
        return {}
    pals = list(want)
    thr = max(0.08, min(0.2, 0.7 / len(pals)))  # 옵션이 많을수록 모음 사진에서 색당 비율이 작다
    centers = np.array([want[p] for p in pals], dtype=float)
    best, flat = {}, None  # flat: 분할이 옷을 못 찾은 단순 배경 컷 중 색 계열이 가장 많은 컷(옷걸이·평면 모음 사진)
    for path in (order(paths) if order else paths):
        if not (ROOT / path).exists():
            continue
        im = Image.open(ROOT / path).convert("RGB")
        for y0, y1 in panels(im):
            if y1 - y0 < im.width * 0.3:
                continue
            key = f"{path}|{y0}|{y1}"
            if key not in cache:
                cache[key] = list(garment_colors(im.crop((0, y0, im.width, y1))))
            area, clusters = cache[key]
            if area < 0.04:  # 분할이 옷을 못 찾음: 옷걸이·평면 사진이면 배경과 다른 부분의 색을 쓴다
                area, clusters, nfam = flat_colors(im.crop((0, y0, im.width, y1)))
                if area < 0.1:
                    continue
                if nfam >= min(3, len(pals)) and (not flat or (nfam, area) > flat[0]):
                    flat = ((nfam, area), (path, y0, y1, 0.0, area))
            for j, share in enumerate(color_shares(clusters, centers)):
                if share >= thr:
                    rank = (share >= 0.6, share, area)
                    if pals[j] not in best or rank > best[pals[j]][0]:
                        best[pals[j]] = (rank, (path, y0, y1, round(float(share), 2), area))
        if all(pal in best and best[pal][0][1] >= 0.7 for pal in (need or pals)):
            break
    if flat:  # 색을 따로 못 찾은 옵션 색에는 여러 색이 보이는 모음 사진을 쓴다(전제: 보이는 옷 색은 모두 옵션 색)
        for pal in pals:
            if pal not in best:
                best[pal] = ((False, 0.0, flat[1][4]), flat[1])
    return {k: v[1] for k, v in best.items()}


EVIDENCE = ["label", "match", "lineup", "representative"]  # 단계 순서(data/color-photo-rules.json의 fallback_policy)
SEGCACHE = ROOT / "cache" / "seg_colors.json"  # 컷별 옷 색 분할 결과(옵션과 무관해서 다시 쓸 수 있다)
LEARNED = ROOT / "data" / "color-photo-learned.json"  # 몰별로 색 사진이 나온 위치(사진 목록을 10등분한 칸별 횟수)


def allowed_evidence(rule):
    """몰 규칙의 evidence 목록(없으면 전부). 목록에 없는 단계는 쓰지 않는다."""
    return [e for e in EVIDENCE if e in (rule.get("evidence") or EVIDENCE)]


def evidence_of(opt, p):
    """옵션 색 하나가 어떤 사진을 근거로 보이는가. label(그 색 이름표 사진) → match(사진 속 옷 색이 그 색) → lineup(여러 색이 함께
    보이는 사진도 허용) → representative(대표 사진, 그 색인지 확인 안 됨). 저장된 ev가 있으면 그 값. 화면(index.html evOf)과 같다."""
    return opt.get("ev") or ("label" if opt.get("img") else "lineup" if p.get("lineup") else "representative")


def bucket(i, n):
    """사진 목록에서 i번째 사진이 어느 10등분 칸인가(몰별로 색 사진이 나오는 위치를 배울 때 쓴다)."""
    return min(9, int(10 * i / max(1, n)))


def main_match(sample=0):
    """--match: 이미 있는 색별 사진(글자로 찾은 label)은 그대로 두고, 사진이 없는 옵션 색만 사진 속 옷 색으로 찾는다(OCR 없이).
    옵션 색마다 가장 잘 보이는 컷을 images/<상품>_m<번호>.jpg로 저장하고 ev를 match(그 색이 대부분)·lineup(여러 색이 함께)로 적는다.
    못 찾은 색은 사진 없이 두어 화면이 대표 사진(representative)을 보여 준다. 몰별로 사진이 나온 위치를 data/color-photo-learned.json에
    쌓아 다음 실행에서 그 위치부터 보고, 분할 결과는 cache/seg_colors.json에 두어 같은 사진을 다시 분할하지 않는다."""
    sys.stdout.reconfigure(encoding="utf-8")
    t0 = time.time()
    text = DATA.read_text(encoding="utf-8")
    data = json.loads(text[text.index("{"):text.rindex("}") + 1])
    raw = {p["id"]: p for p in json.loads(RAW.read_text(encoding="utf-8"))}
    rules = json.loads(RULES.read_text(encoding="utf-8"))["malls"]
    seg = json.loads(SEGCACHE.read_text(encoding="utf-8")) if SEGCACHE.exists() else {}
    learned = json.loads(LEARNED.read_text(encoding="utf-8")) if LEARNED.exists() else {}
    only = sys.argv[sys.argv.index("--mall") + 1] if "--mall" in sys.argv else None  # 한 몰만
    if not sample:  # 지난번 match 결과를 지운다(--mall이면 그 몰 것만. 다른 몰 결과를 지우면 안 된다)
        mine = {p["id"] for p in data["products"] if not only or p["mall"] == only}
        for f in (ROOT / "images").glob("*_m*.jpg"):
            if f.stem.rsplit("_m", 1)[0] in mine:
                f.unlink()
        for p in data["products"]:
            if only and p["mall"] != only:
                continue
            for o in p["opts"]:
                if o.get("ev") in ("match", "lineup"):  # 색 하나를 위해 고른 사진(글자로 찾은 label은 그대로 둔다)
                    o.pop("img", None)
                if o.get("ev") in ("match", "lineup", "representative"):
                    o.pop("ev")
    done, stat, last = Counter(), Counter(), time.time()
    for p in data["products"]:
        rule = rules.get(p["mall"], {})
        allowed = allowed_evidence(rule)
        pals = list(dict.fromkeys(o["pal"] for o in p["opts"] if o.get("pal")))
        if (only and p["mall"] != only) or not ({"match", "lineup"} & set(allowed)) or len(pals) < 2 or p["id"] not in raw or (sample and done[p["mall"]] >= sample):
            continue
        need = [pal for pal in pals if not any(o.get("pal") == pal and o.get("img") for o in p["opts"])]
        if not need:
            continue
        done[p["mall"]] += 1
        r = raw[p["id"]]
        paths = r["cands"] + r.get("more", [])
        st = learned.setdefault(p["mall"], {"pos": [0] * 10, "n": 0})
        order = lambda ps, st=st: sorted(ps, key=lambda x: -st["pos"][bucket(ps.index(x), len(ps))])  # noqa: E731  많이 나온 칸부터
        found = match_photos(paths, p["opts"], seg, order, need)
        if time.time() - last > 60:  # 오래 걸리는 실행이 중간에 끊겨도 분할 결과가 남게 1분마다 저장
            SEGCACHE.parent.mkdir(exist_ok=True)
            SEGCACHE.write_text(json.dumps(seg), encoding="utf-8")
            last = time.time()
            print(f"  {done.total()}개 처리, {time.time() - t0:.0f}초", flush=True)
        stat[p["mall"], "필요"] += len(need)
        got = {}
        for pal in need:
            if pal not in found:
                continue
            path, y0, y1, share, area = found[pal]
            kind = "match" if share >= 0.6 and "match" in allowed else "lineup"
            if kind not in allowed:
                continue
            got[pal] = (kind, (path, y0, y1), share)
            stat[p["mall"], kind] += 1
        if sample:
            print(p["id"], "필요", need, "→", {k: (v[0], v[2]) for k, v in got.items()})
            continue
        for pal, (kind, cut, share) in got.items():
            img = save(cut, f"images/{p['id']}_m{pals.index(pal)}.jpg")
            for o in p["opts"]:
                if o.get("pal") == pal:
                    o["img"], o["ev"] = img, kind
            st["pos"][bucket(paths.index(cut[0]), len(paths))] += 1
            st["n"] += 1
    SEGCACHE.parent.mkdir(exist_ok=True)
    SEGCACHE.write_text(json.dumps(seg), encoding="utf-8")
    for m in done:
        print(f"{m}: 상품 {done[m]}개, 사진이 없던 색 {stat[m, '필요']}개 중 match {stat[m, 'match']}, lineup {stat[m, 'lineup']}")
    if not sample:
        ev = Counter()
        for p in data["products"]:
            for o in p["opts"]:
                if "pal" in o:
                    o["ev"] = evidence_of(o, p)
                    ev[p["mall"], o["ev"]] += 1
        for m in sorted({p["mall"] for p in data["products"]}):
            print(f"{m}: 근거 " + ", ".join(f"{k} {ev[m, k]}" for k in EVIDENCE))
        LEARNED.write_text(json.dumps(learned, ensure_ascii=False, indent=1), encoding="utf-8")
        DATA.write_text("window.SS = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"{time.time() - t0:.0f}초")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sample = int(sys.argv[sys.argv.index("--sample") + 1]) if "--sample" in sys.argv else 0
    if "--match" in sys.argv:
        return main_match(sample)
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
                o.pop("ev", None)
    done, stat = Counter(), Counter()
    for p in data["products"]:
        rule, tg = rules.get(p["mall"], {}), targets(p["opts"])
        pals = list(dict.fromkeys(pal for _, pal in tg))
        if not rule.get("enabled") or len(pals) < 2 or p["id"] not in raw or (sample and done[p["mall"]] >= sample):
            continue
        done[p["mall"]] += 1
        r = raw[p["id"]]
        paths = r["cands"] + r.get("more", [])
        shots, lineup, seen = find(paths, rule, tg, boxes, read)
        shots = {k: v for k, v in shots.items() if f"{p['id']}/{k}" not in rule.get("exclude", [])}
        allowed = allowed_evidence(rule)
        if "label" not in allowed:  # 몰 규칙이 색별 사진을 쓰지 않게 했다
            shots = {}
        if "lineup" not in allowed:  # 여러 벌이 함께 찍힌 사진을 쓰지 않게 했다
            lineup = None
        stat[p["mall"], "색별"] += len(shots)
        stat[p["mall"], "모음"] += lineup is not None
        stat[p["mall"], "색 수"] += len(pals)
        if sample:
            rest = len(pals) - len(shots)
            print(p["id"], pals, "→ 색별", list(shots), "| 모음", bool(lineup),
                  "| 근거 label", len(shots), "lineup", rest if lineup else 0, "representative", 0 if lineup else rest)
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
    if not sample:
        # 모든 옵션 색에 근거 단계를 적는다(규칙이 꺼진 몰·색 1개 상품도 representative로 남긴다)
        ev = Counter()
        for p in data["products"]:
            for o in p["opts"]:
                if "pal" in o:
                    o["ev"] = evidence_of(o, p)
                    ev[p["mall"], o["ev"]] += 1
        for m in sorted({p["mall"] for p in data["products"]}):
            print(f"{m}: 근거 " + ", ".join(f"{k} {ev[m, k]}" for k in EVIDENCE))
    print(f"{time.time() - t0:.0f}초")
    if not sample:
        DATA.write_text("window.SS = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n",
                        encoding="utf-8")


if __name__ == "__main__":
    main()
