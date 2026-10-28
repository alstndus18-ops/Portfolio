"""agent-browser 호출 공통 도구. 시간 초과가 나면 자식 프로세스까지 정리하고 빈 문자열을 돌려준다.
(Windows에서 shell=True로 부르면 시간 초과 뒤에도 파이프가 안 닫혀 파이썬이 영원히 멈추기 때문이다.)
세션은 환경변수 AGENT_BROWSER_SESSION 으로 정한다.
"""
import os
import subprocess

TIMEOUTS = []  # 시간 초과가 난 호출을 모아 둔다


def ab(*args, timeout=75, session=None):
    env = dict(os.environ)
    if session:
        env["AGENT_BROWSER_SESSION"] = session
    p = subprocess.Popen(["agent-browser", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", env=env, shell=(os.name == "nt"))
    try:
        out, _ = p.communicate(timeout=timeout)
        return out.strip()
    except subprocess.TimeoutExpired:
        TIMEOUTS.append(args[:2])
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
        else:
            p.kill()
        try:
            p.communicate(timeout=5)
        except Exception:  # noqa: BLE001
            pass
        return ""
