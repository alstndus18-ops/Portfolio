"""상품 사진에서 해당 카테고리 옷(상의면 상의)만 오려 태그를 만들고 data.js를 쓴다. 모두 이 PC에서 계산한다.

1. 옷 영역 찾기: SegFormer 의류 분할(mattmdjaga/segformer_b2_clothes). 사진 후보 중 옷이 가장 크게 잡힌 컷을 고른다.
2. 색: 오려낸 옷 픽셀만 Lab 색공간에서 3개로 묶어(k-means) 주요 색을 구하고, 색 이름표(PALETTE)에서 가장 가까운 이름을 붙인다.
3. 사진 유사도: 오려낸 이미지로 FashionCLIP(patrickjohncyh/fashion-clip). 상품명에 종류가 없을 때만 종류도 사진으로 정한다.
4. 상품명·옵션 색상: 사전(DICT) 대조. 같은 사전과 색 이름표를 웹 검색어 해석에도 쓴다.
"""
import base64
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from scipy import ndimage
from transformers import (AutoImageProcessor, AutoModelForSemanticSegmentation, CLIPModel,
                          CLIPProcessor)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "products_raw.json"
OUT = ROOT / "data.js"
CLIP_NAME = "patrickjohncyh/fashion-clip"
SEG_NAMES = ["sayeed99/segformer_b3_clothes", "mattmdjaga/segformer_b2_clothes"]  # 같은 라벨, 판정을 평균
SEG_SIDE = 768  # 분할에 넣는 사진의 긴 변
FACE, ARM_L, ARM_R, BELT, DRESS, LOWER = 11, 14, 15, 8, 7, [5, 6]
# 카테고리 -> 분할 라벨(4 상의, 5 치마, 6 바지, 7 원피스)
SEG_LABELS = {"상의": [4], "하의": [5, 6], "원피스": [7]}
MIN_AREA = 0.03  # 옷 영역이 사진의 3% 미만이면 "못 찾음"
BG = 235

# 색 이름표: 이름, 계열, 대표 RGB
PALETTE = [
    ("블랙", "black", (25, 25, 25)), ("차콜", "gray", (62, 62, 64)), ("그레이", "gray", (128, 128, 128)),
    ("라이트그레이", "gray", (190, 190, 190)), ("화이트", "white", (246, 246, 246)),
    ("아이보리", "white", (240, 234, 214)), ("크림", "white", (236, 224, 196)),
    ("베이지", "beige", (214, 194, 164)), ("오트밀", "beige", (200, 188, 168)),
    ("카멜", "brown", (188, 140, 86)), ("모카", "brown", (150, 118, 108)), ("브라운", "brown", (122, 84, 56)), ("다크브라운", "brown", (72, 50, 36)),
    ("레드", "red", (196, 36, 42)), ("버건디", "red", (112, 30, 46)),
    ("핑크", "pink", (240, 172, 192)), ("인디핑크", "pink", (204, 150, 150)), ("핫핑크", "pink", (228, 70, 140)),
    ("코랄", "orange", (244, 132, 112)), ("오렌지", "orange", (238, 130, 40)),
    ("옐로우", "yellow", (244, 214, 72)), ("머스타드", "yellow", (204, 160, 52)), ("버터", "yellow", (246, 232, 160)),
    ("연두", "green", (180, 210, 120)), ("그린", "green", (58, 138, 80)), ("카키", "green", (112, 112, 74)),
    ("올리브", "green", (124, 128, 60)), ("민트", "green", (166, 220, 200)), ("다크그린", "green", (36, 70, 50)),
    ("스카이블루", "blue", (156, 196, 230)), ("블루", "blue", (50, 100, 190)), ("데님", "blue", (92, 122, 160)),
    ("네이비", "navy", (34, 44, 80)), ("퍼플", "purple", (110, 70, 140)), ("라벤더", "purple", (190, 176, 220)),
]

