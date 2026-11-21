"""Start the scanner: python run.py  (or double-click start.bat)"""
import threading
import webbrowser

import uvicorn

URL = "http://127.0.0.1:8000"


def open_pages():
    webbrowser.open(f"{URL}/")
    webbrowser.open(f"{URL}/scan")


if __name__ == "__main__":
    threading.Timer(2.0, open_pages).start()
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="warning")
