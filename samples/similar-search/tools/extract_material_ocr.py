"""상세 이미지의 공식 재질표 글자만 OCR로 읽어 material-records.csv를 보완한다.

사용: python tools/extract_material_ocr.py --mall bluepops
      python tools/extract_material_ocr.py --mall moremoment

옷의 외관을 분석하지 않는다. OCR 텍스트에 PRODUCT/FABRIC/소재/MATERIAL 표제와
소재명·혼용률(%)이 함께 있을 때만 값을 기록한다. checkpoint 덕분에 중단 후 재실행해도
이미 확인한 상품은 건너뛴다.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

import easyocr
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "products_raw.json"
RECORDS = ROOT / "material-data" / "material-records.csv"
CHECKPOINT = ROOT / "material-data" / "ocr-checkpoint.json"

LABEL = re.compile(r"(?:\bPRODUCT\b|\bFABRIC\b|\bMATERIAL\b|소\s*재)", re.I)
PRODUCT_BLOCK_CUE = re.compile(r"(?:\bPRODUCT\b|\bFABRIC\b|\bMATERIAL\b|소\s*재|색\s*상|제조국|원단|혼용률)", re.I)
BLOCK_END = re.compile(r"(?:\bCOMMENT\b|\bMODEL\s*INFO\b|\bDELIVERY\b|\bWASHING\b|\[\s*디테일)", re.I)
PERCENT = re.compile(r"\d{1,3}\s*%")
MATERIAL = re.compile(
    r"폴리(?:에스터)?|플리|풀리|레이온|스판(?:덱스)?|면|코튼|아크릴|나일론|울|모|린넨|"
    r"비스코스|캐시미어|실크|텐셀|모달|앙고라|알파카|폴리우레탄|큐프라|"
    r"라미|대마|마|피마|덕다운|구스다운",
    re.I,
)
OCR_PERCENT = re.compile(r"\d{1,3}(?:\s*%|9[06]|9)")
NORMALIZED_MATERIAL = {"플리": "폴리", "풀리": "폴리"}  # 규격표 OCR에서 반복 확인된 글자 혼동만 보정


def read_json(path: Path, fallback):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback


def save_csv(rows: list[dict[str, str]], fields: list[str]) -> None:
    with RECORDS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def candidate_images(product: dict) -> list[Path]:
    cands, more = product.get("cands", []), product.get("more", [])
    # 블루팝스 표본은 규격표가 대표·착용 컷 뒤(more의 6번째 이후)에 있었다.
    # 이 순서는 OCR 비용을 줄이는 탐색 우선순위일 뿐, 못 찾으면 나머지도 모두 확인한다.
    ordered = more[5:] + cands + more[:5] if product["mall_id"] == "bluepops" else cands + more
    paths = [ROOT / value for value in ordered]
    # 이전 수집 형식에 후보 목록이 빠진 경우도 같은 상품 번호 파일만 사용한다.
    if not paths:
        product_no = product["id"].split("-", 1)[-1]
        paths = list((ROOT / "cache" / product["mall_id"]).glob(f"{product_no}_*"))
    paths = [path for path in dict.fromkeys(paths) if path.exists()]
    # 흰 바탕의 규격표 이미지를 먼저 OCR해 비용을 줄인다. 재질을 이미지 모습으로 판정하는
    # 분석이 아니라, OCR할 '글자 표' 후보의 순서를 정하는 기술적 최적화다.
    def text_table_priority(path: Path) -> float:
        try:
            image = Image.open(path).convert("RGB")
            image.thumbnail((120, 240))
            pixels = np.array(image)
            return float(((pixels[:, :, 0] > 235) & (pixels[:, :, 1] > 235) & (pixels[:, :, 2] > 235)).mean())
        except Exception:
            return 0.0
    return sorted(paths, key=text_table_priority, reverse=True)


def scale_image(path: Path):
    """OCR 속도만 위해 축소한다. 이미지 내용 분류·추정에는 쓰지 않는다."""
    image = Image.open(path).convert("RGB")
    if image.height > 1500:
        image.thumbnail((900, 1500))
    return np.array(image)


def value_from_text(lines: list[str]) -> str:
    text = " ".join(line.replace("\n", " ") for line in lines)
    label_match = LABEL.search(text)
    if not label_match:
        return ""
    # 규격표는 표제 뒤에 작성되는 것이 일반적이다. 과도하게 먼 문구는 제외한다.
    window = text[label_match.end() : label_match.end() + 500]
    if not (OCR_PERCENT.search(window) and MATERIAL.search(window)):
        return ""
    # PRODUCT 이후 다음 큰 표제까지의 부분만 남긴다.
    window = re.split(r"(?:\bCOMMENT\b|\bMODEL\b|\bDELIVERY\b|제조국|세탁)", window, maxsplit=1, flags=re.I)[0]
    return re.sub(r"\s+", " ", window).strip()


def read_product_block(reader, path: Path) -> list[str]:
    """PRODUCT 주변만 다시 확대 OCR한다. 옷의 모습은 읽거나 판단하지 않는다."""
    image = scale_image(path)
    detail = reader.readtext(image, detail=1, paragraph=False)
    if not detail:
        return []
    # EasyOCR 좌표의 세로 중심을 기준으로 PRODUCT/소재 등 같은 정보 블록의 시작을 찾는다.
    entries = []
    for box, text, _confidence in detail:
        y = sum(point[1] for point in box) / len(box)
        entries.append((y, text))
    entries.sort(key=lambda item: item[0])
    start = next((y for y, text in entries if PRODUCT_BLOCK_CUE.search(text)), None)
    if start is None:
        return []
    end = next((y for y, text in entries if y > start + 20 and BLOCK_END.search(text)), image.shape[0])
    top = max(0, int(start - 35))
    bottom = min(image.shape[0], int(end + 15))
    if bottom - top < 30:
        return []
    # 작은 글자 인식률을 높이기 위해 공식 정보 블록만 확대한다.
    crop = np.array(Image.fromarray(image[top:bottom]).resize((image.shape[1] * 2, (bottom - top) * 2)))
    return reader.readtext(crop, detail=0, paragraph=True)


def parse_composition(text: str) -> tuple[str, str]:
    """OCR 원문에서 소재명+% 조각만 보존한다. 숫자/소재를 추측하지 않는다."""
    parts = []
    pattern = re.compile(r"(" + MATERIAL.pattern + r")\s*[:\-]?\s*(\d{1,3})(?:\s*%|9[06]|9)", re.I)
    for match in pattern.finditer(text):
        name, pct = NORMALIZED_MATERIAL.get(match.group(1), match.group(1)), match.group(2)
        item = f"{name} {pct}%"
        if item not in parts:
            parts.append(item)
    if not parts:
        return "", ""
    # OCR이 첫 항목을 빼먹으면 '스판 5%'처럼 부분값만 남는다. 이런 값은 혼용률로 쓰지 않는다.
    percentages = [int(re.search(r"(\d+)%$", item).group(1)) for item in parts]
    if (len(parts) == 1 and percentages[0] != 100) or sum(percentages) < 70 or sum(percentages) > 105:
        return "", ""
    return parts[0].split(" ")[0], ", ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mall", required=True, help="mall_id (예: bluepops)")
    parser.add_argument("--limit", type=int, default=0, help="시험 실행 상품 수")
    parser.add_argument("--reset", action="store_true", help="이 OCR 실행이 채운 값만 비우고 다시 시작")
    args = parser.parse_args()

    products = [p for p in read_json(RAW, []) if p["mall_id"] == args.mall]
    with RECORDS.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        rows = list(reader)
    by_id = {row["product_id"]: row for row in rows}
    checkpoint = read_json(CHECKPOINT, {"version": 1, "done": {}})
    done = checkpoint.setdefault("done", {}).setdefault(args.mall, {})
    if args.reset:
        for product_id, result in done.items():
            if result.get("result") == "found" and product_id in by_id:
                by_id[product_id]["primary"] = ""
                by_id[product_id]["composition"] = ""
        checkpoint["done"][args.mall] = {}
        save_csv(rows, fields)
        CHECKPOINT.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"reset {args.mall}")
        return
    targets = [p for p in products if not by_id.get(p["id"], {}).get("composition") and p["id"] not in done]
    if args.limit:
        targets = targets[: args.limit]

    # 이 작업 PC의 GPU를 사용해 OCR만 가속한다. 재질 판정은 여전히 표 안의 텍스트 규칙이다.
    reader = easyocr.Reader(["ko", "en"], gpu=True, verbose=False)
    changed = found = 0
    for index, product in enumerate(targets, 1):
        composition = primary = ""
        for image_path in candidate_images(product):
            try:
                lines = read_product_block(reader, image_path)
            except Exception:  # 손상 이미지 등은 다음 이미지로 진행
                continue
            spec_text = value_from_text(lines)
            primary, composition = parse_composition(spec_text)
            if composition:
                break
        done[product["id"]] = {"result": "found" if composition else "not_found"}
        if composition:
            row = by_id[product["id"]]
            row["primary"] = primary
            row["composition"] = composition
            found += 1
            changed += 1
        if index % 5 == 0 or index == len(targets):
            save_csv(rows, fields)
            CHECKPOINT.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{args.mall}: {index}/{len(targets)} processed, {found} found", flush=True)
    print(f"complete {args.mall}: {changed} newly filled", flush=True)


if __name__ == "__main__":
    main()
