"""data/products.json + 쇼핑몰 DB의 판매 채널 -> data.js (index.html이 읽는다).

  python tools/build.py
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURATED = ROOT.parents[1] / "research" / "fashion-commerce-map" / "data" / "curated"
BRAND = "KR-BRAND-0175"  # 그레이스유


def read(name):
    with open(CURATED / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    names = {e["id"]: e["name_ko"] for e in read("korea_entities.csv")}
    channels = [names[r["to_id"]] for r in read("korea_relationships.csv")
                if r["from_id"] == BRAND and r["relation"] == "sells_through"]
    data = json.loads((ROOT / "data" / "products.json").read_text(encoding="utf-8"))
    data["channels"] = channels
    (ROOT / "data.js").write_text("window.GU = " + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"상품 {len(data['products'])}개, 채널 {channels} -> data.js")


if __name__ == "__main__":
    main()
