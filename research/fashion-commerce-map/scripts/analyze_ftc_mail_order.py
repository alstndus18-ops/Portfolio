"""Create privacy-safe aggregate statistics from an FTC mail-order CSV.

The source is a public registry, but raw rows can include personal contact and
address fields. This program deliberately writes aggregate counts only.
"""

import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


FASHION_PATTERN = re.compile(
    r"의류|패션|신발|슈즈|가방|핸드백|지갑|주얼리|쥬얼리|액세서리|악세서리|"
    r"골프|아웃도어|등산|스포츠웨어|스포츠 의류|유아동복|아동복|속옷|언더웨어|"
    r"란제리|모자|시계|명품|빈티지|리셀",
    re.IGNORECASE,
)

# A handful of registry entries contain very long quoted fields. The default
# CSV safety limit is too low for this official source; raise it without ever
# serialising those fields into the derived file.
csv.field_size_limit(512 * 1024 * 1024)


def label(value: str) -> str:
    value = (value or "").strip()
    return value if value else "(미기재)"


def top(counter: Counter, limit: int = 30):
    return [
        {"label": name, "count": count}
        for name, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def safe_category(value: str) -> bool:
    """Keep only category-like labels; drop a shifted address/phone/email value."""
    return bool(re.fullmatch(r"[가-힣A-Za-z/ ]+", value)) and len(value) <= 100


def safe_institution(value: str) -> bool:
    return bool(re.fullmatch(r"[가-힣]+(?:특별시|광역시|도) [가-힣]+(?:시|군|구)(?: [가-힣]+구)?", value))


def main(input_name: str, output_name: str, source_scope: str) -> None:
    input_path = Path(input_name)
    output_path = Path(output_name)
    status_counts = Counter()
    sale_method_counts = Counter()
    product_type_counts = Counter()
    institution_counts = Counter()
    filtered_value_counts = Counter()
    total_rows = valid_rows = malformed_rows = active_rows = fashion_candidate_rows = 0

    # newline='' is required by Python's CSV implementation for quoted
    # linebreaks. utf-8-sig also consumes a possible BOM in the header.
    with input_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source)
        header = next(reader)
        header = [field.strip() for field in header]
        required = {"업소상태", "판매방식", "취급품목", "신고기관명"}
        missing = required.difference(header)
        if missing:
            raise ValueError(f"Required columns missing: {', '.join(sorted(missing))}")
        columns = {name: header.index(name) for name in required}

        for row in reader:
            if not row or row == [""]:
                continue
            total_rows += 1
            if len(row) != len(header):
                malformed_rows += 1
                continue
            valid_rows += 1
            status = row[columns["업소상태"]].strip()
            sale_method = row[columns["판매방식"]].strip()
            product_type = row[columns["취급품목"]].strip()
            institution = row[columns["신고기관명"]].strip()
            if status in {"정상영업", "폐업처리", "직권취소", "직권말소", "휴업처리", "타시군구전입", "영업재개"}:
                status_counts[status] += 1
            else:
                filtered_value_counts["status"] += 1
            if safe_category(sale_method):
                sale_method_counts[label(sale_method)] += 1
            else:
                filtered_value_counts["sale_method"] += 1
            if safe_category(product_type):
                product_type_counts[label(product_type)] += 1
            else:
                filtered_value_counts["product_type"] += 1
            if safe_institution(institution):
                institution_counts[institution] += 1
            else:
                filtered_value_counts["reporting_institution"] += 1
            if status == "정상영업":
                active_rows += 1
            if FASHION_PATTERN.search(product_type):
                fashion_candidate_rows += 1

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_scope": source_scope,
        "source_file": input_path.name,
        "privacy": {
            "raw_records_exported": False,
            "excluded_fields": ["대표자명", "전화번호", "전자우편", "사업장소재지", "사업장소재지(도로명)"],
        },
        "method": {
            "parser": "Python standard-library csv.reader (RFC 4180-style quoted-field handling)",
            "active_definition": "업소상태가 정확히 '정상영업'인 유효 행",
            "fashion_candidate_definition": "취급품목에 사전 정의한 패션 관련 키워드가 포함된 유효 행. 검증된 패션 사업자 수가 아님.",
            "malformed_row_policy": "헤더 열 수와 다른 레코드는 집계에서 제외하고 건수만 공개한다.",
            "field_safety_policy": "집계 열에서도 형식에 맞지 않는 값은 공개 목록에서 제외하고 건수만 기록한다.",
        },
        "metrics": {
            "total_parsed_rows": total_rows,
            "valid_rows": valid_rows,
            "malformed_rows": malformed_rows,
            "active_rows": active_rows,
            "fashion_candidate_rows": fashion_candidate_rows,
            "filtered_value_counts": dict(filtered_value_counts),
        },
        "breakdowns": {
            "status": top(status_counts),
            "sale_method": top(sale_method_counts),
            "product_type": top(product_type_counts),
            "reporting_institution": top(institution_counts, 40),
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output["metrics"], ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Usage: python scripts/analyze_ftc_mail_order.py <input.csv> <output.json> <source_scope>")
    main(sys.argv[1], sys.argv[2], sys.argv[3])
