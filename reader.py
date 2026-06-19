#!/usr/bin/env python3
"""本地小说阅读器 — python3 reader.py 启动"""
import re, sys, json, webbrowser, threading
from pathlib import Path
from flask import Flask, jsonify, request, abort, render_template_string

# 书架目录：打包成 .app 后，bundle 内部只读，所以把书放到用户可写、可见的位置；
# 开发期（直接 python3 运行）则放在脚本旁边的 books/。
if getattr(sys, "frozen", False):
    BOOKS_DIR = Path.home() / "Documents" / "小说阅读器" / "books"
else:
    BOOKS_DIR = Path(__file__).parent / "books"
app = Flask(__name__)

# ── 格式解析 ─────────────────────────────────────────────────────────────────

def _split_chapters(text):
    """按常见章节标题切分，无标题则整本作一章"""
    pat = r'(?m)^(第[零一二三四五六七八九十百千万\d〇]+[章节回集卷部篇][^\n]{0,30})\n'
    parts = re.split(pat, text.strip())
    if len(parts) <= 1:
        pat2 = r'(?mi)^(Chapter\s+\d+[^\n]{0,40})\n'
        parts = re.split(pat2, text.strip())
    if len(parts) <= 1:
        return [{"title": "全文", "content": text}]
    # parts = [before, title1, body1, title2, body2, ...]
    chapters = []
    if parts[0].strip():
        chapters.append({"title": "序", "content": parts[0]})
    for i in range(1, len(parts) - 1, 2):
        chapters.append({"title": parts[i].strip(), "content": parts[i + 1]})
    return chapters

def read_txt(path):
    import chardet
    raw = path.read_bytes()
    enc = chardet.detect(raw)["encoding"] or "utf-8"
    return _split_chapters(raw.decode(enc, errors="replace"))

def read_epub(path):
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup
    book = epub.read_epub(str(path))
    chapters = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        body = soup.get_text("\n")
        if len(body.strip()) < 80:
            continue
        h = soup.find(["h1", "h2", "h3"])
        chapters.append({"title": h.get_text().strip() if h else item.get_name(), "content": body})
    return chapters or [{"title": "全文", "content": "（EPUB 解析为空）"}]

def read_pdf(path):
    import fitz
    doc = fitz.open(str(path))
    return [{"title": f"第 {i+1} 页", "content": p.get_text()} for i, p in enumerate(doc)]

def read_docx(path):
    from docx import Document
    doc = Document(str(path))
    return _split_chapters("\n".join(p.text for p in doc.paragraphs))

def read_md(path):
    return _split_chapters(path.read_text(errors="replace"))

READERS = {".txt": read_txt, ".epub": read_epub, ".pdf": read_pdf,
           ".docx": read_docx, ".md": read_md, ".mobi": read_epub, ".azw3": read_epub}

# ── API ──────────────────────────────────────────────────────────────────────

@app.route("/api/books")
def list_books():
    items = []
    for f in sorted(BOOKS_DIR.iterdir()):
        if f.suffix.lower() in READERS:
            items.append({"name": f.name, "stem": f.stem, "ext": f.suffix.lower()})
    return jsonify(items)

@app.route("/api/read/<path:name>")
def read_book(name):
    p = (BOOKS_DIR / name).resolve()
    if BOOKS_DIR.resolve() not in p.parents or not p.exists() or p.suffix.lower() not in READERS:
        abort(404)
    try:
        return jsonify(READERS[p.suffix.lower()](p))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/upload", methods=["POST"])
def upload_book():
    """拖拽 / 选择文件导入；ZIP 内的可读文件会被解压出来"""
    saved = []
    for f in request.files.getlist("files"):
        name = Path(f.filename).name
        ext = Path(name).suffix.lower()
        if ext == ".zip":
            import zipfile, io
            try:
                zf = zipfile.ZipFile(io.BytesIO(f.read()))
                for info in zf.infolist():
                    inner = Path(info.filename).name
                    if Path(inner).suffix.lower() in READERS and not info.is_dir():
                        (BOOKS_DIR / inner).write_bytes(zf.read(info))
                        saved.append(inner)
            except Exception as e:
                return jsonify({"error": f"解压失败: {e}"}), 400
        elif ext in READERS:
            f.save(str(BOOKS_DIR / name))
            saved.append(name)
    return jsonify({"saved": saved})