# 속성: 키 -> (한국어 이름, 사진 판정 문장)
GROUPS = {
    "color": ("색", {
        "black": ("블랙", "a black top"), "white": ("화이트", "a white top"),
        "gray": ("그레이", "a gray top"), "beige": ("베이지", "a beige top"),
        "brown": ("브라운", "a brown top"), "red": ("레드", "a red top"),
        "pink": ("핑크", "a pink top"), "orange": ("오렌지", "an orange top"),
        "yellow": ("옐로우", "a yellow top"), "green": ("그린", "a green top"),
        "blue": ("블루", "a light blue top"), "navy": ("네이비", "a navy top"),
        "purple": ("퍼플", "a purple top"),
    }),
    "type": ("종류", {
        "tshirt": ("티셔츠", "a t-shirt"), "shirt": ("셔츠", "a button-up shirt"),
        "blouse": ("블라우스", "a blouse"), "knit": ("니트", "a knit sweater"),
        "cardigan": ("가디건", "a cardigan"), "sweat": ("맨투맨", "a sweatshirt"),
        "hoodie": ("후드", "a hoodie"), "sleeveless": ("나시", "a sleeveless tank top"),
        "vest": ("조끼·뷔스티에", "a vest or bustier"), "polo": ("카라티", "a polo shirt"),
        "outer": ("아우터", "a jacket or padded coat"),
    }),
    "sleeve": ("소매", {
        "long": ("긴팔", "a long sleeve top"), "short": ("반팔", "a short sleeve top"),
        "none": ("민소매", "a sleeveless top"), "three": ("7부·5부", "a three-quarter sleeve top"),
    }),
    "pattern": ("무늬", {
        "solid": ("무지", "a plain solid color top"), "stripe": ("스트라이프", "a striped top"),
        "check": ("체크", "a plaid check top"), "floral": ("플라워", "a floral print top"),
        "dot": ("도트", "a polka dot top"), "graphic": ("레터링·프린팅", "a top with graphic print or lettering"),
        "lace": ("레이스", "a lace top"), "argyle": ("아가일", "an argyle pattern top"),
    }),
    "neck": ("넥라인", {
        "round": ("라운드넥", "a crew neck top"), "vneck": ("브이넥", "a v-neck top"),
        "collar": ("카라", "a top with a shirt collar"), "turtle": ("터틀넥", "a turtleneck top"),
        "offshoulder": ("오프숄더", "an off-shoulder top"), "square": ("스퀘어넥", "a square neck top"),
        "hood": ("후드넥", "a hooded top"), "henley": ("헨리넥", "a henley neck top with a short button placket"),
        "boat": ("보트넥", "a wide boat neck top"), "halter": ("홀터넥", "a halter neck top"),
        "uneck": ("유넥", "a deep u-neck top"),
    }),
    "fit": ("핏", {
        "over": ("오버핏", "an oversized loose fit top"), "slim": ("슬림핏", "a slim fitted top"),
        "crop": ("크롭", "a cropped short top"),
    }),
    "style": ("분위기", {
        "casual": ("캐주얼", "casual everyday style"), "office": ("오피스", "office formal style"),
        "lovely": ("러블리", "feminine romantic lovely style"), "minimal": ("미니멀", "minimal basic style"),
        "street": ("스트릿", "street hip style"), "sporty": ("스포티", "sporty style"),
    }),
}
# 상품명에서만 찾는 태그(사진 판정 없음). 상품 애칭(레이·메리 등)은 사전에 없으므로 태그가 되지 않는다.
NAME_ONLY = {
    "detail": ("디테일", {
        "raglan": ("나그랑", ["나그랑", "라글란"]), "puff": ("퍼프", ["퍼프"]), "shirring": ("셔링", ["셔링"]),
        "frill": ("프릴", ["프릴", "러플"]), "ribbon": ("리본·타이", ["리본", "타이 ", "스트링"]),
        "button": ("버튼", ["버튼", "단추"]), "pocket": ("포켓", ["포켓", "주머니"]), "embroidery": ("자수", ["자수"]),
        "eyelet": ("아일렛·펀칭", ["아일렛", "펀칭"]), "layered": ("레이어드", ["레이어드", "레이어"]),
        "colorblock": ("배색", ["배색"]), "twist": ("꼬임", ["꼬임", "트위스트"]), "drape": ("드레이프", ["드레이프"]),
        "strap": ("스트랩", ["스트랩"]), "wrap": ("랩", ["랩"]), "twoway": ("투웨이", ["투웨이", "멀티웨이"]),
        "cutout": ("컷아웃·트임", ["컷아웃", "트임", "슬릿"]), "seethrough": ("시스루", ["시스루"]),
        "cable": ("꽈배기", ["꽈배기", "케이블"]), "unbal": ("언발", ["언발란스", "언발"]), "set": ("세트", ["set", "세트"]),
    }),
    "material": ("소재", {
        "linen": ("린넨", ["린넨", "리넨"]), "brushed": ("기모", ["양기모", "기모"]), "rib": ("골지", ["골지"]),
        "tencel": ("텐셀·모달", ["텐셀", "모달", "레이온"]), "velvet": ("벨벳", ["벨벳"]), "boucle": ("부클", ["부클"]),
        "waffle": ("와플", ["와플"]), "chiffon": ("시폰", ["시폰", "쉬폰"]), "cotton": ("코튼", ["코튼"]),
        "wool": ("울·캐시미어", ["캐시미어", "앙고라", "알파카", "모헤어", "울혼방"]), "satin": ("새틴", ["새틴", "사틴"]),
        "terry": ("쭈리·테리", ["쭈리", "테리"]), "span": ("스판", ["스판"]),
    }),
}

