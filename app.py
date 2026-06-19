#!/usr/bin/env python3
"""独立窗口入口 —— 用系统原生 WKWebView 窗口套住阅读器界面（非浏览器）。
   开发期直接运行：python3 app.py
   打包后由 .app 的可执行文件调用 main()。"""
import threading, socket, time, sys
import webview
from reader import app, BOOKS_DIR


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_server(port, timeout=8):
    """等 Flask 起来再开窗口，避免白屏"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), 0.2).close()
            return True
        except OSError:
            time.sleep(0.1)
    return False


def main():
    BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port,
                               debug=False, use_reloader=False, threaded=True),
        daemon=True,
    ).start()
    if not _wait_server(port):
        sys.exit("本地服务启动失败")
    webview.create_window(
        "阅读器", f"http://127.0.0.1:{port}",
        width=1180, height=820, min_size=(760, 560),
    )
    webview.start()


if __name__ == "__main__":
    main()
