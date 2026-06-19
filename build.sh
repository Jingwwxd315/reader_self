#!/bin/bash
# 一键构建 小说阅读器.app
# 用法： ./build.sh
set -e
cd "$(dirname "$0")"
export PATH="$HOME/Library/Python/3.9/bin:$PATH"

echo "==> 清理旧的构建产物"
rm -rf build dist

echo "==> PyInstaller 打包"
python3 -m PyInstaller reader.spec --noconfirm

echo "==> 清除扩展属性并 ad-hoc 签名（iCloud 目录需要）"
xattr -cr "dist/小说阅读器.app"
codesign --force --deep -s - "dist/小说阅读器.app"

echo ""
echo "✅ 完成： dist/小说阅读器.app"
echo "   双击运行，或拖到「应用程序」文件夹。"
echo "   书籍放在： ~/Documents/小说阅读器/books/"