# 한국어 단어 -> 속성 값. 속성마다 긴 단어부터 맞추고, 맞춘 부분은 지운다(스웨트셔츠가 셔츠로도 잡히지 않게).
DICT = {
    "color": {
        "black": ["블랙", "검정", "검은", "먹색", "까만"],
        "white": ["화이트", "흰색", "하얀", "흰", "아이보리", "크림", "오프화이트", "백멜란지"],
        "gray": ["그레이", "회색", "차콜", "챠콜", "멜란지", "메란지", "실버"],
        "beige": ["베이지", "오트밀", "샌드", "라떼", "오트"],
        "brown": ["브라운", "갈색", "카멜", "모카", "초코", "밤색", "코코아", "브릭"],
        "red": ["레드", "빨강", "빨간", "버건디", "와인", "체리"],
        "pink": ["핑크", "분홍", "로즈", "라즈베리"],
        "orange": ["오렌지", "주황", "코랄", "테라코타", "살구"],
        "yellow": ["옐로우", "노랑", "노란", "머스타드", "레몬", "버터"],
        "green": ["그린", "초록", "녹색", "카키", "올리브", "민트", "세이지", "연두", "라임", "청록", "쑥"],
        "blue": ["블루", "파랑", "파란", "하늘", "스카이", "소라", "데님", "인디고"],
        "navy": ["네이비", "남색", "곤색"],
        "purple": ["퍼플", "보라", "라벤더", "바이올렛", "라일락"],
    },
    "type": {
        "tshirt": ["티셔츠", "반팔티", "긴팔티", "롱슬리브", "폴라티", " 티 ", " t "],
        "shirt": ["셔츠", "남방", " nb "],
        "blouse": ["블라우스"],
        "knit": ["니트", "스웨터", "꽈배기"],
        "cardigan": ["가디건"],
        "sweat": ["맨투맨", "스웨트셔츠"],
        "hoodie": ["후드 티셔츠", "후드티셔츠", "후드티", "후디", "후드 집업", "후드집업", "후드"],
        "sleeveless": ["캡나시", "나시", "민소매", "슬리브리스", "탱크탑"],
        "vest": ["조끼", "뷔스티에", "베스트"],
        "polo": ["카라티", "폴로", "피케"],
        "outer": ["자켓", "재킷", "패딩", "점퍼", "코트", "아우터", " jp "],
    },
    "sleeve": {
        "long": ["긴팔", "롱슬리브"],
        "short": ["반팔", "숏슬리브", "하프슬리브"],
        "none": ["민소매", "나시", "슬리브리스"],
        "three": ["7부", "5부", "칠부", "오부"],
    },
    "pattern": {
        "solid": ["무지"],
        "stripe": ["스트라이프", "줄무늬", "단가라"],
        "check": ["체크", "깅엄"],
        "floral": ["플라워", "꽃무늬", "플로럴"],
        "dot": ["도트", "땡땡이"],
        "graphic": ["레터링", "프린팅", "그래픽", "로고"],
        "lace": ["레이스"],
        "argyle": ["아가일"],
    },
    "neck": {
        "round": ["라운드넥", "라운드"],
        "vneck": ["브이넥", "v넥", "브이"],
        "collar": ["카라", "칼라"],
        "turtle": ["터틀넥", "목폴라", "폴라"],
        "offshoulder": ["오프숄더", "오프 숄더"],
        "square": ["스퀘어넥", "스퀘어"],
        "hood": ["후드"],
        "henley": ["헨리넥", "헨리"],
        "boat": ["보트넥"],
        "halter": ["홀터넥", "홀터"],
        "uneck": ["유넥", "u넥"],
    },
    "fit": {
        "over": ["오버핏", "루즈핏", "박시"],
        "slim": ["슬림핏", "슬림"],
        "crop": ["크롭"],
    },
    "style": {
        "casual": ["캐주얼", "데일리"],
        "office": ["오피스", "출근", "하객", "포멀"],
        "lovely": ["러블리", "페미닌", "프릴", "셔링", "퍼프"],
        "minimal": ["미니멀", "심플", "베이직"],
        "street": ["스트릿"],
        "sporty": ["스포티", "트레이닝"],
    },
    **{g: {k: ws for k, (_, ws) in vals.items()} for g, (_, vals) in NAME_ONLY.items()},
}

