from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env", override=False)


def start(cmd: list[str]) -> subprocess.Popen:
    return subprocess.Popen(cmd, cwd=ROOT)


def wait_for_api(url: str, proc: subprocess.Popen, timeout_seconds: float = 10.0) -> None:
    """Wait until the vendor risk mock API is reachable."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"Vendor-risk API exited during startup with code {proc.returncode}. "
                "Check if port 8001 is already in use."
            )
        try:
            response = requests.get(url, timeout=0.5)
            if response.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(0.25)
    raise RuntimeError(f"Service did not become ready within {timeout_seconds:.0f}s: {url}")


def _handle_termination(signum: int, frame: object) -> None:
    raise KeyboardInterrupt


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_termination)
    procs: list[subprocess.Popen] = []
    try:
        print("Starting vendor-risk API on http://127.0.0.1:8001 ...")
        api_proc = start(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "mock_api.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8001",
                "--log-level",
                "warning",
            ]
        )
        procs.append(api_proc)
        wait_for_api("http://127.0.0.1:8001/health", api_proc)
        print("Vendor-risk API is ready.")

        print("Starting Streamlit UI on http://127.0.0.1:8501 ...")
        ui_proc = start(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "app.py",
                "--server.port",
                "8501",
                "--server.headless",
                "true",
            ]
        )
        procs.append(ui_proc)

        print("\nAll services running!")
        print("  * Mock API:      http://127.0.0.1:8001")
        print("  * Streamlit UI:  http://127.0.0.1:8501")
        print("Press Ctrl+C to stop both services.\n")

        while True:
            time.sleep(1)
            for proc in procs:
                if proc.poll() is not None:
                    raise RuntimeError(f"A local process exited with code {proc.returncode}")

    except KeyboardInterrupt:
        print("\nStopping local services ...")
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()