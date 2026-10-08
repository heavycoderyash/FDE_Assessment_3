"""One-command backend verification using a temporary mock service and results folder."""
from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1",0))
        port=probe.getsockname()[1]
    env={**os.environ,"VENDOR_RISK_BASE_URL":f"http://127.0.0.1:{port}","COPILOT_MODE":"offline"}
    api=subprocess.Popen([sys.executable,"-m","uvicorn","mock_api.app:app","--host","127.0.0.1","--port",str(port),"--log-level","warning"],cwd=ROOT,env=env)
    try:
        deadline=time.monotonic()+10
        while True:
            if api.poll() is not None: raise RuntimeError("Mock API exited during startup")
            try:
                if requests.get(env["VENDOR_RISK_BASE_URL"]+"/health",timeout=.5).ok: break
            except requests.RequestException: pass
            if time.monotonic()>deadline: raise RuntimeError("Mock API startup timed out")
            time.sleep(.1)
        subprocess.run([sys.executable,"verify_setup.py"],cwd=ROOT,env=env,check=True,timeout=30)
        subprocess.run([sys.executable,"-m","pytest","-q"],cwd=ROOT,env=env,check=True,timeout=60)
        for architecture in ("single","staged"):
            subprocess.run([sys.executable,"evals/run_public_evals.py","--architecture",architecture],cwd=ROOT,env=env,check=True,timeout=30)
        with tempfile.TemporaryDirectory(prefix="procurement-check-") as output:
            subprocess.run([sys.executable,"evals/compare.py","--mode","offline","--repeat","1","--output",output],cwd=ROOT,env=env,check=True,timeout=60)
        print("\nPROJECT VERIFICATION PASSED")
    finally:
        api.terminate()
        try: api.wait(timeout=5)
        except subprocess.TimeoutExpired:
            api.kill();api.wait(timeout=5)


if __name__=="__main__": main()