def text_tags(text):
    """문장에서 속성별 값 목록. 속성마다 긴 단어부터 맞추고 맞춘 부분은 지운다."""
    found = {}
    for g, d in DICT.items():
        rest = f" {text.lower()} "
        for w, k in sorted(((w, k) for k, ws in d.items() for w in ws), key=lambda x: -len(x[0])):
            if w in rest:
                found.setdefault(g, [])
                if k not in found[g]:
                    found[g].append(k)
                rest = rest.replace(w, " ")
    return found


def name_type(name):
    """상품명의 종류 단어 중 맨 뒤에 나온 것(한국어 상품명은 끝 단어가 종류). 없으면 None."""
    rest, best = f" {name.lower()} ", (-1, None)
    for w, k in sorted(((w, k) for k, ws in DICT["type"].items() for w in ws), key=lambda x: -len(x[0])):
        i = rest.rfind(w)
        if i >= 0:
            best = max(best, (i, k), key=lambda x: x[0])
            rest = rest.replace(w, " " * len(w))
    if best[1] is None and re.search(r"[가-힣](티|t)\b", name.lower()):  # 이너티·박스티·기본T
        return "tshirt"
    return best[1]


def rgb2lab(rgb):
    a = np.asarray(rgb, dtype=float) / 255
    a = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = a @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


PAL_LAB = rgb2lab(np.array([c for _, _, c in PALETTE]))
PAL_IDX = {n: i for i, (n, _, _) in enumerate(PALETTE)}

# 쇼핑몰 옵션 색 이름 -> 이름표 색. 긴 말부터, 같으면 뒤에 나온 말(한국어는 끝말이 중심) 기준.
# 값이 (색, 밝기 보정)이면 그만큼 밝기를 바꾼다(연청·진청 등).
OPT_SYN = {
    "블랙": "블랙", "검정": "블랙", "black": "블랙", "먹색": "차콜", "흑청": "차콜",
    "차콜": "차콜", "챠콜": "차콜", "진회색": "차콜", "다크그레이": "차콜",
    "그레이": "그레이", "회색": "그레이", "gray": "그레이", "grey": "그레이", "실버": "라이트그레이",
    "멜란지": "라이트그레이", "메란지": "라이트그레이", "연회색": "라이트그레이", "라이트그레이": "라이트그레이",
    "화이트": "화이트", "흰색": "화이트", "white": "화이트", "오프화이트": "아이보리", "아이보리": "아이보리", "ivory": "아이보리",
    "크림": "크림", "베이지": "베이지", "샌드": "베이지", "라떼": "베이지", "오트밀": "오트밀", "오트": "오트밀",
    "카멜": "카멜", "모카": "모카", "토프": "모카", "브라운": "브라운", "갈색": "브라운", "커피": "브라운", "브릭": "브라운",
    "밤색": "다크브라운", "초코": "다크브라운", "코코아": "다크브라운", "다크브라운": "다크브라운",
    "레드": "레드", "빨강": "레드", "체리": "레드", "와인": "버건디", "버건디": "버건디",
    "핑크": "핑크", "분홍": "핑크", "인디핑크": "인디핑크", "로즈": "인디핑크", "핫핑크": "핫핑크", "진핑크": "핫핑크",
    "피치": "코랄", "살구": "코랄", "코랄": "코랄", "오렌지": "오렌지", "주황": "오렌지", "테라코타": "오렌지",
    "옐로우": "옐로우", "노랑": "옐로우", "레몬": "옐로우", "머스타드": "머스타드", "겨자": "머스타드",
    "버터": "버터", "바닐라": "버터", "연두": "연두", "라임": "연두", "그린": "그린", "초록": "그린", "녹색": "그린",
    "카키": "카키", "쑥": "카키", "세이지": "카키", "올리브": "올리브", "민트": "민트",
    "다크그린": "다크그린", "딥그린": "다크그린", "청록": "다크그린", "포레스트": "다크그린",
    "스카이블루": "스카이블루", "스카이": "스카이블루", "하늘": "스카이블루", "소라": "스카이블루",
    "블루": "블루", "파랑": "블루", "코발트": "블루", "데님": "데님", "중청": "데님",
    "연청": ("데님", 15), "진청": ("데님", -15), "네이비": "네이비", "남색": "네이비", "곤색": "네이비",
    "퍼플": "퍼플", "보라": "퍼플", "바이올렛": "퍼플", "라벤더": "라벤더", "라일락": "라벤더", "연보라": "라벤더",
    "플럼": "퍼플", "자주": "버건디", "에메랄드": "그린", "인디고": "네이비", "스트로우베리": "레드", "스트로베리": "레드",
    "블랙멜란지": "차콜", "블랙메란지": "차콜", "차콜멜란지": "차콜", "다크멜란지": "차콜",
    "우드": "브라운", "밤": "다크브라운", "메란": "라이트그레이", "백염": "아이보리", "린넨": "오트밀",
}
OPT_MOD = {"라이트": 12, "페일": 12, "파스텔": 12, "연": 12, "다크": -12, "딥": -12, "진": -12}
KR_SIZES = [44, 55, 66, 77, 88, 99, 110]
SIZE_ORDER = ["FREE", "XS", "S", "M", "L", "XL", "XXL"] + [str(n) for n in KR_SIZES] + ["옵션 없음"]


