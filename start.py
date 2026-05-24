import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

# Backend health endpoint. We poll this so we only start the frontend when the
# backend is actually ready to serve requests.
BACKEND_URL = "http://127.0.0.1:8000/ping"
# How often we check readiness.
POLL_INTERVAL_SEC = 1.0
# Project root so child processes run in the correct folder.
ROOT_DIR = Path(__file__).resolve().parent


def is_backend_ready() -> bool:
    # A simple GET request is enough for readiness because /ping returns 200
    # only when the FastAPI app is up.
    try:
        with urlopen(BACKEND_URL, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def start_process(args: list[str]) -> subprocess.Popen:
    # Spawn a child process without blocking this script.
    return subprocess.Popen(args, cwd=str(ROOT_DIR))


def terminate_process(proc: subprocess.Popen | None, name: str) -> None:
    # Gracefully stop a child process, then force-kill if it refuses to exit.
    if proc is None or proc.poll() is not None:
        return
    print(f"Stopping {name}...")
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def wait_for_backend(backend_proc: subprocess.Popen) -> None:
    print("Waiting for backend to start...")
    while True:
        # If the backend crashes early, we stop instead of waiting forever.
        if backend_proc.poll() is not None:
            raise RuntimeError("Backend exited before becoming ready.")
        if is_backend_ready():
            print("Backend is ready.")
            return
        time.sleep(POLL_INTERVAL_SEC)


def main() -> int:
    # Start the backend first.
    backend = start_process([sys.executable, str(ROOT_DIR / "main.py")])
    frontend = None

    try:
        wait_for_backend(backend)
        print("Starting frontend...")
        # Streamlit is launched as a module so it works consistently on Windows.
        frontend = start_process(
            [sys.executable, "-m", "streamlit", "run", str(ROOT_DIR / "frontend.py")]
        )

        while True:
            # Keep the launcher alive while both processes run.
            if backend.poll() is not None:
                print("Backend exited. Shutting down frontend.")
                break
            if frontend.poll() is not None:
                print("Frontend exited. Shutting down backend.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nCtrl+C received. Shutting down...")
    except RuntimeError as exc:
        print(str(exc))
    finally:
        terminate_process(frontend, "frontend")
        terminate_process(backend, "backend")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
