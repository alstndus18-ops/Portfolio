"""29CM 브랜드 페이지를 agent-browser로 열어 tools/29cm_extract.js 로 브랜드 정보와 상품 카드를 읽는다.
  python tools/snap_29cm.py 3421 1939 ...        # 브랜드 ID 여러 개
  python tools/snap_29cm.py --file ids.txt        # 한 줄에 ID 하나(# 주석 가능)
결과: snapshots/29cm/<id>/<오늘날짜>.json  (같은 날 다시 돌리면 덮어쓴다)
화면 텍스트만 읽는다(내부 API 호출 없음). 브랜드 사이 1초 쉰다. 날마다 돌리면 snapshots/29cm/<id>/ 에 날짜별로 쌓이고
tools/diff_snapshots.py 가 날짜 사이 변화를 보여 준다.
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
JS = (Path(__file__).resolve().parent / "29cm_extract.js").read_text(encoding="utf-8")
SESSION = os.environ.get("AGENT_BROWSER_SESSION") or "gu-snap-29cm"


def ab(*args, timeout=75):
    return _ab(*args, timeout=timeout, session=SESSION)


def read_brand(bid):
    ab("open", f"https://www.29cm.co.kr/store/brand/{bid}")
    code = "(async()=>JSON.stringify(await (" + JS.strip() + ")()))()"
    raw = ab("eval", "-b", base64.b64encode(code.encode("utf-8")).decode("ascii"), timeout=120)
    # 출력은 JSON 문자열 한 번 더 감싼 형태일 수 있다
    try:
        v = json.loads(raw)
        return json.loads(v) if isinstance(v, str) else v
    except Exception:  # noqa: BLE001
        i = raw.find("{")
        return json.loads(raw[i:raw.rfind("}") + 1]) if i >= 0 else None


if __name__ == "__main__":
    args = sys.argv[1:]
    ids = []
    if args and args[0] == "--file":
        ids = [x.split("#")[0].strip() for x in Path(args[1]).read_text(encoding="utf-8").splitlines() if x.split("#")[0].strip()]
    else:
        ids = args
    today = date.today().isoformat()
    for bid in ids:
        try:
            d = read_brand(bid)
        except Exception as e:  # noqa: BLE001
            print(bid, "실패", e)
            continue
        if not d or d.get("err") or not d.get("n"):
            print(bid, "읽지 못함", (d or {}).get("title"))
            continue
        d["id"] = int(bid)
        d["observed_at"] = today
        out = ROOT / "snapshots" / "29cm" / str(bid)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{today}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(bid, d.get("ko"), "상품", d["n"], "중앙", d["p"]["med"], "할인", d["disc"]["n"], d["disc"]["med"])
        time.sleep(1)
    ab("close")