@app.route("/api/delete/<path:name>", methods=["POST"])
def delete_book(name):
    p = (BOOKS_DIR / name).resolve()
    if BOOKS_DIR.resolve() in p.parents and p.exists():
        p.unlink()
        return jsonify({"ok": True})
    abort(404)

# ── 前端 ─────────────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>阅读器</title>
<style>
  :root{--bg:#fdf6e3;--fg:#333;--side:#f0e8d0;--btn:#c9b99a;--hl:#8b6914}
  body.dark{--bg:#1a1a2e;--fg:#ccc;--side:#16213e;--btn:#444;--hl:#7aa2f7}
  body.eye {--bg:#c7edcc;--fg:#2d3a2d;--side:#b3deba;--btn:#7da87f;--hl:#3a7a3a}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--fg);font-family:'PingFang SC','Hiragino Sans GB',serif;display:flex;height:100vh;transition:.2s}
  #shelf{flex:1;padding:30px;overflow-y:auto}
  .shelf-head{display:flex;align-items:center;gap:14px;margin-bottom:20px}
  .shelf-head h1{font-size:22px;color:var(--hl)}
  .import-btn{background:var(--hl);color:#fff;border:none;padding:7px 16px;border-radius:6px;cursor:pointer;font-size:14px}
  .import-btn:hover{opacity:.85}
  .book-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:16px}
  .book-card{position:relative;background:var(--side);border-radius:8px;padding:16px 10px;cursor:pointer;text-align:center;transition:.15s}
  .book-card:hover{transform:translateY(-3px);box-shadow:0 4px 12px #0002}
  .book-cover{font-size:36px;margin-bottom:8px}
  .book-title{font-size:13px;line-height:1.4;word-break:break-all}
  .book-ext{font-size:11px;color:var(--btn);margin-top:4px}
  .book-del{position:absolute;top:4px;right:6px;font-size:14px;opacity:0;color:var(--hl);transition:.15s}
  .book-card:hover .book-del{opacity:.7}
  .book-del:hover{opacity:1;transform:scale(1.2)}
  body.dragging #dropzone{background:var(--side);opacity:1;border-color:var(--hl)}
  .book-del{position:absolute;top:4px;right:6px;font-size:14px;opacity:0;transition:.15s;color:#c0392b}
  .book-card{position:relative}
  .book-card:hover .book-del{opacity:.7}
  .book-del:hover{opacity:1!important;transform:scale(1.2)}
  .shelf-bar{display:flex;align-items:center;gap:12px;margin-bottom:20px}
  .shelf-bar h1{font-size:22px;color:var(--hl)}
  .shelf-bar .spacer{flex:1}
  .imp-btn{background:var(--hl);color:#fff;border:none;padding:7px 16px;border-radius:6px;cursor:pointer;font-size:14px}
  .imp-btn:hover{opacity:.85}
  body.drag #shelf{outline:3px dashed var(--hl);outline-offset:-12px}
  #reader{display:none;flex-direction:column;flex:1;height:100vh}
  #topbar{display:flex;align-items:center;gap:8px;padding:10px 16px;background:var(--side);border-bottom:1px solid var(--btn)}
  #topbar button{background:var(--btn);border:none;padding:5px 10px;border-radius:5px;cursor:pointer;color:var(--fg);font-size:13px}
  #topbar button:hover{opacity:.8}
  #topbar select{background:var(--side);border:1px solid var(--btn);color:var(--fg);padding:4px 8px;border-radius:5px;font-size:13px;max-width:220px}
  #topbar .spacer{flex:1}
  #content{flex:1;overflow-y:auto;padding:40px max(10%,30px);position:relative}
  #page{line-height:var(--lh,1.9);font-size:var(--fs,18px);white-space:pre-wrap;word-break:break-all}
  body.pagemode #content{overflow:hidden}
  body.pagemode #page{column-fill:auto;transition:transform .25s ease;will-change:transform}
  body.pagemode #content{cursor:default}
  #progress{font-size:12px;color:var(--btn);padding:6px 16px;text-align:right;background:var(--side)}
  .empty{text-align:center;padding:60px;opacity:.4;font-size:16px}
  #searchbar{display:none;align-items:center;gap:8px;padding:8px 16px;background:var(--side);border-bottom:1px solid var(--btn)}
  #searchbar input{flex:1;background:var(--bg);border:1px solid var(--btn);color:var(--fg);padding:5px 10px;border-radius:5px;font-size:14px}
  #searchbar .hits{font-size:12px;color:var(--btn);white-space:nowrap}
  mark{background:#ffd54f;color:#000;border-radius:2px}
  mark.cur{background:#ff7043;color:#fff}
  #dropzone{border:2px dashed var(--btn);border-radius:12px;padding:30px;text-align:center;margin-top:20px;opacity:.6;font-size:14px}
</style>
</head>
<body>

<div id="shelf">
  <div class="shelf-head">
    <h1>📚 我的书架</h1>
    <button class="import-btn" onclick="document.getElementById('fileInput').click()">+ 导入</button>
    <input type="file" id="fileInput" multiple accept=".txt,.epub,.pdf,.docx,.md,.mobi,.azw3,.zip" style="display:none">
  </div>
  <div class="book-grid" id="grid"></div>
  <div id="dropzone">把书拖到这里导入（TXT / EPUB / PDF / DOCX / MD / MOBI / AZW3 / ZIP）</div>
</div>

<div id="reader">
  <div id="topbar">
    <button onclick="backShelf()">← 书架</button>
    <select id="chapSel" onchange="jumpChap(this.value)"></select>
    <div class="spacer"></div>
    <button onclick="adjFont(-1)">A-</button>
    <button onclick="adjFont(1)">A+</button>
    <button onclick="adjLH(-0.1)">行-</button>
    <button onclick="adjLH(0.1)">行+</button>
    <button onclick="cycleTheme()">🎨</button>
    <button id="modeBtn" onclick="toggleMode()">📖 翻页</button>
    <button onclick="toggleSearch()">🔍</button>
    <button onclick="toggleFull()">⛶</button>
    <button onclick="viewPrev()">◀</button>
    <button onclick="viewNext()">▶</button>
  </div>
  <div id="searchbar">
    <input id="searchInput" placeholder="在本书中搜索…（回车下一个，Shift+回车上一个）">
    <span class="hits" id="hits"></span>
    <button onclick="searchStep(1)">↓</button>
    <button onclick="searchStep(-1)">↑</button>
    <button onclick="toggleSearch()">✕</button>
  </div>
  <div id="content"><div id="page"></div></div>
  <div id="progress"></div>
</div>

<script>
let chapters=[], chapIdx=0, curBook='';
const themes=['','dark','eye'];
let themeIdx=0;
// 阅读模式：'scroll' 上下滚动 / 'page' 左右翻页
let mode=localStorage.getItem('mode')||'scroll', pageIdx=0, pageCount=1, pitch=1, goLastPage=false;

async function loadShelf(){
  const r=await fetch('/api/books');
  let books=await r.json();
  const g=document.getElementById('grid');
  if(!books.length){g.innerHTML='<div class="empty">书架为空，点「+ 导入」或拖文件进来</div>';return}
  // 按最近阅读时间排序
  const lastRead=JSON.parse(localStorage.getItem('lastRead')||'{}');
  books.sort((a,b)=>(lastRead[b.name]||0)-(lastRead[a.name]||0));
  const covers={'epub':'📘','pdf':'📕','txt':'📄','md':'📝','docx':'📃','mobi':'📗','azw3':'📙'};
  g.innerHTML=books.map(b=>`
    <div class="book-card" onclick="openBook('${esc(b.name)}','${esc(b.stem)}')">
      <button class="del-btn" onclick="event.stopPropagation();delBook('${esc(b.name)}')" title="删除">✕</button>
      <div class="book-cover">${covers[b.ext.slice(1)]||'📖'}</div>
      <div class="book-title">${esc(b.stem)}</div>
      <div class="book-ext">${b.ext}${lastRead[b.name]?' · 读过':''}</div>
    </div>`).join('');
}

function esc(s){return s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}

async function openBook(name, stem){
  document.getElementById('shelf').style.display='none';
  document.getElementById('reader').style.display='flex';
  document.getElementById('page').textContent='加载中…';
  curBook=name;
  // 记录最近阅读时间
  const lastRead=JSON.parse(localStorage.getItem('lastRead')||'{}');
  lastRead[name]=Date.now(); localStorage.setItem('lastRead',JSON.stringify(lastRead));
  const r=await fetch('/api/read/'+encodeURIComponent(name));
  const data=await r.json();
  if(data.error){document.getElementById('page').textContent='解析失败: '+data.error;return}
  chapters=data;
  const sel=document.getElementById('chapSel');
  sel.innerHTML=chapters.map((c,i)=>`<option value="${i}">${i+1}. ${esc(c.title)}</option>`).join('');
  const saved=+(localStorage.getItem('chap:'+name)||0);
  chapIdx=Math.min(saved,chapters.length-1);
  applySettings();   // 先定模式，再排版
  showChap();
}

function showChap(){
  const c=chapters[chapIdx];
  const page=document.getElementById('page');
  page.textContent=c.title+'\n\n'+c.content;
  document.getElementById('content').scrollTop=0;
  document.getElementById('chapSel').value=chapIdx;
  localStorage.setItem('chap:'+curBook, chapIdx);
  layoutChap();
  if(searchOn && curQuery) doSearch(curQuery);  // 跳章后重新高亮
}

// 计算分页几何 / 复位滚动；resize 时 keepPos=true 保留页码
function layoutChap(keepPos){
  const content=document.getElementById('content'), page=document.getElementById('page');
  if(mode==='page'){
    // 每页 = 一个与可视区等宽的列；列宽 = 内容区减去左右 padding
    const cs=getComputedStyle(content);
    const padX=parseFloat(cs.paddingLeft)+parseFloat(cs.paddingRight);
    const colW=content.clientWidth-padX;
    pitch=content.clientWidth;                 // 每翻一页平移的距离
    page.style.height=(content.clientHeight-parseFloat(cs.paddingTop)-parseFloat(cs.paddingBottom))+'px';
    page.style.columnWidth=colW+'px';
    page.style.columnGap=padX+'px';
    pageCount=Math.max(1,Math.ceil((page.scrollWidth+padX)/pitch));
    if(!keepPos) pageIdx=goLastPage?pageCount-1:0;
    pageIdx=Math.min(pageIdx,pageCount-1);
    goLastPage=false;
    applyPage();
  }else{
    page.style.height=page.style.columnWidth=page.style.columnGap='';
    page.style.transform='';
    if(!keepPos) content.scrollTop=0;
    updateProgress();
  }
}

function applyPage(){
  document.getElementById('page').style.transform=`translateX(${-pageIdx*pitch}px)`;
  updateProgress();
}
function gotoPage(i){pageIdx=Math.max(0,Math.min(i,pageCount-1));applyPage()}

function updateProgress(){
  const p=document.getElementById('progress');
  if(mode==='page') p.textContent=`第 ${chapIdx+1}/${chapters.length} 章 · 第 ${pageIdx+1}/${pageCount} 页`;
  else p.textContent=`第 ${chapIdx+1} / ${chapters.length} 章`;
}

function jumpChap(i){chapIdx=+i;showChap()}
function prevChap(){if(chapIdx>0){chapIdx--;showChap()}}
function nextChap(){if(chapIdx<chapters.length-1){chapIdx++;showChap()}}

// 翻页 / 翻章统一入口（方向键、按钮、点击都走这里）
function viewNext(){
  if(mode==='page'){
    if(pageIdx<pageCount-1){pageIdx++;applyPage()}
    else if(chapIdx<chapters.length-1){chapIdx++;showChap()}
  }else nextChap();
}
function viewPrev(){
  if(mode==='page'){
    if(pageIdx>0){pageIdx--;applyPage()}
    else if(chapIdx>0){goLastPage=true;chapIdx--;showChap()}  // 回到上一章末页
  }else prevChap();
}

function toggleMode(){
  mode = mode==='page' ? 'scroll' : 'page';
  localStorage.setItem('mode',mode);
  applyMode();
  if(curBook) showChap();
}
function applyMode(){
  document.body.classList.toggle('pagemode', mode==='page');
  document.getElementById('modeBtn').textContent = mode==='page' ? '📜 滚动' : '📖 翻页';
}

function backShelf(){
  document.getElementById('reader').style.display='none';
  document.getElementById('shelf').style.display='block';
}

function adjFont(d){
  const fs=Math.min(32,Math.max(14,(parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--fs'))||18)+d));
  document.documentElement.style.setProperty('--fs',fs+'px');
  localStorage.setItem('fs',fs);
  layoutChap();   // 字号变了要重新分页
}
function adjLH(d){
  const lh=Math.min(3,Math.max(1.2,(parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--lh'))||1.9)+d)).toFixed(1);
  document.documentElement.style.setProperty('--lh',lh);
  localStorage.setItem('lh',lh);
  layoutChap();
}
function cycleTheme(){
  document.body.classList.remove('dark','eye');
  themeIdx=(themeIdx+1)%themes.length;
  if(themes[themeIdx]) document.body.classList.add(themes[themeIdx]);
  localStorage.setItem('theme',themeIdx);
}
function applySettings(){
  const fs=localStorage.getItem('fs'); if(fs) document.documentElement.style.setProperty('--fs',fs+'px');
  const lh=localStorage.getItem('lh'); if(lh) document.documentElement.style.setProperty('--lh',lh);
  themeIdx=+(localStorage.getItem('theme')||0);
  document.body.classList.remove('dark','eye');
  if(themes[themeIdx]) document.body.classList.add(themes[themeIdx]);
  applyMode();
}

// ── 导入 / 删除 ──────────────────────────────────────────────
async function uploadFiles(fileList){
  const files=[...fileList].filter(f=>/\.(txt|epub|pdf|docx|md|mobi|azw3|zip)$/i.test(f.name));
  if(!files.length){alert('没有支持的文件格式');return}
  const fd=new FormData();
  files.forEach(f=>fd.append('files',f));
  document.getElementById('dropzone').textContent='导入中…';
  const r=await fetch('/api/upload',{method:'POST',body:fd});
  const d=await r.json();
  document.getElementById('dropzone').textContent='把书拖到这里导入（TXT / EPUB / PDF / DOCX / MD / MOBI / AZW3 / ZIP）';
  if(d.error){alert(d.error);return}
  loadShelf();
}

async function delBook(name){
  if(!confirm('删除《'+name+'》？文件会从 books 文件夹移除。'))return;
  await fetch('/api/delete/'+encodeURIComponent(name),{method:'POST'});
  loadShelf();
}

// ── 书内搜索 ─────────────────────────────────────────────────
let searchOn=false, curQuery='', hitEls=[], hitIdx=0;

function toggleSearch(){
  searchOn=!searchOn;
  document.getElementById('searchbar').style.display=searchOn?'flex':'none';
  if(searchOn){document.getElementById('searchInput').focus()}
  else{curQuery='';showChap()}  // 关闭时清除高亮
}

function doSearch(q){
  curQuery=q;
  const el=document.getElementById('page');
  const c=chapters[chapIdx];
  const text=c.title+'\n\n'+c.content;
  if(!q){el.textContent=text;hitEls=[];layoutChap();updateHits();return}
  const re=new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi');
  el.innerHTML=esc(text).replace(re,m=>`<mark>${m}</mark>`);
  layoutChap();              // 重新算分页（高亮不改变文本流，页数不变）
  hitEls=[...el.querySelectorAll('mark')];
  hitIdx=0; focusHit(); updateHits();
}

function focusHit(){
  hitEls.forEach(m=>m.classList.remove('cur'));
  if(!hitEls.length)return;
  const m=hitEls[(hitIdx+hitEls.length)%hitEls.length];
  m.classList.add('cur');
  if(mode==='page'){
    // 计算命中项落在第几页，翻过去
    const page=document.getElementById('page');
    const off=m.getBoundingClientRect().left-page.getBoundingClientRect().left;
    gotoPage(Math.round(off/pitch));
  }else{
    m.scrollIntoView({block:'center'});
  }
}
function searchStep(d){if(hitEls.length){hitIdx=(hitIdx+d+hitEls.length)%hitEls.length;focusHit();updateHits()}}
function updateHits(){document.getElementById('hits').textContent=hitEls.length?`${(hitIdx%hitEls.length)+1}/${hitEls.length}`:'无结果'}

// ── 全屏 ─────────────────────────────────────────────────────
function toggleFull(){
  if(!document.fullscreenElement)document.documentElement.requestFullscreen();
  else document.exitFullscreen();
}

// ── 事件绑定 ─────────────────────────────────────────────────
document.getElementById('fileInput').addEventListener('change',e=>uploadFiles(e.target.files));

const dz=document.getElementById('dropzone');
['dragover','dragenter'].forEach(ev=>document.addEventListener(ev,e=>{e.preventDefault();dz.style.opacity=1}));
['dragleave','drop'].forEach(ev=>document.addEventListener(ev,e=>{e.preventDefault();dz.style.opacity=.6}));
document.addEventListener('drop',e=>{if(e.dataTransfer.files.length)uploadFiles(e.dataTransfer.files)});

document.getElementById('searchInput').addEventListener('input',e=>doSearch(e.target.value));
document.getElementById('searchInput').addEventListener('keydown',e=>{
  if(e.key==='Enter'){e.preventDefault();searchStep(e.shiftKey?-1:1)}
  if(e.key==='Escape')toggleSearch();
});

document.addEventListener('keydown',e=>{
  if(document.getElementById('reader').style.display==='none')return;
  if(document.activeElement.id==='searchInput')return;
  if(e.key==='ArrowLeft'){e.preventDefault();viewPrev()}
  if(e.key==='ArrowRight'){e.preventDefault();viewNext()}
  if(e.key===' '){  // 空格：翻页模式下一页；滚动模式交给浏览器默认滚动
    if(mode==='page'){e.preventDefault();e.shiftKey?viewPrev():viewNext()}
  }
  if(e.key==='f'||e.key==='F')toggleFull();
  if((e.metaKey||e.ctrlKey)&&e.key==='f'){e.preventDefault();if(!searchOn)toggleSearch()}
  if(e.key==='Escape'&&!searchOn)backShelf();
});

// 翻页模式下点击左/右半屏翻页（避开划词选择）
document.getElementById('content').addEventListener('click',e=>{
  if(mode!=='page')return;
  if(window.getSelection().toString())return;  // 正在选字，不翻页
  const x=e.clientX-e.currentTarget.getBoundingClientRect().left;
  if(x < e.currentTarget.clientWidth*0.3) viewPrev(); else viewNext();
});

// 窗口缩放：翻页模式重算分页并尽量保留当前页
let rzTimer;
window.addEventListener('resize',()=>{
  if(!curBook||mode!=='page')return;
  clearTimeout(rzTimer);
  rzTimer=setTimeout(()=>layoutChap(true),150);
});

applySettings();
loadShelf();
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

if __name__ == "__main__":
    BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"📚 书架目录: {BOOKS_DIR}")
    threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(port=5000, debug=False)