def lab2rgb(lab):
    L, a, b = lab
    fy = (L + 16) / 116
    f = np.array([fy + a / 500, fy, fy - b / 200])
    xyz = np.where(f > 0.206893, f ** 3, (f - 16 / 116) / 7.787) * np.array([0.95047, 1.0, 1.08883])
    m = np.array([[3.2406, -1.5372, -0.4986], [-0.9689, 1.8758, 0.0415], [0.0557, -0.2040, 1.0570]])
    c = m @ xyz
    c = np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.clip(c, 0, None) ** (1 / 2.4) - 0.055)
    return np.clip(np.round(c * 255), 0, 255).astype(int)


def opt_color(name):
    """옵션 색 이름 -> {pal, fam, lab, hex}. 색 이름이 없으면 None(예: 스트라이프, A타입)."""
    t = name.lower()
    hits = [(len(w), t.rfind(w), w) for w in OPT_SYN if w in t]
    if not hits:
        return None
    _, i, w = max(hits)
    v = OPT_SYN[w]
    base, dl = (v, 0) if isinstance(v, str) else v
    dl += next((d for m, d in OPT_MOD.items() if t[max(0, i - len(m)):i] == m), 0)
    k = PAL_IDX[base]
    lab = PAL_LAB[k].copy()
    lab[0] = np.clip(lab[0] + dl, 5, 98)
    fam = PALETTE[k][1]
    same = [j for j, (_, f, _) in enumerate(PALETTE) if f == fam]
    pal = PALETTE[min(same, key=lambda j: np.linalg.norm(PAL_LAB[j] - lab))][0] if dl else base
    return {"pal": pal, "fam": fam, "lab": [round(float(x), 1) for x in lab], "hex": "#%02x%02x%02x" % tuple(lab2rgb(lab))}


def size_keys(sizes):
    """사이즈 옵션 -> 필터용 값(FREE, S·M·L, 44~110). 판매 중인 사이즈 기준, 옵션이 없으면 '옵션 없음'."""
    live = [s for s in sizes if not s["soldout"]] or sizes
    keys = set()
    for s in live:
        t = s["name"].upper().replace(" ", "")
        if re.match(r"^(F|FREE|프리|ONESIZE)(\(|$)", t):
            keys.add("FREE")
        keys.update(re.findall(r"(?<![A-Z])(XXL|XL|XS|S|M|L)(?![A-Z])", t))
        for a, b in re.findall(r"(\d{2,3})\s*[-~]\s*(\d{2,3})", t):
            keys.update(str(n) for n in KR_SIZES if int(a) <= n <= int(b) or (n == 110 and int(b) >= 100 and int(a) <= 110))
        keys.update(n for n in re.findall(r"(?<!\d)(\d{2,3})(?!\d)", t) if int(n) in KR_SIZES)
    return [k for k in SIZE_ORDER if k in keys] or ["옵션 없음"]


def name_color(lab):
    i = int(np.linalg.norm(PAL_LAB - lab, axis=1).argmin())
    return PALETTE[i][0], PALETTE[i][1]


