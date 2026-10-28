"""W컨셉 브랜드관을 agent-browser로 열어 tools/wconcept_extract.js 로 브랜드 소개와 상품 카드를 읽는다.
  python tools/snap_wconcept.py 108809 102698 ...      # W컨셉 브랜드 ID
  python tools/snap_wconcept.py --file data/wconcept_ids.txt
결과: snapshots/wconcept/<id>/<오늘날짜>.json . 화면 텍스트만 읽는다. 브랜드 사이 1초 쉰다.
"""
import base64
import json
import os
import subprocess
from ab_util import ab as _ab
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = (Path(__file__).resolve().parent / "wconcept_extract.js").read_text(encoding="utf-8")
SESSION = os.environ.get("AGENT_BROWSER_SESSION") or "gu-snap-wc"


def ab(*args, timeout=75):
    return _ab(*args, timeout=timeout, session=SESSION)


def read_brand(bid):
    ab("open", f"https://display.wconcept.co.kr/rn/brand/{bid}")
    code = "(async()=>JSON.stringify(await (" + JS.strip() + ")()))()"
    raw = ab("eval", "-b", base64.b64encode(code.encode("utf-8")).decode("ascii"))
    v = json.loads(raw)
    return json.loads(v) if isinstance(v, str) else v


if __name__ == "__main__":
    args = sys.argv[1:]
    ids = [x.split("#")[0].strip() for x in Path(args[1]).read_text(encoding="utf-8").splitlines() if x.split("#")[0].strip()] if args and args[0] == "--file" else args
    today = date.today().isoformat()
    for bid in ids:
        try:
            d = read_brand(bid)
        except Exception as e:  # noqa: BLE001
            print(bid, "실패", repr(e)[:120])
            continue
        if not d or not d.get("n"):
            print(bid, "읽지 못함", (d or {}).get("ko"))
            continue
        d["id"] = int(bid)
        d["observed_at"] = today
        out = ROOT / "snapshots" / "wconcept" / str(bid)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{today}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(bid, d.get("ko"), "상품", d["n"], "중앙", d["p"]["med"], "할인", d["disc"]["n"], d["disc"]["med"])
        time.sleep(1)
    ab("close")
