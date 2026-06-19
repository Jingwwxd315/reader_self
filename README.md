# 小说阅读器

运行在 macOS 上的本地小说阅读器，独立窗口，多格式兼容，纯净长时间阅读。所有数据存本地，不联网。

## 直接使用

双击 `dist/小说阅读器.app` 即可。首次运行会自动创建书籍目录：

```
~/Documents/小说阅读器/books/
```

把小说文件放进去（或在 App 里点「+ 导入」、直接拖进窗口），刷新即可看到。

## 支持格式

| 类别 | 格式 |
|------|------|
| 文本 | TXT（自动识别 UTF-8 / GBK / GB18030 编码）、Markdown |
| 电子书 | EPUB、MOBI、AZW3 |
| 文档 | PDF、DOCX |
| 压缩包 | ZIP（自动解压其中的可读文件） |

## 功能

- **书架**：导入 / 拖拽、删除、按最近阅读排序
- **章节**：TXT 按「第 X 章/节/回」自动切分，目录下拉跳转，上/下章
- **排版**：字号、行距、主题（羊皮纸 / 夜间 / 护眼绿），设置自动记忆
- **进度**：每本书自动记住读到第几章，下次打开恢复
- **搜索**：书内关键词搜索并高亮定位
- **全屏**：沉浸阅读
- **快捷键**：
  - `← / →` 上一章 / 下一章
  - `F` 全屏
  - `⌘F` 书内搜索（回车下一个，Shift+回车上一个，Esc 关闭）
  - `Esc` 返回书架

## 开发 / 运行源码

```bash
# 浏览器模式（调试用）
python3 reader.py

# 独立窗口模式
python3 app.py
```

依赖：
```bash
python3 -m pip install flask chardet ebooklib beautifulsoup4 lxml PyMuPDF python-docx pywebview
```

## 重新打包 .app

```bash
./build.sh
```

产物在 `dist/小说阅读器.app`。

## 项目结构

```
reader.py      后端 + 内嵌前端（Flask，格式解析 + 单页界面）
app.py         独立窗口入口（pywebview 套 WKWebView，打包用这个做主程序）
reader.spec    PyInstaller 打包配置
build.sh       一键构建脚本
```

## 已知限制

- **MOBI / AZW3**：用 EPUB 解析器尝试读取，部分文件（尤其旧版或 DRM 加密）可能解析为空或乱码。无 DRM 的现代文件通常可读。
- **PDF**：按「页」而非「章」展示，扫描版（图片型）PDF 提取不到文字。
- **RAR**：未内置解压（需系统装 `unrar`），目前仅支持 ZIP 压缩包。
- **封面**：书架用格式图标代替真实封面（未做封面图提取）。
- **签名**：ad-hoc 签名，非 Apple 公证。首次打开若被 Gatekeeper 拦，右键点图标选「打开」即可。