def main_colors(rgb_pixels, k=3):
    """옷 픽셀의 주요 색(비중 큰 순). 그림자처럼 같은 계열로 갈라진 묶음은 합친다."""
    px = rgb_pixels[np.random.default_rng(0).choice(len(rgb_pixels), min(4000, len(rgb_pixels)), replace=False)]
    lab = rgb2lab(px)
    centers = np.percentile(lab, np.linspace(15, 85, k), axis=0)
    w = np.array([0.5, 1, 1])  # 그늘(밝기 차이)만으로 같은 천이 갈라지지 않게 밝기 비중을 낮춘다
    for _ in range(15):
        assign = np.linalg.norm((lab[:, None] - centers[None]) * w, axis=2).argmin(1)
        centers = np.array([lab[assign == j].mean(0) if (assign == j).any() else centers[j] for j in range(k)])
    # 한 가지 색 옷도 k개로 쪼개지므로, 밝기만 다른 가까운 묶음은 큰 쪽으로 합친다
    order = np.argsort(-np.bincount(assign, minlength=k))
    for i, j in enumerate(order):
        for big in order[:i]:
            if (assign == big).any() and np.linalg.norm((centers[j] - centers[big]) * w) < 12:
                assign[assign == j] = big
                break
    out = []
    for j in order:
        if not (assign == j).any():
            continue
        share = float((assign == j).mean())
        if share < 0.08:
            continue
        # 그늘진 부분 때문에 실제보다 어둡게 읽히므로 묶음에서 밝은 쪽 40%로 색을 정한다
        lj = lab[assign == j]
        lit = lj[:, 0] >= np.percentile(lj[:, 0], 60)
        rgb = px[assign == j][lit].mean(0).astype(int)
        centers[j] = lj[lit].mean(0)
        name, fam = name_color(centers[j])
        same = next((o for o in out if o["fam"] == fam), None)
        if same:
            same["share"] = round(same["share"] + share, 2)
            continue
        out.append({"hex": "#%02x%02x%02x" % tuple(rgb), "name": name, "fam": fam,
                    "lab": [round(float(v), 1) for v in centers[j]], "share": round(share, 2)})
    return sorted(out, key=lambda o: -o["share"])


def segment(segs, im, labels, device, side=SEG_SIDE):
    """옷 마스크·확률과 사진 정보. 분할 모델 여러 개 × 좌우 뒤집기 판정을 평균하고, 비율을 지켜 크게 넣는다.
    돌려주는 값: (마스크, 옷 확률, 사람이 입은 사진인지, 옷 덩어리 수)"""
    s = side / max(im.size)
    w, h = (max(64, round(v * s / 32) * 32) for v in im.size)
    pair = [im, im.transpose(Image.FLIP_LEFT_RIGHT)]
    with torch.no_grad():
        pr = 0
        for proc, model in segs:
            x = proc(images=pair, size={"height": h, "width": w}, return_tensors="pt").to(device)
            o = model(**x).logits.softmax(1)
            pr = pr + (o[0] + o[1].flip(-1)) / (2 * len(segs))
        pr = torch.nn.functional.interpolate(pr[None], size=im.size[::-1], mode="bilinear")[0]
        target = pr[labels].sum(0)
        rest = pr.clone()
        rest[labels] = 0
        hard = (target > rest.max(0).values).cpu().numpy()
        am = pr.argmax(0).cpu().numpy()
    # 얼굴이 보이거나 팔이 넉넉히 보이면 입은 사진. 팔 몇 픽셀만으로는 보지 않는다(행거 옷 소매를 팔로 읽는 일이 있다)
    worn = bool((am == FACE).mean() > 0.002 or np.isin(am, [ARM_L, ARM_R]).mean() > 0.015)
    if labels == SEG_LABELS["상의"]:
        # 허리선(벨트, 없으면 치마·바지 윗선) 기준: 위쪽의 "원피스" 판정은 상의로(위아래 같은 색일 때 생기는 혼동),
        # 아래로 내려간 상의 조각(허리에 묶은 가디건 등)은 뺀다
        rows = np.where((am == BELT).any(1))[0]
        if not len(rows):
            rows = np.where(np.isin(am, LOWER).sum(1) > am.shape[1] * 0.02)[0]
        if len(rows):
            y = int(rows.min() + am.shape[0] * 0.02)
            dress = am[:y] == DRESS
            hard[:y] |= dress
            below = hard[y:].sum() / max(hard.sum(), 1)
            if (dress.mean() > 0.01 or below > 0.6) and hard[:y].mean() >= 0.02:
                hard[y:] = False
    prob = target.cpu().numpy()
    # 얇게 붙은 조각(글자·끈)을 떼고, 떨어진 작은 조각(옆 사람 옷·배경 무늬)은 버리고, 옷 안의 구멍은 메운다
    hard = ndimage.binary_opening(hard, iterations=2)
    lab, n = ndimage.label(hard)
    pieces = 0
    if n:
        size = ndimage.sum(hard, lab, range(1, n + 1))
        keep = [i + 1 for i, v in enumerate(size) if v >= max(size.max() * 0.15, hard.size * 0.002)]
        pieces = len(keep)
        hard = ndimage.binary_fill_holes(np.isin(lab, keep))
    return hard, prob, worn, pieces


