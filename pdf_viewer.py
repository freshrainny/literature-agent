"""
PDF 阅读器组件
用 PyMuPDF 将 PDF 渲染为图片，叠加可选中的文字层
通过 declare_component 实现选文 → 回传 Python
"""

import base64, io, json, os
import fitz
import streamlit as st
import streamlit.components.v1 as components

# ── PDF 阅读器组件目录 ──
_COMPONENT_DIR = os.path.join(os.path.dirname(__file__), "_pdf_component")
os.makedirs(_COMPONENT_DIR, exist_ok=True)

# ── Highlights 面板组件目录 ──
_HL_COMPONENT_DIR = os.path.join(os.path.dirname(__file__), "_hl_component")
os.makedirs(_HL_COMPONENT_DIR, exist_ok=True)

# declare_component 只初始化一次
_pdf_component = None
_hl_component = None

_INDEX_HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
    background: #f0ede8;
    user-select: none;
    overflow: hidden;
  }
  #reader-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
  }
  #canvas-container {
    position: relative;
    margin: 0 auto;
    cursor: text;
    background: white;
    box-shadow: 0 2px 20px rgba(0,0,0,.12);
  }
  #page-img {
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    display: block;
    pointer-events: none;
    user-select: none;
    -webkit-user-select: none;
  }
  .word-span {
    position: absolute;
    background: transparent;
    cursor: text;
    border-radius: 1px;
  }
  .word-span.saved-hl {
    background: rgba(200, 169, 110, 0.28);
    border-radius: 2px;
  }
  .word-span.selected {
    background: rgba(255, 213, 79, 0.55);
  }
  .word-span.saved-hl.selected {
    background: rgba(255, 213, 79, 0.55);
  }
  #toolbar {
    display: none;
    position: fixed;
    background: #1a1a1a;
    border-radius: 8px;
    padding: 6px 4px;
    gap: 2px;
    box-shadow: 0 4px 16px rgba(0,0,0,.3);
    z-index: 9999;
    align-items: center;
  }
  #toolbar.visible { display: flex; }
  .tb-btn {
    background: transparent;
    border: none;
    color: #fff;
    font-size: 12px;
    padding: 5px 10px;
    border-radius: 5px;
    cursor: pointer;
    white-space: nowrap;
    transition: background .1s;
  }
  .tb-btn:hover { background: #333; }
  .tb-btn.primary { background: #c8a96e; color: #fff; }
  .tb-btn.primary:hover { background: #b8996e; }
  #toolbar-arrow {
    position: absolute;
    bottom: -6px;
    left: 50%;
    transform: translateX(-50%);
    width: 0; height: 0;
    border-left: 6px solid transparent;
    border-right: 6px solid transparent;
    border-top: 6px solid #1a1a1a;
  }
</style>
</head>
<body>
<div id="reader-wrap">
  <div id="canvas-container">
    <img id="page-img" draggable="false">
    <div id="text-layer"></div>
    <div id="toolbar">
      <button class="tb-btn primary" onclick="saveHighlight()">✦ Highlight</button>
      <button class="tb-btn" onclick="copyText()">Copy</button>
      <button class="tb-btn" onclick="clearSelection()">✕</button>
      <div id="toolbar-arrow"></div>
    </div>
  </div>
</div>

<script>
// ── Streamlit 内联通信协议 ──
// 参考 streamlit-component-lib 源码，无需 CDN
var _componentReady = false;

function _sendMsg(type, data) {
  var msg = Object.assign({isStreamlitMessage: true, type: type}, data || {});
  window.parent.postMessage(msg, '*');
}

// 监听来自 Streamlit 的 render 消息（含页面数据）
window.addEventListener('message', function(e) {
  if (!e.data || typeof e.data !== 'object') return;
  var t = e.data.type;
  if (t === 'streamlit:render') {
    var args = e.data.args || {};
    if (args.img_b64) {
      renderPage(args);
    }
  }
});

// 通知就绪
function _notifyReady() {
  _sendMsg('streamlit:componentReady', {apiVersion: 1});
}

function _setHeight(h) {
  _sendMsg('streamlit:setFrameHeight', {height: h});
}

function _setValue(val) {
  _sendMsg('streamlit:setComponentValue', {value: val});
}

// ── 页面状态 ──
var WORDS = [];
var CURRENT_PAGE = 0;
var TOTAL_PAGES = 1;
var PAPER_ID = 0;
var SAVED_HIGHLIGHTS = [];  // 当前页已保存的划线文本列表

var selectedWords = new Set();
var isSelecting = false;
var startIdx = -1;

// ── 渲染页面（由 Streamlit args 驱动）──
function renderPage(args) {
  WORDS = args.words || [];
  CURRENT_PAGE = args.current_page || 0;
  TOTAL_PAGES = args.total_pages || 1;
  PAPER_ID = args.paper_id || 0;
  SAVED_HIGHLIGHTS = args.saved_highlights || [];

  var canvasW = args.canvas_w || 800;
  var canvasH = args.canvas_h || 1000;

  var container = document.getElementById('canvas-container');
  container.style.width = canvasW + 'px';
  container.style.height = canvasH + 'px';

  var img = document.getElementById('page-img');
  img.src = 'data:image/png;base64,' + args.img_b64;

  buildTextLayer();
  _setHeight(canvasH + 20);
}

// ── 把保存的高亮文本转换为 word 索引集合 ──
// 将 WORDS 数组拼成全文字符串，然后做子串定位
function computeSavedHighlightIndices() {
  var savedSet = new Set();
  if (!SAVED_HIGHLIGHTS.length || !WORDS.length) return savedSet;

  // 构建 words 的字符拼接数组，记录每个字符对应的 word 索引
  var fullText = '';
  var charToWord = [];  // fullText[i] → WORDS 的哪个 word index
  for (var wi = 0; wi < WORDS.length; wi++) {
    var t = WORDS[wi].t;
    // 相邻词之间插入空格（非 CJK）
    if (wi > 0 && !WORDS[wi].cjk && !WORDS[wi-1].cjk) {
      fullText += ' ';
      charToWord.push(-1);  // 空格不属于任何 word
    }
    for (var ci = 0; ci < t.length; ci++) {
      fullText += t[ci];
      charToWord.push(wi);
    }
  }

  var lowerFull = fullText.toLowerCase();

  SAVED_HIGHLIGHTS.forEach(function(hlText) {
    if (!hlText) return;
    var lowerHl = hlText.toLowerCase().trim();
    // 在全文中查找所有匹配位置
    var pos = 0;
    while (pos < lowerFull.length) {
      var idx = lowerFull.indexOf(lowerHl, pos);
      if (idx === -1) break;
      // 把匹配范围内的所有字符的 word index 加入 savedSet
      for (var c = idx; c < idx + lowerHl.length; c++) {
        var wIdx = charToWord[c];
        if (wIdx >= 0) savedSet.add(wIdx);
      }
      pos = idx + 1;
    }
  });
  return savedSet;
}

// ── 构建文字层 ──
function buildTextLayer() {
  var savedSet = computeSavedHighlightIndices();
  var layer = document.getElementById('text-layer');
  layer.innerHTML = '';
  WORDS.forEach(function(w, i) {
    var span = document.createElement('div');
    span.className = 'word-span' + (savedSet.has(i) ? ' saved-hl' : '');
    span.style.left   = w.x + 'px';
    span.style.top    = w.y + 'px';
    span.style.width  = w.w + 'px';
    span.style.height = w.h + 'px';
    span.dataset.idx  = i;
    span.dataset.text = w.t;
    span.addEventListener('mousedown', onWordDown);
    span.addEventListener('mouseenter', onWordEnter);
    span.addEventListener('mouseup', onWordUp);
    layer.appendChild(span);
  });
}

function onWordDown(e) {
  e.preventDefault();
  isSelecting = true;
  startIdx = parseInt(this.dataset.idx);
  selectedWords.clear();
  selectedWords.add(startIdx);
  updateHighlight();
  hideToolbar();
}

function onWordEnter(e) {
  if (!isSelecting) return;
  var idx = parseInt(this.dataset.idx);
  var lo = Math.min(startIdx, idx);
  var hi = Math.max(startIdx, idx);
  selectedWords.clear();
  for (var i = lo; i <= hi; i++) selectedWords.add(i);
  updateHighlight();
}

function onWordUp(e) {
  if (!isSelecting) return;
  isSelecting = false;
  var idx = parseInt(this.dataset.idx);
  var lo = Math.min(startIdx, idx);
  var hi = Math.max(startIdx, idx);
  selectedWords.clear();
  for (var i = lo; i <= hi; i++) selectedWords.add(i);
  updateHighlight();
  if (selectedWords.size > 0) showToolbar(e);
}

document.addEventListener('mouseup', function(e) {
  if (isSelecting) {
    isSelecting = false;
    if (selectedWords.size > 0) showToolbar(e);
  }
});

function updateHighlight() {
  document.querySelectorAll('.word-span').forEach(function(span) {
    var i = parseInt(span.dataset.idx);
    span.classList.toggle('selected', selectedWords.has(i));
  });
}

function getSelectedText() {
  var indices = Array.from(selectedWords).sort(function(a,b){ return a-b; });
  if (indices.length === 0) return '';
  var result = '';
  for (var k = 0; k < indices.length; k++) {
    var w = WORDS[indices[k]];
    if (k === 0) {
      result += w.t;
    } else {
      var prev = WORDS[indices[k-1]];
      var needSpace = !w.cjk && !prev.cjk;
      result += (needSpace ? ' ' : '') + w.t;
    }
  }
  return result;
}

// ── 工具条 ──
function showToolbar(e) {
  var tb = document.getElementById('toolbar');
  tb.classList.add('visible');
  var container = document.getElementById('canvas-container');
  var rect = container.getBoundingClientRect();
  var minY = Infinity, maxX = 0;
  selectedWords.forEach(function(i) {
    minY = Math.min(minY, WORDS[i].y);
    maxX = Math.max(maxX, WORDS[i].x + WORDS[i].w);
  });
  var tbW = tb.offsetWidth || 200;
  var x = rect.left + (maxX / 2) - (tbW / 2);
  var y = rect.top + minY - tb.offsetHeight - 12;
  if (x < 4) x = 4;
  tb.style.left = x + 'px';
  tb.style.top  = y + 'px';
}

function hideToolbar() {
  document.getElementById('toolbar').classList.remove('visible');
}

function clearSelection() {
  selectedWords.clear();
  updateHighlight();
  hideToolbar();
}

function copyText() {
  var t = getSelectedText();
  navigator.clipboard.writeText(t).catch(function(){});
  clearSelection();
}

// ── 保存划线 ──
function saveHighlight() {
  var text = getSelectedText();
  if (!text.trim()) return;

  var idx = Array.from(selectedWords).sort(function(a,b){ return a-b; });
  var lo = Math.max(0, idx[0] - 30);
  var hi = Math.min(WORDS.length-1, idx[idx.length-1] + 30);
  var ctx = '';
  for (var i = lo; i <= hi; i++) {
    var needSpace = i > lo && !WORDS[i].cjk && !WORDS[i-1].cjk;
    ctx += (needSpace ? ' ' : '') + WORDS[i].t;
  }

  var payload = JSON.stringify({
    action: 'highlight',
    text: text.trim(),
    page: CURRENT_PAGE + 1,
    paper_id: PAPER_ID,
    context: ctx.trim(),
  });

  // 视觉反馈
  document.querySelectorAll('.word-span.selected').forEach(function(s) {
    s.style.background = 'rgba(200,169,110,0.5)';
  });

  _setValue(payload);
  // 发送后自动清空组件值，防止 Python 端 rerun 时重复处理（止住 title 闪烁循环）
  setTimeout(function() {
    _setValue(null);
    clearSelection();
  }, 800);
}

// 点击空白取消选区
document.addEventListener('mousedown', function(e) {
  if (!e.target.classList.contains('word-span') && !e.target.closest('#toolbar')) {
    clearSelection();
    hideToolbar();
  }
});

// ── 初始化 ──
_notifyReady();
</script>
</body>
</html>
"""


def _ensure_component_html():
    """确保 index.html 存在于组件目录，内容变化时自动更新"""
    html_path = os.path.join(_COMPONENT_DIR, "index.html")
    # 每次都检查内容，有变化则重写（开发期间代码会更新）
    try:
        existing = open(html_path, encoding="utf-8").read() if os.path.exists(html_path) else ""
    except Exception:
        existing = ""
    if existing != _INDEX_HTML:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(_INDEX_HTML)


def _get_component():
    global _pdf_component
    _ensure_component_html()
    if _pdf_component is None:
        _pdf_component = components.declare_component(
            "pdf_reader",
            path=_COMPONENT_DIR
        )
    return _pdf_component


def _page_to_b64(page: fitz.Page, zoom: float = 1.5) -> str:
    """将 PDF 页面渲染为 base64 PNG"""
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    buf = io.BytesIO()
    buf.write(pix.tobytes("png"))
    return base64.b64encode(buf.getvalue()).decode()


def _get_page_chars(page: fitz.Page, zoom: float = 1.5) -> list:
    """
    按字符提取页面文字及精确坐标（缩放后）。
    对中文：每个字符单独一个 span；对英文：同一个词的字符合并为一个 span。
    """
    result = []
    raw = page.get_text("rawdict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            for span in spans:
                chars = span.get("chars", [])
                i = 0
                while i < len(chars):
                    ch = chars[i]
                    c = ch.get("c", "")
                    if not c.strip():
                        i += 1
                        continue
                    bbox = ch.get("bbox", (0, 0, 0, 0))

                    cp = ord(c)
                    is_cjk = (0x4E00 <= cp <= 0x9FFF or
                              0x3400 <= cp <= 0x4DBF or
                              0xF900 <= cp <= 0xFAFF or
                              0x3000 <= cp <= 0x303F or
                              0xFF00 <= cp <= 0xFFEF)

                    if is_cjk:
                        result.append({
                            "x": bbox[0] * zoom,
                            "y": bbox[1] * zoom,
                            "w": max((bbox[2] - bbox[0]) * zoom, 2),
                            "h": max((bbox[3] - bbox[1]) * zoom, 2),
                            "t": c,
                            "cjk": True,
                        })
                        i += 1
                    else:
                        word_chars = [c]
                        x0, y0, x1, y1 = bbox
                        i += 1
                        while i < len(chars):
                            nc = chars[i].get("c", "")
                            ncp = ord(nc) if nc else 0
                            n_is_cjk = (0x4E00 <= ncp <= 0x9FFF or
                                        0x3400 <= ncp <= 0x4DBF)
                            if not nc.strip() or n_is_cjk:
                                break
                            nb = chars[i].get("bbox", (0, 0, 0, 0))
                            x1 = nb[2]
                            y1 = max(y1, nb[3])
                            word_chars.append(nc)
                            i += 1
                        result.append({
                            "x": x0 * zoom,
                            "y": y0 * zoom,
                            "w": max((x1 - x0) * zoom, 2),
                            "h": max((y1 - y0) * zoom, 2),
                            "t": "".join(word_chars),
                            "cjk": False,
                        })
    return result


def render_pdf_reader(pdf_path: str, paper_id: int, zoom: float = 1.5,
                      saved_highlights: list | None = None) -> dict | None:
    """
    渲染 PDF 阅读器。
    翻页由 Python 端按钮控制。
    saved_highlights: 已保存的划线列表（来自 DB），用于在当前页标黄显示。
    返回格式：{"action": "highlight", "text": str, "page": int, "context": str} 或 None
    """
    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    # 当前页状态
    key_page = f"pdf_page_{paper_id}"
    if key_page not in st.session_state:
        st.session_state[key_page] = 0
    current_page = st.session_state[key_page]
    current_page = max(0, min(current_page, total_pages - 1))
    st.session_state[key_page] = current_page

    # ── Python 端翻页控件 ──
    nav_col1, nav_col2, nav_col3, nav_col4, nav_col5 = st.columns([1, 1, 2, 1, 1])
    with nav_col1:
        if st.button("⟵ First", key=f"pg_first_{paper_id}", disabled=(current_page == 0)):
            st.session_state[key_page] = 0
            st.rerun()
    with nav_col2:
        if st.button("← Prev", key=f"pg_prev_{paper_id}", disabled=(current_page == 0)):
            st.session_state[key_page] = current_page - 1
            st.rerun()
    with nav_col3:
        st.markdown(
            f"<div style='text-align:center;font-size:0.82rem;color:#666;padding-top:8px;'>"
            f"p. {current_page+1} / {total_pages}</div>",
            unsafe_allow_html=True
        )
    with nav_col4:
        if st.button("Next →", key=f"pg_next_{paper_id}", disabled=(current_page >= total_pages - 1)):
            st.session_state[key_page] = current_page + 1
            st.rerun()
    with nav_col5:
        if st.button("Last ⟶", key=f"pg_last_{paper_id}", disabled=(current_page >= total_pages - 1)):
            st.session_state[key_page] = total_pages - 1
            st.rerun()

    page = doc[current_page]
    img_b64 = _page_to_b64(page, zoom)
    words = _get_page_chars(page, zoom)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    canvas_w, canvas_h = pix.width, pix.height
    doc.close()

    # 当前页的已保存高亮文本（只传当前页的，减小数据量）
    page_num_1indexed = current_page + 1
    hl_texts = []
    if saved_highlights:
        for h in saved_highlights:
            if h.get("page_number") == page_num_1indexed and h.get("content"):
                hl_texts.append(h["content"])

    # 把当前页数据作为 args 传给组件
    pdf_reader = _get_component()
    result = pdf_reader(
        img_b64=img_b64,
        words=words,
        current_page=current_page,
        total_pages=total_pages,
        paper_id=paper_id,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        saved_highlights=hl_texts,
        key=f"pdf_reader_{paper_id}",   # 同一篇论文用固定 key，翻页不重建 iframe
        default=None,
    )
    return result


# ════════════════════════════════════════════
# Highlights 面板组件
# ════════════════════════════════════════════

_HL_INDEX_HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
    background: transparent;
    padding: 0;
  }
  .hl-card {
    border-left: 3px solid #c8b89a;
    padding: 10px 14px 0 14px;
    margin: 8px 0 0 0;
    background: #fdfbf7;
    border-radius: 0 6px 0 0;
  }
  .hl-text {
    font-family: 'Georgia', serif;
    font-size: 0.88rem;
    color: #333;
    line-height: 1.65;
    font-style: italic;
  }
  .hl-meta {
    font-size: 0.74rem;
    color: #aaa;
    margin-top: 5px;
  }
  .hl-note {
    font-size: 0.74rem;
    color: #888;
    margin-top: 4px;
  }
  .tag-pill {
    display: inline-block;
    background: #f0eeea;
    color: #666;
    padding: 1px 7px;
    border-radius: 20px;
    font-size: 0.72rem;
    margin: 1px 2px 1px 0;
  }
  /* 操作栏：与卡片融为一体 */
  .hl-actions {
    border-left: 3px solid #c8b89a;
    background: #fdfbf7;
    border-radius: 0 0 6px 0;
    padding: 3px 8px 6px 8px;
    margin: 0 0 4px 0;
    display: flex;
    justify-content: flex-end;
    gap: 5px;
    align-items: center;
  }
  .hl-btn {
    font-size: 0.72rem;
    padding: 2px 10px;
    border: 1px solid #ddd8d0;
    border-radius: 4px;
    background: transparent;
    color: #888;
    cursor: pointer;
    line-height: 1.5;
    transition: all .12s;
  }
  .hl-btn:hover {
    background: #f0ede8;
    color: #555;
    border-color: #c8b89a;
  }
  .hl-btn.del:hover {
    background: #fff0f0;
    color: #d04040;
    border-color: #f0c0c0;
  }
  .empty-tip {
    color: #bbb;
    font-size: 0.82rem;
    padding: 8px 0;
  }
</style>
</head>
<body>
<div id="root"></div>
<script>
var _ready = false;
var _highlights = [];

function _sendMsg(type, data) {
  var msg = Object.assign({isStreamlitMessage: true, type: type}, data || {});
  window.parent.postMessage(msg, '*');
}
function _setValue(val) {
  _sendMsg('streamlit:setComponentValue', {value: val});
}
function _setHeight(h) {
  _sendMsg('streamlit:setFrameHeight', {height: h});
}

window.addEventListener('message', function(e) {
  if (!e.data || typeof e.data !== 'object') return;
  if (e.data.type === 'streamlit:render') {
    var args = e.data.args || {};
    _highlights = args.highlights || [];
    render();
  }
});

function render() {
  var root = document.getElementById('root');
  if (_highlights.length === 0) {
    root.innerHTML = '<div class="empty-tip">Select text in the PDF to create highlights.</div>';
    _setHeight(50);
    return;
  }
  var html = '';
  _highlights.forEach(function(h) {
    var tags = (h.tags || []).map(function(t) {
      return '<span class="tag-pill">' + esc(t) + '</span>';
    }).join('');
    var note = h.note ? '<div class="hl-note">' + esc(h.note) + '</div>' : '';
    html += '<div class="hl-card">'
      + '<div class="hl-text">' + esc(h.content.substring(0, 200)) + '</div>'
      + '<div class="hl-meta">p.' + (h.page_number || '?') + ' ' + tags + '</div>'
      + note
      + '</div>'
      + '<div class="hl-actions">'
      + '<button class="hl-btn" onclick="jump(' + h.page_number + ')">↗ p.' + (h.page_number || '?') + '</button>'
      + '<button class="hl-btn del" onclick="del(' + h.id + ')" title="Delete">🗑</button>'
      + '</div>';
  });
  root.innerHTML = html;
  _setHeight(root.scrollHeight + 10);
}

function jump(page) {
  _setValue(JSON.stringify({action: 'jump', page: page}));
  setTimeout(function() { _setValue(null); }, 400);
}

function del(id) {
  _setValue(JSON.stringify({action: 'delete', id: id}));
  setTimeout(function() { _setValue(null); }, 400);
}

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// 通知就绪
_sendMsg('streamlit:componentReady', {apiVersion: 1});
</script>
</body>
</html>
"""


def _ensure_hl_html():
    """确保 highlights 组件 index.html 存在且为最新"""
    html_path = os.path.join(_HL_COMPONENT_DIR, "index.html")
    try:
        existing = open(html_path, encoding="utf-8").read() if os.path.exists(html_path) else ""
    except Exception:
        existing = ""
    if existing != _HL_INDEX_HTML:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(_HL_INDEX_HTML)


def _get_hl_component():
    global _hl_component
    _ensure_hl_html()
    if _hl_component is None:
        _hl_component = components.declare_component(
            "hl_panel",
            path=_HL_COMPONENT_DIR,
        )
    return _hl_component


def render_highlights_panel(highlights: list, paper_id: int) -> dict | None:
    """
    渲染 highlights 面板组件。
    返回格式：
      {"action": "jump",   "page": int}  → 跳转到该页
      {"action": "delete", "id":  int}   → 删除该条
      None                               → 无操作
    """
    # 序列化，只传必要字段
    hl_data = [
        {
            "id":          h["id"],
            "content":     h["content"],
            "page_number": h.get("page_number") or 1,
            "note":        h.get("note") or "",
            "tags":        h.get("tags") or [],
        }
        for h in highlights
    ]
    comp = _get_hl_component()
    raw = comp(
        highlights=hl_data,
        key=f"hl_panel_{paper_id}",
        default=None,
    )
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None
