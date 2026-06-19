# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置：把 app.py + reader.py 打成独立的 macOS .app
# 构建命令： python3 -m PyInstaller reader.spec --noconfirm

block_cipher = None

# 解析各格式用到的库，PyInstaller 静态分析常漏掉这些，显式声明
hidden = [
    "flask", "jinja2", "werkzeug",
    "ebooklib", "bs4", "lxml", "lxml.etree", "lxml._elementpath",
    "fitz", "pymupdf",
    "docx",
    "chardet",
    "webview", "webview.platforms.cocoa",
]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "PyQt5", "PySide6", "PyQt6"],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="小说阅读器",
    debug=False,
    strip=False,
    upx=False,
    console=False,          # 不开终端窗口
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=False,
    name="小说阅读器",
)

app = BUNDLE(
    coll,
    name="小说阅读器.app",
    icon=None,
    bundle_identifier="com.local.novelreader",
    info_plist={
        "CFBundleName": "小说阅读器",
        "CFBundleDisplayName": "小说阅读器",
        "NSHighResolutionCapable": True,    # Retina 清晰显示
        "LSMinimumSystemVersion": "12.0",
    },
)
