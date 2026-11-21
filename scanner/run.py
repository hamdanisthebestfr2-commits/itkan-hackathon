"""Start the app: python run.py  (or double-click start.bat)"""
import socket
import sys
import threading
import urllib.request
import webbrowser

import uvicorn

HOST, PORT = "127.0.0.1", 8000
URL = f"http://{HOST}:{PORT}"


def open_pages():
    webbrowser.open(f"{URL}/")
    webbrowser.open(f"{URL}/scan")


def port_in_use() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((HOST, PORT)) == 0


def our_app_running() -> bool:
    try:
        with urllib.request.urlopen(f"{URL}/api/reference", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


if __name__ == "__main__":
    if port_in_use():
        if our_app_running():
            # Double-clicking start.bat twice used to crash with "only one usage of each socket address".
            print("Iris is ALREADY RUNNING (another start.bat window is open).")
            print("Opening it in your browser. To restart it, close the other black window first.")
            open_pages()
        else:
            print(f"Port {PORT} is being used by another program. Close it, then run start.bat again.")
        sys.exit(0)
    threading.Timer(2.0, open_pages).start()
    uvicorn.run("app.main:app", host=HOST, port=PORT, log_level="warning")
