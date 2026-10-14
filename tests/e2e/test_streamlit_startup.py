import subprocess
import sys
import time
from pathlib import Path

def test_streamlit_app_starts():
    app = Path("src/app/main.py")
    assert app.exists()
    process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(app), "--server.headless", "true", "--server.port", "8512"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(15)
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=15)