def cutout(im, mask):
    """옷만 남기고 나머지는 회색으로 칠해 정사각형으로 자른다. 경계만 1~2px 부드럽게."""
    alpha = ndimage.gaussian_filter(mask.astype(np.float32), 1.0)[..., None]
    arr = (np.asarray(im).astype(np.float32) * alpha + BG * (1 - alpha)).astype(np.uint8)
    ys, xs = np.where(mask)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    side = int(max(y1 - y0, x1 - x0) * 1.08) + 1
    cy, cx = (y0 + y1) // 2 + side, (x0 + x1) // 2 + side
    arr = np.pad(arr, ((side, side), (side, side), (0, 0)), constant_values=BG)
    top, left = cy - side // 2, cx - side // 2
    return Image.fromarray(arr[top:top + side, left:left + side])


def main():
    products = json.loads(RAW.read_text(encoding="utf-8"))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    seg_models = [(AutoImageProcessor.from_pretrained(n), AutoModelForSemanticSegmentation.from_pretrained(n).to(device).eval())
                  for n in SEG_NAMES]
    (ROOT / "images").mkdir(exist_ok=True)
    (ROOT / "crops").mkdir(exist_ok=True)

    crops = []
    for n, p in enumerate(products):
        labels = SEG_LABELS[p.get("category", "상의")]
        ims = [Image.open(ROOT / c).convert("RGB") for c in p["cands"]]
        segs = [segment(seg_models, im, labels, device) for im in ims]
        areas = [float(s[0].mean()) for s in segs]
        # 사진 고르기: 사람이 입은 사진 우선, 옷이 여러 벌 따로 잡힌 사진(행거·색상 모음)과
        # 여러 컷을 세로로 이어 붙인 상세 이미지는 뒤로
        score = [a * (0.3 if pieces > 2 else 1) * (1 if im.height <= im.width * 1.8 else 0)
                 for a, (_, _, _, pieces), im in zip(areas, segs, ims)]
        worn = [sc if s[2] and sc >= MIN_AREA * 1.5 else 0 for sc, s in zip(score, segs)]
        best = int(np.argmax(worn)) if max(worn) else int(np.argmax(score)) if max(score) >= MIN_AREA else int(np.argmax(areas))
        p["img"] = f"images/{p['id']}.jpg"
        shutil.copyfile(ROOT / p["cands"][best], ROOT / p["img"])
        if areas[best] >= MIN_AREA:
            mask, prob = segs[best][:2]
            # 색은 경계·그림자 섞임을 피해 안쪽의 확실한 픽셀로만 계산한다
            inner = ndimage.binary_erosion(mask, iterations=4) & (prob > 0.85)
            rgb = np.asarray(ims[best])
            p["seg"], p["area"] = "ok", round(areas[best], 3)
            p["col"] = main_colors(rgb[inner if inner.sum() >= 200 else mask])
            # 테두리 띠(6px)에서 옷의 주요 색 어느 것과도 크게 다른 픽셀(뒤 배경·치마가 섞인 것)은 뺀다
            band = mask & ~ndimage.binary_erosion(mask, iterations=6)
            if p["col"]:
                cl = np.array([c["lab"] for c in p["col"]])
                d = np.linalg.norm((rgb2lab(rgb[band])[:, None] - cl[None]) * [0.5, 1, 1], axis=2).min(1)
                mask = mask.copy()
                mask[np.where(band)[0][d > 25], np.where(band)[1][d > 25]] = False
                mask = ndimage.binary_opening(mask, iterations=1)
            crop = cutout(ims[best], mask)
        else:
            crop, p["seg"], p["area"], p["col"] = ims[best], "fail", round(areas[best], 3), []
        crop.thumbnail((384, 384))
        p["crop"] = f"crops/{p['id']}.jpg"
        crop.save(ROOT / p["crop"], "JPEG", quality=85)
        crops.append(crop)
        if (n + 1) % 50 == 0:
            print(f"분할 {n + 1}/{len(products)}")

    model = CLIPModel.from_pretrained(CLIP_NAME).to(device).eval()
    proc = CLIPProcessor.from_pretrained(CLIP_NAME)
    with torch.no_grad():
        # 사진 판정은 상품명에 종류가 없을 때 종류를 정하는 데만 쓴다(소매·핏 등 사진 태그는 잘 틀려 쓰지 않음)
        t = proc(text=[pr for _, pr in GROUPS["type"][1].values()], return_tensors="pt", padding=True).to(device)
        type_emb = model.text_projection(model.text_model(**t).pooler_output)
        type_emb = type_emb / type_emb.norm(dim=-1, keepdim=True)
        embs = []
        for i in range(0, len(crops), 32):
            x = proc(images=crops[i:i + 32], return_tensors="pt").to(device)
            e = model.visual_projection(model.vision_model(pixel_values=x["pixel_values"]).pooler_output)
            embs.append(e / e.norm(dim=-1, keepdim=True))
        img_emb = torch.cat(embs)
        keys = list(GROUPS["type"][1].keys())
        probs = (model.logit_scale.exp() * img_emb @ type_emb.T).softmax(dim=-1).cpu().numpy()
        for p, row in zip(products, probs):
            p["_type"] = (keys[int(row.argmax())], float(row.max()))

    for p in products:
        name_t = text_tags(p["name"])
        # 상품의 색 = 구매 옵션 색상. 사진 색은 '사진 속 옷이 어느 옵션인지' 맞추고, 그 옵션의 실제 색조를 보완한다.
        opts = []
        for o in p.get("colors", []):
            o = {**o, **(opt_color(o["name"]) or {})}
            opts.append(o)
        mapped = [o for o in opts if "lab" in o]
        if mapped and p["seg"] == "ok" and p["col"]:
            c0 = p["col"][0]
            d = [np.linalg.norm((np.array(o["lab"]) - c0["lab"]) * [0.5, 1, 1]) for o in mapped]
            model = [o for o in mapped if o.get("model")]
            hit = model[0] if model else (mapped[int(np.argmin(d))] if min(d) <= 30 else None)
            if hit:
                hit["photo"] = True
                if hit["fam"] == c0["fam"]:
                    hit["lab"], hit["hex"] = c0["lab"], c0["hex"]
        p["opts"], p["colorSrc"] = opts, "옵션" if mapped else "사진"
        p["sizeKeys"] = size_keys(p.get("sizes", []))
        del p["colors"]
        tags, src = {}, {}
        # 종류는 하나만: 상품명이 있으면 상품명, 없으면 사진 판정 1위
        nt = name_type(p["name"])
        k, v = p.pop("_type")
        if nt:
            tags["type"], src[f"type:{nt}"] = [nt], "상품명"
        else:
            tags["type"], src[f"type:{k}"] = [k], f"사진 {round(v * 100)}%"
        for g in NAME_ONLY:
            tags[g] = name_t.get(g, [])
            for k in tags[g]:
                src[f"{g}:{k}"] = "상품명"
        for g in GROUPS:
            if g == "type":
                continue
            vals = list(name_t.get(g, []))
            for k in vals:
                src[f"{g}:{k}"] = "상품명"
            if g == "color" and mapped:
                vals = []
                for o in mapped:
                    if o["fam"] not in vals:
                        vals.append(o["fam"])
                        src[f"color:{o['fam']}"] = "옵션 색"
            elif g == "color" and p["seg"] == "ok":
                # 색은 오려낸 옷 픽셀로 정한다. 두 번째 색은 30% 이상일 때만(배색·줄무늬)
                for c in p["col"][:2]:
                    if c is p["col"][0] or c["share"] >= 0.3:
                        if c["fam"] not in vals:
                            vals.append(c["fam"])
                        src[f"color:{c['fam']}"] = "상품명·사진 색" if f"color:{c['fam']}" in src else "사진 색"
            tags[g] = vals
        p["tags"], p["src"] = tags, src
        del p["cands"]
        p.pop("more", None)

    arr = img_emb.cpu().numpy()
    q = np.clip(np.round(arr * 127 / np.abs(arr).max()), -127, 127).astype(np.int8)
    for p, row in zip(products, q):
        p["e"] = base64.b64encode(row.tobytes()).decode()

    labels = {g: {"name": n, "values": {k: v[0] for k, v in vals.items()}}
              for g, (n, vals) in {**GROUPS, **NAME_ONLY}.items()}
    palette = [{"name": n, "fam": f, "lab": [round(float(v), 1) for v in lab]} for (n, f, _), lab in zip(PALETTE, PAL_LAB)]
    data = {"asOf": date.today().isoformat(), "models": [*SEG_NAMES, CLIP_NAME], "labels": labels,
            "dict": DICT, "palette": palette, "sizeOrder": SIZE_ORDER, "products": products}
    OUT.write_text("window.SS = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n",
                   encoding="utf-8")
    ok = sum(p["seg"] == "ok" for p in products)
    print(f"{len(products)}개 -> {OUT} (옷 영역 찾음 {ok}, 못 찾음 {len(products) - ok})")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
