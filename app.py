"""
文献管理系统 — Librarian
图书馆风格 UI，简洁高级
"""

import streamlit as st
import os, sys, json, time, re, fitz
import requests

sys.path.insert(0, os.path.dirname(__file__))

from database import (
    init_database, get_all_papers, get_paper_by_id,
    get_highlights_by_paper, get_all_highlights,
    search_papers, delete_paper, save_paper,
    save_highlight, add_highlight_to_vector_db,
    semantic_search_highlights,
    update_paper_keywords, get_all_keywords,
    # Collections
    get_all_collections, create_collection, delete_collection,
    add_paper_to_collection, remove_paper_from_collection,
    get_papers_in_collection, get_collections_for_paper,
    # My Thesis
    get_my_thesis, save_my_thesis,
    # highlight suggestion
    update_highlight_suggestion,
    # paper notes
    update_paper_notes,
)
from tools import generate_citation
from agent import LiteratureAssistant, LLM_PROVIDERS
from pdf_viewer import render_pdf_reader, render_highlights_panel

# ─────────────────────────────────────────
# 基础配置
# ─────────────────────────────────────────
st.set_page_config(
    page_title="Librarian",
    page_icon="⬛",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_database()
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ─────────────────────────────────────────
# 全局样式
# ─────────────────────────────────────────
st.markdown("""
<style>
/* ── 字体 & 基础 ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Lora:ital,wght@0,400;0,600;1,400&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, sans-serif;
}

/* ── 隐藏 Streamlit 默认装饰 ── */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
.block-container { padding: 2rem 2rem 4rem; max-width: 1400px; }

/* ── 侧边栏 ── */
[data-testid="stSidebar"] {
    background: #f5f4f0;
    border-right: 1px solid #e4e2db;
}
[data-testid="stSidebar"] * { color: #1a1a1a !important; }
[data-testid="stSidebar"] hr { border-color: #ddd !important; }
[data-testid="stSidebar"] input {
    background: #fff !important;
    border: 1px solid #d0cdc6 !important;
    color: #1a1a1a !important;
    border-radius: 6px !important;
}
[data-testid="stSidebar"] input::placeholder { color: #aaa !important; }
[data-testid="stSidebar"] input:focus {
    border-color: #999 !important;
    box-shadow: 0 0 0 2px rgba(0,0,0,.06) !important;
}
[data-testid="stSidebar"] select,
[data-testid="stSidebar"] [data-baseweb="select"] {
    background: #fff !important;
    color: #1a1a1a !important;
    border: 1px solid #d0cdc6 !important;
    border-radius: 6px !important;
}

/* ── 主内容区背景 ── */
.main { background: #fafaf9; }

/* ── 通用卡片 ── */
.lib-card {
    background: #fff;
    border: 1px solid #e8e8e4;
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 8px;
    transition: border-color .15s, box-shadow .15s;
}
.lib-card:hover {
    border-color: #c8c8c4;
    box-shadow: 0 2px 12px rgba(0,0,0,.06);
}

/* ── 文献卡片标题 ── */
.paper-title {
    font-family: 'Lora', serif;
    font-size: 1.05rem;
    font-weight: 600;
    color: #1a1a1a;
    line-height: 1.4;
    margin-bottom: 4px;
}
.paper-meta {
    font-size: 0.8rem;
    color: #888;
    margin-bottom: 10px;
}
.paper-abstract {
    font-size: 0.85rem;
    color: #555;
    line-height: 1.6;
}

/* ── 划线卡片 ── */
.hl-card {
    border-left: 3px solid #c8b89a;
    padding: 12px 16px;
    margin: 8px 0;
    background: #fdfbf7;
    border-radius: 0 6px 6px 0;
}
.hl-text {
    font-family: 'Lora', serif;
    font-size: 0.9rem;
    color: #333;
    line-height: 1.65;
    font-style: italic;
}
.hl-meta {
    font-size: 0.75rem;
    color: #aaa;
    margin-top: 6px;
}

/* ── 引用框 ── */
.cite-block {
    background: #f5f4f0;
    border-radius: 6px;
    padding: 12px 16px;
    font-size: 0.82rem;
    color: #444;
    line-height: 1.6;
    font-family: 'Georgia', serif;
    border: 1px solid #e0ddd6;
}

/* ── 标签 ── */
.tag-pill {
    display: inline-block;
    background: #f0eeea;
    color: #666;
    padding: 2px 9px;
    border-radius: 20px;
    font-size: 0.74rem;
    margin: 2px 3px 2px 0;
}

/* ── 状态点 ── */
.dot-green { color: #22c55e; font-size: 0.55rem; vertical-align: middle; }
.dot-gray  { color: #aaa;    font-size: 0.55rem; vertical-align: middle; }

/* ── 页面标题 ── */
.page-header {
    font-family: 'Lora', serif;
    font-size: 1.5rem;
    font-weight: 600;
    color: #1a1a1a;
    margin-bottom: 4px;
}
.page-sub {
    font-size: 0.82rem;
    color: #999;
    margin-bottom: 24px;
}

/* ── 聊天气泡 ── */
.msg-user {
    background: #1a1a1a;
    color: #f5f5f5;
    border-radius: 12px 12px 2px 12px;
    padding: 12px 16px;
    font-size: 0.88rem;
    max-width: 75%;
    margin-left: auto;
    margin-bottom: 12px;
    line-height: 1.55;
}
.msg-agent {
    background: #fff;
    color: #1a1a1a;
    border: 1px solid #e8e8e4;
    border-radius: 12px 12px 12px 2px;
    padding: 12px 16px;
    font-size: 0.88rem;
    max-width: 80%;
    margin-bottom: 12px;
    line-height: 1.65;
}
.msg-wrap { display: flex; flex-direction: column; gap: 4px; padding: 8px 0; }

/* ── 页面内 Tab 导航 ── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 0 !important;
    border-bottom: 1px solid #e8e8e4 !important;
    background: transparent !important;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    font-size: 0.85rem !important;
    font-family: 'Inter', sans-serif !important;
    color: #aaa !important;
    padding: 10px 20px 10px 0 !important;
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    margin-right: 8px !important;
}
[data-testid="stTabs"] [data-baseweb="tab"]:hover {
    color: #555 !important;
    background: transparent !important;
}
[data-testid="stTabs"] [aria-selected="true"] {
    color: #1a1a1a !important;
    font-weight: 500 !important;
    border-bottom: 2px solid #1a1a1a !important;
    background: transparent !important;
}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { display: none !important; }
[data-testid="stTabs"] [data-baseweb="tab-border"] { display: none !important; }

/* ── 统计数字 ── */
.stat-num {
    font-size: 1.8rem;
    font-weight: 600;
    color: #1a1a1a;
    line-height: 1;
}
.stat-label {
    font-size: 0.72rem;
    color: #888;
    text-transform: uppercase;
    letter-spacing: .06em;
    margin-top: 3px;
}

/* ── Agent 思考状态 ── */
.thinking-row {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #999;
    font-size: 0.82rem;
    padding: 8px 0;
}

/* ── 输入框美化 ── */
.stTextInput input, .stTextArea textarea, .stSelectbox select {
    border-radius: 6px !important;
    border: 1px solid #e0ddd6 !important;
    font-size: 0.88rem !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: #aaa !important;
    box-shadow: 0 0 0 2px rgba(0,0,0,.06) !important;
}

/* ── 按钮 ── */
.stButton > button {
    border-radius: 6px !important;
    font-size: 0.84rem !important;
    font-weight: 500 !important;
    border: 1px solid #e0ddd6 !important;
    background: #fff !important;
    color: #333 !important;
    padding: 6px 14px !important;
    transition: all .15s !important;
}
.stButton > button:hover {
    border-color: #999 !important;
    background: #f9f8f5 !important;
}
.stButton[data-testid*="primary"] > button,
button[kind="primary"] {
    background: #1a1a1a !important;
    color: #fff !important;
    border-color: #1a1a1a !important;
}
button[kind="primary"]:hover {
    background: #333 !important;
}

/* (hl-btn-wrap styles moved into _hl_component/index.html) */

/* ── 分隔线 ── */
hr { border-color: #ebebeb !important; margin: 16px 0 !important; }

/* ── st.pills tag 筛选 ── */
[data-testid="stPills"] {
    gap: 6px !important;
    flex-wrap: wrap !important;
    margin-bottom: 8px !important;
}
[data-testid="stPills"] button {
    border-radius: 20px !important;
    font-size: 0.73rem !important;
    font-weight: 400 !important;
    padding: 2px 11px !important;
    height: auto !important;
    min-height: 0 !important;
    line-height: 1.8 !important;
    border: 1px solid #e0ddd6 !important;
    background: #f5f4f0 !important;
    color: #666 !important;
    transition: all .12s !important;
}
[data-testid="stPills"] button:hover {
    border-color: #bbb !important;
    background: #eae8e3 !important;
    color: #333 !important;
}
[data-testid="stPills"] button[aria-pressed="true"],
[data-testid="stPills"] button[data-selected="true"] {
    background: #2a2520 !important;
    color: #fff !important;
    border-color: #2a2520 !important;
}

/* ── 文件夹卡片 ── */
.folder-card {
    background: #fff;
    border: 1px solid #e8e8e4;
    border-radius: 10px;
    padding: 20px 22px;
    cursor: pointer;
    transition: border-color .15s, box-shadow .15s;
    margin-bottom: 0;
}
.folder-card:hover {
    border-color: #bbb;
    box-shadow: 0 3px 14px rgba(0,0,0,.07);
}
.folder-card-icon { font-size: 1.5rem; margin-bottom: 10px; }
.folder-card-name { font-size: 0.92rem; font-weight: 500; color: #1a1a1a; margin-bottom: 4px; }
.folder-card-meta { font-size: 0.72rem; color: #aaa; }

/* ── 侧边栏内部收起箭头：美化样式 ── */
[data-testid="stSidebarCollapseButton"] button {
    color: #888 !important;
    border-radius: 6px !important;
}
[data-testid="stSidebarCollapseButton"] button:hover {
    background: #eceae4 !important;
    color: #333 !important;
}

/* ── 展开按钮（侧边栏折叠后显示在左边缘）：美化样式 ── */
[data-testid="stExpandSidebarButton"] {
    position: fixed !important;
    left: 0 !important;
    top: 50% !important;
    transform: translateY(-50%) !important;
    z-index: 99999 !important;
    width: 28px !important;
    height: 52px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    background: #f5f4f0 !important;
    border: 1px solid #d0cdc6 !important;
    border-left: none !important;
    border-radius: 0 8px 8px 0 !important;
    box-shadow: 2px 2px 8px rgba(0,0,0,.10) !important;
    cursor: pointer !important;
    pointer-events: all !important;
    visibility: visible !important;
    opacity: 1 !important;
}
[data-testid="stExpandSidebarButton"]:hover {
    background: #e8e5de !important;
}
[data-testid="stExpandSidebarButton"] button {
    width: 100% !important;
    height: 100% !important;
    background: transparent !important;
    border: none !important;
    cursor: pointer !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    color: #555 !important;
    font-size: 14px !important;
    padding: 0 !important;
}
[data-testid="stExpandSidebarButton"] svg {
    color: #555 !important;
    fill: #555 !important;
    width: 14px !important;
    height: 14px !important;
}
/* 抖起时隐藏左边缘的 collapsedControl （已被 stExpandSidebarButton 替代） */
[data-testid="collapsedControl"] { display: none !important; }

/* ── 上传区域 ── */
[data-testid="stFileUploader"] {
    border: 2px dashed #ddd !important;
    border-radius: 10px !important;
    background: #fafaf9 !important;
    padding: 16px !important;
}

/* ── Notebook 全屏覆盖层 ── */
.notebook-overlay {
    position: fixed;
    inset: 0;
    background: #f2efe8;
    z-index: 9999;
    overflow-y: auto;
    padding: 0;
}
.notebook-topbar {
    position: sticky;
    top: 0;
    background: #ece9e1;
    border-bottom: 1px solid #d8d3c8;
    padding: 12px 40px;
    display: flex;
    align-items: center;
    gap: 16px;
    z-index: 10000;
}
.notebook-paper {
    max-width: 760px;
    margin: 40px auto 80px;
    background: #fffef9;
    border: 1px solid #ddd9ce;
    border-radius: 2px;
    box-shadow: 0 2px 24px rgba(0,0,0,.08), 2px 2px 0 #e8e3d8, 4px 4px 0 #ddd9ce;
    padding: 56px 64px;
    min-height: 600px;
    font-family: 'Lora', serif;
    line-height: 1.8;
    color: #2a2520;
    position: relative;
}
.notebook-paper::before {
    content: '';
    position: absolute;
    left: 88px;
    top: 0;
    bottom: 0;
    border-left: 1px solid #e8c8b0;
    opacity: .45;
}
.notebook-title {
    font-family: 'Lora', serif;
    font-size: 1.35rem;
    font-weight: 600;
    color: #1a1714;
    line-height: 1.4;
    margin-bottom: 4px;
    border-bottom: 1px solid #e8e3d8;
    padding-bottom: 16px;
    margin-bottom: 24px;
}
.notebook-empty {
    text-align: center;
    padding: 80px 0;
    color: #bbb;
    font-family: 'Inter', sans-serif;
    font-size: 0.88rem;
    letter-spacing: .04em;
}

/* ── Notebook 内容排版 ── */
.notebook-content { font-family: 'Lora', serif; font-size: 0.95rem; line-height: 1.85; color: #2a2520; }
.notebook-content h1 { font-size: 1.25rem; font-weight: 600; color: #1a1714; border-bottom: 1px solid #e8e3d8; padding-bottom: 8px; margin: 28px 0 14px; }
.notebook-content h2 { font-size: 1.05rem; font-weight: 600; color: #1a1714; margin: 24px 0 10px; }
.notebook-content h3 { font-size: 0.95rem; font-weight: 600; color: #3a3028; margin: 18px 0 8px; }
.notebook-content p  { margin: 0 0 12px; }
.notebook-content ul, .notebook-content ol { padding-left: 1.4em; margin: 0 0 12px; }
.notebook-content li { margin-bottom: 5px; }
.notebook-content strong { color: #1a1714; font-weight: 600; }
.notebook-content em { color: #7a6a3e; font-style: italic; }
.notebook-content blockquote {
    border-left: 3px solid #c8b89a;
    margin: 12px 0;
    padding: 6px 14px;
    background: #fdf9f4;
    color: #5a4e3e;
    font-style: italic;
}
.notebook-content hr { border: none; border-top: 1px solid #e0dbd0; margin: 20px 0; }
.notebook-content table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 0.88rem; }
.notebook-content th { background: #f5f2ec; font-weight: 600; padding: 7px 12px; border: 1px solid #ddd9ce; text-align: left; }
.notebook-content td { padding: 6px 12px; border: 1px solid #e8e3d8; }
.notebook-content code { font-family: monospace; background: #f0ede6; padding: 1px 5px; border-radius: 3px; font-size: 0.85em; color: #4a3e2e; }
.notebook-content pre { background: #f0ede6; padding: 12px 16px; border-radius: 6px; overflow-x: auto; font-size: 0.85rem; }

/* ── Notebook 编辑模式：让 textarea 看起来在纸张里 ── */
.notebook-edit-wrap {
    max-width: 760px;
    margin: 0 auto 80px;
    background: #fffef9;
    border: 1px solid #ddd9ce;
    border-radius: 2px;
    box-shadow: 0 2px 24px rgba(0,0,0,.08), 2px 2px 0 #e8e3d8, 4px 4px 0 #ddd9ce;
    padding: 40px 64px 48px;
    position: relative;
}
.notebook-edit-wrap::before {
    content: '';
    position: absolute;
    left: 88px;
    top: 0;
    bottom: 0;
    border-left: 1px solid #e8c8b0;
    opacity: .45;
}
.notebook-edit-wrap .nb-edit-title {
    font-family: 'Lora', serif;
    font-size: 1.15rem;
    font-weight: 600;
    color: #1a1714;
    border-bottom: 1px solid #e8e3d8;
    padding-bottom: 12px;
    margin-bottom: 4px;
}
.notebook-edit-wrap .nb-edit-meta {
    font-size: 0.75rem;
    color: #bbb;
    font-family: Inter, sans-serif;
    letter-spacing: .04em;
    margin-bottom: 16px;
}
/* textarea 撑满纸张内部，无边框装饰 */
.notebook-edit-wrap .stTextArea textarea {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    font-family: 'Lora', serif !important;
    font-size: 0.93rem !important;
    line-height: 1.85 !important;
    color: #2a2520 !important;
    padding: 0 !important;
    resize: none !important;
}

/* ── 文献详情面板 ── */
.detail-panel {
    background: #fff;
    border: 1px solid #e8e8e4;
    border-radius: 10px;
    padding: 24px;
    height: fit-content;
    position: sticky;
    top: 20px;
}
.detail-title {
    font-family: 'Lora', serif;
    font-size: 1.2rem;
    font-weight: 600;
    color: #1a1a1a;
    line-height: 1.4;
    margin-bottom: 6px;
}
.detail-author {
    font-size: 0.85rem;
    color: #666;
    margin-bottom: 16px;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
# 元数据解析辅助函数
# ─────────────────────────────────────────

def _parse_pdf_meta(pdf_path: str) -> dict:
    """从 PDF 前3页提取标题、作者、年份、DOI、摘要（启发式规则）"""
    meta = {"title": "", "authors_str": "", "year": 2024,
            "journal": "", "doi": "", "abstract": ""}
    try:
        doc = fitz.open(pdf_path)
        pages_to_scan = min(3, len(doc))
        full_text = ""
        for pi in range(pages_to_scan):
            full_text += doc[pi].get_text() + "\n"

        # DOI
        doi_m = re.search(r'10\.\d{4,}/[^\s,;"\'>\]]+', full_text)
        if doi_m:
            meta["doi"] = doi_m.group(0).rstrip(".")

        # 年份：优先找 "published/received/accepted/©" 附近的年份，
        # 其次取前3页所有年份中出现频率最高的那个
        year_priority_m = re.search(
            r'(?:published|received|accepted|©|copyright)\D{0,20}?\b(20[0-2]\d|19[89]\d)\b',
            full_text, re.IGNORECASE
        )
        if year_priority_m:
            meta["year"] = int(year_priority_m.group(1))
        else:
            all_years = re.findall(r'\b(20[0-2]\d|19[89]\d)\b', full_text)
            if all_years:
                from collections import Counter
                most_common = Counter(all_years).most_common(1)[0][0]
                meta["year"] = int(most_common)

        # 标题：用 rawdict 找第一页最大字号的文本行
        blocks = doc[0].get_text("dict")["blocks"]
        candidates = []
        for b in blocks:
            for line in b.get("lines", []):
                line_text = "".join(s["text"] for s in line.get("spans", [])).strip()
                max_size  = max((s["size"] for s in line.get("spans", []) if s["text"].strip()), default=0)
                if len(line_text) > 5 and max_size > 0:
                    candidates.append((max_size, line_text))
        if candidates:
            candidates.sort(key=lambda x: -x[0])
            top_size = candidates[0][0]
            title_lines = [t for s, t in candidates if s >= top_size * 0.82][:4]
            meta["title"] = " ".join(title_lines)

        # ── 期刊名：从前2页页眉（页面顶部 10% 区域，小字）中间文本块提取 ──
        _journal_ban = re.compile(
            r'doi|http|www|©|copyright|vol\.|no\.|pp\.|page|\d{4}|\d+',
            re.IGNORECASE
        )
        for pi in range(min(2, len(doc))):
            page = doc[pi]
            h = page.rect.height
            w = page.rect.width
            header_rect = fitz.Rect(0, 0, w, h * 0.12)   # 页面顶部12%
            hblocks = page.get_text("dict", clip=header_rect)["blocks"]
            header_candidates = []
            for b in hblocks:
                for ln in b.get("lines", []):
                    txt = "".join(s["text"] for s in ln.get("spans", [])).strip()
                    sz  = max((s["size"] for s in ln.get("spans", []) if s["text"].strip()), default=0)
                    # 期刊名：适中字号（7-14pt）、不含数字/doi/http、长度合适
                    if (5 < len(txt) < 120 and 6 < sz < 15
                            and not _journal_ban.search(txt)):
                        # 取水平中心位置（x0+x1）/2，越靠近页面中央越可能是期刊名
                        cx = (b["bbox"][0] + b["bbox"][2]) / 2
                        dist_center = abs(cx - w / 2)
                        header_candidates.append((dist_center, sz, txt))
            if header_candidates:
                # 优先取最靠近水平中心的，次优字号最大的
                header_candidates.sort(key=lambda x: (x[0], -x[1]))
                meta["journal"] = header_candidates[0][2]
                break

        # ── 作者：先用 rawdict 按坐标找候选行，再过滤噪声 ──
        _inst_words = {
            '大学','学院','学校','研究院','研究所','中心','公司','机构',
            '作者','简介','基金','项目','摘要','关键词','收稿','审稿',
            '通讯','编辑','责任','北京','上海','南京','合肥','广州','深圳',
            '杭州','成都','武汉','西安','天津','重庆','省','市','区','县',
        }
        _cn_ban = re.compile(
            r'作者简介|通讯作者|基金|项目|摘要|关键词|收稿|审稿|编辑部'
            r'|大学|学院|学校|研究院|研究所|中心|公司'
            r'|E.?mail|http|doi|\d{5,}|@'
        )
        # 用 rawdict 逐行扫描，记录每行文字及其垂直位置
        page0_lines = []
        for b in doc[0].get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                txt = "".join(s["text"] for s in ln.get("spans", [])).strip()
                sz  = max((s["size"] for s in ln.get("spans", []) if s["text"].strip()), default=0)
                y0  = ln["bbox"][1]
                if txt:
                    page0_lines.append((y0, sz, txt))
        page0_lines.sort(key=lambda x: x[0])  # 按垂直位置排序

        # 中文论文：标题后的第一个「纯人名行」
        title_y = None
        for y0, sz, txt in page0_lines:
            if meta["title"] and meta["title"][:6] in txt:
                title_y = y0
                break
        if title_y is None and page0_lines:
            # 找最大字号行作为标题行基准
            biggest = max(page0_lines, key=lambda x: x[1])
            title_y = biggest[0]

        for y0, sz, txt in page0_lines:
            if title_y and y0 <= title_y:
                continue  # 跳过标题及之前的内容
            if len(txt) > 80:
                continue  # 太长的行不是纯作者行
            has_cn = bool(re.search(r'[\u4e00-\u9fff]', txt))
            has_en = bool(re.search(r'[A-Za-z]', txt))
            if has_cn and not _cn_ban.search(txt):
                # 提取 2-4 字中文片段，过滤机构词
                raw = re.findall(r'[\u4e00-\u9fff]{2,4}', txt)
                names = [n for n in raw if n not in _inst_words]
                # 名字应都是 2-3 字，且数量在 1-8 之间
                names = [n for n in names if len(n) <= 3]
                if 1 <= len(names) <= 8:
                    meta["authors_str"] = ", ".join(names)
                    break
            if not has_cn and has_en:
                # 英文作者行
                if any(kw in txt.lower() for kw in
                       ["abstract","journal","doi","university","department",
                        "press","©","institute","school","college","lab",
                        "editor","correspondence","email","http","received",
                        "accepted","published","volume","issue"]):
                    continue
                cleaned = re.sub(r'\b\d+\b', '', txt)
                cleaned = re.sub(r'[a-zA-Z0-9._%+\-]+@[^\s]+', '', cleaned)
                cleaned = re.sub(r'\([^)]*\)', '', cleaned)
                cleaned = re.sub(r'[∗*†‡§¶#,;]', ' ', cleaned)
                names = re.findall(r'[A-Z][a-z]+(?:[\s\-][A-Z][a-z]+)+', cleaned)
                if 1 <= len(names) <= 10:
                    meta["authors_str"] = ", ".join(names)
                    break

        # 摘要
        abs_m = re.search(
            r'[Aa]bstract[:\s]*(.{50,800}?)(?:\n\n|\Z|[Kk]eyword)',
            full_text, re.DOTALL
        )
        if abs_m:
            meta["abstract"] = abs_m.group(1).replace("\n", " ").strip()[:600]

        doc.close()
    except Exception:
        pass
    return meta


def _fetch_crossref(doi: str) -> dict | None:
    """通过 DOI 查 CrossRef，返回元数据 dict 或 None"""
    try:
        r = requests.get(
            f"https://api.crossref.org/works/{doi}",
            headers={"User-Agent": "Librarian/1.0"},
            timeout=8
        )
        if r.status_code != 200:
            return None
        data = r.json()["message"]
        authors = []
        for a in data.get("author", []):
            name = f"{a.get('given','')} {a.get('family','')}".strip()
            if name:
                authors.append(name)
        year = None
        for key in ("published-print", "published-online", "created"):
            if key in data:
                year = data[key]["date-parts"][0][0]
                break
        # 去掉 CrossRef abstract 里的 <jats:p> 标签
        abstract = re.sub(r'<[^>]+>', '', data.get("abstract", "")).strip()
        journal = data.get("container-title", [""])[0]
        title   = data.get("title", [""])[0]
        return {
            "title":       title,
            "authors_str": ", ".join(authors),
            "year":        year or 2024,
            "journal":     journal,
            "abstract":    abstract[:600],
        }
    except Exception:
        return None


# ─────────────────────────────────────────
# Session State
# ─────────────────────────────────────────
def _init():
    defaults = {
        "assistant": None,
        "agent_ready": False,
        "global_chat": [],
        "global_thread": "global_main",
        "paper_chats": {},
        "paper_threads": {},
        "active_paper": None,
        "search_query": "",
        # PDF 阅读器：待处理的划线队列（由 component 回调写入）
        "pending_highlight": None,
        # 每篇文献当前页码
        "pdf_pages": {},
        # Import 页上传的 PDF 路径（跳过 rerun 丢失问题）
        "imported_pdf_path": None,
        "imported_pdf_name": None,
        # Process 结果（跨 rerun 保留）
        "process_result": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
_init()


# ─────────────────────────────────────────
# 侧边栏
# ─────────────────────────────────────────
with st.sidebar:
    # ── 品牌 ──
    st.markdown("""
<div style='padding:24px 0 4px;'>
  <div style='font-size:1.05rem;font-weight:600;letter-spacing:.02em;color:#1a1a1a;'>Librarian</div>
  <div style='font-size:0.7rem;color:#999;margin-top:2px;letter-spacing:.03em;'>Academic Reference Manager</div>
</div>
""", unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown("<div style='border-top:1px solid #e4e2db;margin-bottom:20px;'></div>", unsafe_allow_html=True)

    # ── My Thesis ──
    st.markdown("<div style='font-size:0.68rem;color:#aaa;text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px;'>My Thesis</div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.7rem;color:#bbb;margin-bottom:10px;'>让 Agent 在分析时始终联系你的论文</div>", unsafe_allow_html=True)

    _thesis = get_my_thesis()

    # 已填写时显示摘要卡片
    if _thesis.get("title"):
        st.markdown(f"""
<div style='font-size:0.8rem;font-weight:500;color:#2a2520;line-height:1.4;margin-bottom:2px;'>{_thesis['title']}</div>
<div style='font-size:0.72rem;color:#888;font-style:italic;line-height:1.5;margin-bottom:10px;'>{_thesis.get('argument','')[:90]}{'…' if len(_thesis.get('argument',''))>90 else ''}</div>
""", unsafe_allow_html=True)

    with st.expander("Edit" if _thesis.get("title") else "＋ Add thesis", expanded=not bool(_thesis.get("title"))):
        _th_title = st.text_input(
            "Title", value=_thesis.get("title", ""), key="th_title",
            placeholder="e.g. Platform Governance and User Rights"
        )
        _th_arg = st.text_area(
            "Argument", value=_thesis.get("argument", ""), key="th_arg",
            placeholder="核心论点...",
            height=80
        )
        _th_kw = st.text_input(
            "Keywords", value=_thesis.get("keywords", ""), key="th_kw",
            placeholder="platform governance, content moderation..."
        )
        _th_outline = st.text_area(
            "Outline (optional)", value=_thesis.get("outline", ""), key="th_outline",
            placeholder="1. 引言  2. 理论框架  3. 案例分析  4. 结论",
            height=70
        )
        if st.button("Save", key="btn_save_thesis", type="primary", use_container_width=True):
            save_my_thesis(
                title=_th_title.strip(),
                argument=_th_arg.strip(),
                keywords=_th_kw.strip(),
                outline=_th_outline.strip(),
            )
            if st.session_state.agent_ready and st.session_state.assistant:
                st.session_state.assistant.refresh_thesis_context()
            st.rerun()

    st.markdown("<div style='height:1px'></div>", unsafe_allow_html=True)

    # ── AI Engine（底部，用空白撑开）──
    st.markdown("<div style='border-top:1px solid #e4e2db;margin:20px 0 12px;'></div>", unsafe_allow_html=True)

    if st.session_state.agent_ready:
        _cur_model = st.session_state.get("sel_model") or st.session_state.get("custom_model") or st.session_state.get("input_model") or ""
        _engine_label = f"● AI Engine"
    else:
        _engine_label = "○ AI Engine"

    with st.expander(_engine_label, expanded=not st.session_state.agent_ready):
        provider_keys = list(LLM_PROVIDERS.keys())
        provider_labels = [LLM_PROVIDERS[k]["label"] for k in provider_keys]
        selected_provider_label = st.selectbox(
            "Provider", provider_labels, label_visibility="collapsed",
            key="sel_provider"
        )
        provider = provider_keys[provider_labels.index(selected_provider_label)]

        models = LLM_PROVIDERS[provider]["models"]
        if provider == "custom":
            model = st.text_input("Model name", placeholder="model-name", label_visibility="collapsed", key="custom_model")
        elif models:
            model = st.selectbox("Model", models, label_visibility="collapsed", key="sel_model")
        else:
            model = st.text_input("Model", placeholder="输入模型名", label_visibility="collapsed", key="input_model")

        if "api_key_input" not in st.session_state:
            st.session_state.api_key_input = os.getenv("OPENAI_API_KEY", "")
        if "base_url_input" not in st.session_state:
            st.session_state.base_url_input = os.getenv("OPENAI_BASE_URL", "")

        st.text_input("API Key", label_visibility="collapsed", placeholder="API Key", key="api_key_input")
        st.text_input("Base URL", label_visibility="collapsed", placeholder="https://api.example.com/v1", key="base_url_input")

        agent_color = "#16a34a" if st.session_state.agent_ready else "#bbb"
        agent_status = "● Connected" if st.session_state.agent_ready else "○ Not connected"
        st.markdown(f"<div style='font-size:0.72rem;color:{agent_color};margin:4px 0 8px;'>{agent_status}</div>", unsafe_allow_html=True)

        if st.button("Connect", use_container_width=True, key="btn_connect"):
            _api_key = st.session_state.get("api_key_input", "")
            _base_url = st.session_state.get("base_url_input", "")
            if not _api_key and provider not in ("ollama",):
                st.error("请输入 API Key")
            elif not model:
                st.error("请输入模型名")
            else:
                with st.spinner("连接中..."):
                    try:
                        from agent import create_llm
                        test_llm = create_llm(
                            provider=provider, model=model,
                            api_key=_api_key if _api_key else None,
                            base_url=_base_url if _base_url else None,
                        )
                        test_llm.invoke("hi")
                        st.session_state.assistant = LiteratureAssistant(
                            provider=provider, model=model,
                            api_key=_api_key if _api_key else None,
                            base_url=_base_url if _base_url else None,
                        )
                        st.session_state.agent_ready = True
                        st.rerun()
                    except Exception as e:
                        st.session_state.agent_ready = False
                        st.session_state.assistant = None
                        err = str(e)
                        if "401" in err or "invalid_api_key" in err or "Incorrect API key" in err:
                            st.error("❌ API Key 无效")
                        elif "405" in err or "404" in err:
                            st.error("❌ Base URL 或模型名有误")
                        elif "connection" in err.lower() or "timeout" in err.lower():
                            st.error("❌ 网络连接失败")
                        else:
                            st.error(f"❌ {err}")

    # 已连接时 expander 外显示模型名
    if st.session_state.agent_ready:
        _cur_model = st.session_state.get("sel_model") or st.session_state.get("custom_model") or st.session_state.get("input_model") or ""
        st.markdown(
            f"<div style='font-size:0.7rem;color:#16a34a;margin:-2px 0 0;padding-left:2px;'>● {_cur_model}</div>",
            unsafe_allow_html=True
        )


# ─────────────────────────────────────────
# Notebook 全屏页面
# ─────────────────────────────────────────
def render_notebook():
    """
    当 st.session_state["notebook_open"] = paper_id 时，渲染仿真笔记全屏页面。
    使用 st.empty() + HTML overlay 模拟全屏覆盖（侧边栏仍存在，主内容区完全替换）。
    """
    import datetime
    pid = st.session_state.get("notebook_open")
    if not pid:
        return False  # 未激活

    paper = get_paper_by_id(pid)
    if not paper:
        st.session_state.pop("notebook_open", None)
        return False

    title   = paper.get("title") or "Untitled"
    authors = paper.get("authors") or []
    author_str = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
    year    = paper.get("year") or ""
    notes   = paper.get("notes") or ""

    # ── 顶栏 ──
    top_c1, top_c2, top_spacer = st.columns([2, 2, 8])
    with top_c1:
        if st.button("← Back", key="nb_back"):
            st.session_state.pop("notebook_open", None)
            st.rerun()
    with top_c2:
        if st.session_state.get("agent_ready"):
            if st.button("🔄 Regenerate", key="nb_regen"):
                with st.spinner("Generating..."):
                    try:
                        _nt = f"notes_{pid}_{int(time.time())}"
                        _msg = (
                            f"请为 paper_id={pid} 重新生成完整阅读笔记。\n"
                            "1. search_paper_content 多次检索：核心论点、研究背景、主要论证、关键概念、结论\n"
                            "2. get_paper_details 获取元数据\n"
                            "3. 生成 Markdown 笔记并调用 save_paper_notes 保存\n\n"
                            f"{st.session_state.assistant.NOTE_TEMPLATE}\n"
                            "  - {{abstract_summary}}：2-4句话核心主张\n"
                            "  - {{core_arguments}}：编号列表，至少3条\n"
                            "  - {{key_points}}：按节分块，每块2-4个观点\n"
                            "  - {{key_concepts}}：至少6组术语\n"
                            f"  - {{date}}：{datetime.date.today().strftime('%Y-%m-%d')}\n"
                        )
                        st.session_state.assistant.global_chat(_msg, _nt)
                    except Exception as _e:
                        st.error(str(_e))
                st.rerun()

    # ── 纸质页面 ──
    import markdown as _md
    if notes:
        notes_html = _md.markdown(notes, extensions=["tables", "fenced_code", "nl2br"])
    else:
        notes_html = """
<div class="notebook-empty">
  — 暂无笔记 —<br>
  <span style='font-size:0.78rem;'>点击上方 🔄 Regenerate 让 Agent 自动生成</span>
</div>
"""
    st.markdown(f"""
<div class="notebook-paper">
  <div class="notebook-title">{title}</div>
  <div style='font-size:0.75rem;color:#bbb;font-family:Inter,sans-serif;
              letter-spacing:.04em;margin-bottom:32px;'>{author_str}{"&ensp;·&ensp;" + str(year) if year else ""}</div>
  <div class="notebook-content">{notes_html}</div>
</div>
""", unsafe_allow_html=True)

    # 在笔记底部显示 Paper Agent 里待追加的内容（如有）
    pending_append = st.session_state.pop(f"nb_append_{pid}", None)
    if pending_append:
        import datetime
        appended = (notes.rstrip() + "\n\n---\n\n" +
                    f"*{datetime.date.today().strftime('%Y-%m-%d')} · Paper Agent*\n\n" +
                    pending_append)
        update_paper_notes(pid, appended)
        st.rerun()

    pending_new = st.session_state.pop(f"nb_new_{pid}", None)
    if pending_new:
        import datetime
        new_note = f"*{datetime.date.today().strftime('%Y-%m-%d')} · Paper Agent*\n\n{pending_new}"
        update_paper_notes(pid, new_note)
        st.rerun()

    return True  # 已渲染 notebook，主流程应跳过


# ─────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────
@st.dialog("Move to folder", width="small")
def _move_to_folder_dialog(paper_id: int, all_collections: list):
    """弹窗：选择目标 folder，支持加入/移出"""
    paper_colls = get_collections_for_paper(paper_id)
    paper_coll_ids = {c["id"] for c in paper_colls}

    if not all_collections:
        st.markdown("<div style='color:#aaa;font-size:0.88rem;'>No folders yet. Create one in Library.</div>", unsafe_allow_html=True)
        return

    st.markdown("<div style='font-size:0.82rem;color:#666;margin-bottom:14px;'>Select folders for this paper:</div>", unsafe_allow_html=True)

    for coll in all_collections:
        in_coll = coll["id"] in paper_coll_ids
        _mc1, _mc2 = st.columns([6, 2])
        with _mc1:
            _mark = "✓" if in_coll else "+"
            _color = "#5a8a5a" if in_coll else "#aaa"
            st.markdown(f"<div style='font-size:0.84rem;color:{_color};padding-top:8px;'>{_mark} {coll['name']}</div>", unsafe_allow_html=True)
        with _mc2:
            if in_coll:
                if st.button("Remove", key=f"dlg_rm_{paper_id}_{coll['id']}"):
                    remove_paper_from_collection(paper_id, coll["id"])
                    st.rerun()
            else:
                if st.button("Add", key=f"dlg_add_{paper_id}_{coll['id']}"):
                    add_paper_to_collection(paper_id, coll["id"])
                    st.rerun()


def render_paper_card(paper: dict, show_detail_btn: bool = True,
                      all_collections: list = None):
    """渲染一张文献卡片，右上角有 Move 按钮"""
    authors = paper.get("authors") or []
    author_str = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
    year = paper.get("year") or "n.d."
    journal = paper.get("journal") or ""
    highlights = get_highlights_by_paper(paper["id"])
    kws = paper.get("keywords") or []
    tags_html = "".join(f"<span class='tag-pill'>{k}</span>" for k in kws)

    # 所属 collections（小标签展示，不再用 expander）
    paper_colls = get_collections_for_paper(paper["id"])
    coll_html = ""
    if paper_colls:
        coll_html = " ".join(
            f"<span style='font-size:0.7rem;color:#c8a96e;background:#fdf8ef;"
            f"border:1px solid #e8dfc8;border-radius:4px;padding:1px 6px;margin-right:3px;'>"
            f"📁 {c['name']}</span>"
            for c in paper_colls
        )

    with st.container():
        # 卡片主体 + 右上角 Move 按钮同行
        _card_col, _move_col = st.columns([11, 1])
        with _card_col:
            st.markdown(f"""
<div class="lib-card">
  <div class="paper-title">{paper['title']}</div>
  <div class="paper-meta">{author_str} &nbsp;·&nbsp; {year}
  {("&nbsp;·&nbsp; <em>" + journal + "</em>") if journal else ""}
  &nbsp;·&nbsp; {len(highlights)} highlights
  </div>
  {f"<div style='margin-top:6px;'>{tags_html}</div>" if tags_html else ""}
  {f"<div style='margin-top:4px;'>{coll_html}</div>" if coll_html else ""}
</div>
""", unsafe_allow_html=True)
        with _move_col:
            # 右上角移动按钮，用小图标
            if all_collections is not None:
                st.markdown("<div style='padding-top:18px;'>", unsafe_allow_html=True)
                if st.button("⊞", key=f"move_btn_{paper['id']}", help="Move to folder"):
                    _move_to_folder_dialog(paper["id"], all_collections)
                st.markdown("</div>", unsafe_allow_html=True)

        if show_detail_btn:
            c1, c2, _sp = st.columns([2, 2, 8])
            with c1:
                if st.button("Open", key=f"open_{paper['id']}"):
                    st.session_state.active_paper = paper["id"]
                    st.session_state["_pending_nav"] = "Library"
                    st.rerun()
            with c2:
                if st.button("Delete", key=f"del_{paper['id']}"):
                    delete_paper(paper["id"])
                    if st.session_state.active_paper == paper["id"]:
                        st.session_state.active_paper = None
                    st.rerun()


def get_apa(paper: dict) -> str:
    if paper.get("citation_apa"):
        return paper["citation_apa"]
    result = generate_citation.invoke({"paper_id": paper["id"], "style": "apa"})
    data = json.loads(result)
    return data.get("citation", "") if data.get("success") else ""


# ─────────────────────────────────────────
# ── Notebook 全屏（优先级最高，拦截所有页面渲染）──
# ─────────────────────────────────────────
if st.session_state.get("notebook_open"):
    render_notebook()
    st.stop()

# ─────────────────────────────────────────
# ── 主 Tab 导航 ──
# ─────────────────────────────────────────
_TAB_NAMES = ["Library", "Agent"]
_TAB_DEFAULT = {"Library": 0, "Agent": 1}

if st.session_state.get("_pending_nav"):
    _pn = st.session_state.pop("_pending_nav")
    st.session_state["_pending_tab"] = _TAB_DEFAULT.get(_pn, 0)

_pending_tab = st.session_state.pop("_pending_tab", None)

tab_lib, tab_agent = st.tabs(_TAB_NAMES)

# ── Import 弹窗 ──────────────────────────
@st.dialog("Import Paper", width="large")
def _import_dialog():
    uploaded = st.file_uploader("Upload PDF file", type=["pdf"], label_visibility="collapsed", key="dlg_pdf_uploader")
    if uploaded:
        save_path = os.path.join(UPLOAD_DIR, uploaded.name)
        with open(save_path, "wb") as f:
            f.write(uploaded.getbuffer())
        st.session_state.dlg_pdf_path = save_path
        st.session_state.dlg_pdf_name = uploaded.name
        st.session_state.dlg_parsed_meta = _parse_pdf_meta(save_path)

    save_path = st.session_state.get("dlg_pdf_path")
    pdf_name  = st.session_state.get("dlg_pdf_name")

    proc_result = st.session_state.pop("dlg_proc_result", None)
    if proc_result:
        status, msg = proc_result
        if status == "ok":
            st.success("✅ 已添加到文献库")
        else:
            st.error(f"❌ {msg}")

    if save_path and os.path.exists(save_path):
        meta = st.session_state.get("dlg_parsed_meta") or {}
        if "dlg_qs_title" not in st.session_state or st.session_state.get("_dlg_for") != save_path:
            st.session_state["_dlg_for"]       = save_path
            st.session_state["dlg_qs_title"]   = meta.get("title") or os.path.splitext(pdf_name)[0].replace("_"," ").replace("-"," ")
            st.session_state["dlg_qs_authors"] = meta.get("authors_str", "")
            st.session_state["dlg_qs_year"]    = meta.get("year", 2024)
            st.session_state["dlg_qs_journal"] = meta.get("journal", "")
            st.session_state["dlg_qs_abstract"]= meta.get("abstract", "")

        st.markdown(f"<div style='font-size:0.8rem;color:#888;margin-bottom:12px;'>📄 {pdf_name}</div>", unsafe_allow_html=True)
        qs_title   = st.text_input("Title *",   value=st.session_state["dlg_qs_title"],   key="dlg_f_title")
        qs_authors = st.text_input("Authors",   value=st.session_state["dlg_qs_authors"], key="dlg_f_authors", placeholder="Author 1, Author 2")
        c1q, c2q   = st.columns(2)
        qs_year    = c1q.number_input("Year",   value=int(st.session_state["dlg_qs_year"] or 2024), min_value=1900, max_value=2100, key="dlg_f_year")
        qs_journal = c2q.text_input("Journal",  value=st.session_state["dlg_qs_journal"], key="dlg_f_journal")

        b1, b2 = st.columns(2)
        with b1:
            if st.button("Save to Library", type="primary", use_container_width=True, key="dlg_btn_save"):
                if qs_title.strip():
                    a_list = [a.strip() for a in qs_authors.split(",") if a.strip()]
                    try:
                        _doc = fitz.open(save_path)
                        full_text = "\n".join(p.get_text() for p in _doc)
                        _doc.close()
                    except Exception:
                        full_text = None
                    save_paper(title=qs_title.strip(), authors=a_list, year=int(qs_year),
                               journal=qs_journal.strip() or None, doi=None,
                               abstract=st.session_state.get("dlg_qs_abstract") or None,
                               keywords=[], file_path=save_path, full_text=full_text)
                    for k in ["dlg_pdf_path","dlg_pdf_name","dlg_parsed_meta","_dlg_for",
                               "dlg_qs_title","dlg_qs_authors","dlg_qs_year","dlg_qs_journal","dlg_qs_abstract"]:
                        st.session_state.pop(k, None)
                    st.rerun()
                else:
                    st.error("请输入标题")
        with b2:
            if st.session_state.agent_ready:
                if st.button("✦ Agent Process", use_container_width=True, key="dlg_btn_agent"):
                    with st.spinner("Agent 正在分析（30-60s）..."):
                        try:
                            st.session_state.assistant.process_pdf(save_path, st.session_state.global_thread)
                            st.session_state["dlg_proc_result"] = ("ok", "")
                            for k in ["dlg_pdf_path","dlg_pdf_name","dlg_parsed_meta","_dlg_for",
                                       "dlg_qs_title","dlg_qs_authors","dlg_qs_year","dlg_qs_journal","dlg_qs_abstract"]:
                                st.session_state.pop(k, None)
                        except Exception as e:
                            st.session_state["dlg_proc_result"] = ("err", str(e))
                    st.rerun()
    else:
        st.markdown("<div style='font-size:0.8rem;color:#aaa;margin-bottom:16px;'>或手动填写</div>", unsafe_allow_html=True)
        with st.form("dlg_no_pdf_form"):
            t2 = st.text_input("Title *")
            a2 = st.text_input("Authors", placeholder="Author 1, Author 2")
            c1, c2 = st.columns(2)
            y2 = c1.number_input("Year", 1900, 2100, 2024, key="dlg_y2")
            j2 = c2.text_input("Journal")
            ab2 = st.text_area("Abstract", height=80, key="dlg_abs2")
            kw2 = st.text_input("Keywords")
            if st.form_submit_button("Add to Library", type="primary"):
                if t2.strip():
                    save_paper(title=t2.strip(), authors=[a.strip() for a in a2.split(",") if a.strip()],
                               year=int(y2), journal=j2 or None, doi=None, abstract=ab2 or None,
                               keywords=[k.strip() for k in kw2.split(",") if k.strip()])
                    st.rerun()
                else:
                    st.error("请输入标题")

# ─────────────────────────────────────────
# ── Tab: Library ──
# ─────────────────────────────────────────
with tab_lib:
    if st.session_state.active_paper:
        # ──── 文献详情视图 ────
        paper = get_paper_by_id(st.session_state.active_paper)
        if not paper:
            st.session_state.active_paper = None
            st.rerun()

        back_col, _ = st.columns([1, 9])
        with back_col:
            if st.button("← Back"):
                st.session_state.active_paper = None
                st.rerun()

        authors = paper.get("authors") or []
        author_str = ", ".join(authors)
        year = paper.get("year") or "n.d."

        st.markdown(f"<div class='page-header'>{paper['title']}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='page-sub'>{author_str} · {year}{' · ' + paper['journal'] if paper.get('journal') else ''}</div>", unsafe_allow_html=True)

        pid = paper["id"]
        tab_read, tab_highlights, tab_cite, tab_info, tab_agent = st.tabs(
            ["Read", "Highlights", "Citations", "Info", "Paper Agent"]
        )

        # ── Tab: Read（PDF 阅读器 + 划线面板）──────────────────────
        with tab_read:
            has_pdf = paper.get("file_path") and os.path.exists(paper["file_path"])
            if not has_pdf:
                st.markdown("""
<div style='padding:40px 0;text-align:center;color:#aaa;font-size:0.88rem;'>
  No PDF file associated with this paper.<br>
  <span style='font-size:0.8rem;'>Go to Import to upload the PDF, or add this paper with a PDF file.</span>
</div>
""", unsafe_allow_html=True)
            else:
                # 左侧阅读器 + 右侧划线面板
                col_pdf, col_panel = st.columns([3, 1], gap="medium")

                with col_pdf:
                    # ── 处理来自阅读器的回调 ──
                    # 传入已保存的高亮列表，让 PDF 阅读器在对应页标黄显示
                    _saved_hls = get_highlights_by_paper(pid)
                    component_val = render_pdf_reader(paper["file_path"], pid,
                                                      saved_highlights=_saved_hls)

                    if component_val and isinstance(component_val, str):
                        try:
                            payload = json.loads(component_val)
                        except Exception:
                            payload = None

                        if payload and payload.get("action") == "highlight":
                            hl_text = payload.get("text", "").strip()
                            hl_page_num = payload.get("page", 1)
                            hl_ctx = payload.get("context", "")
                            # 去重：与上次相同的划线内容不重复处理
                            last_hl_key = f"last_hl_{pid}"
                            last_hl = st.session_state.get(last_hl_key)
                            if hl_text and hl_text != last_hl:
                                st.session_state[last_hl_key] = hl_text
                                # 清除组件返回值，防止下次 rerun 重复触发
                                comp_key = f"pdf_reader_{pid}"
                                if comp_key in st.session_state:
                                    del st.session_state[comp_key]
                                # 存入 pending，让右侧面板处理
                                st.session_state.pending_highlight = {
                                    "text": hl_text,
                                    "page": hl_page_num,
                                    "context": hl_ctx,
                                    "paper_id": pid,
                                }
                                st.rerun()

                with col_panel:
                    st.markdown("<div style='font-size:0.78rem;text-transform:uppercase;letter-spacing:.06em;color:#999;margin-bottom:12px;'>Highlights</div>", unsafe_allow_html=True)

                    # ── 待确认的新划线 ──
                    pending = st.session_state.get("pending_highlight")
                    if pending and pending.get("paper_id") == pid:
                        st.markdown("<div style='font-size:0.75rem;color:#c8a96e;margin-bottom:6px;font-weight:500;'>New selection</div>", unsafe_allow_html=True)
                        st.markdown(f"""
<div class="hl-card" style="border-left-color:#c8a96e;">
  <div class="hl-text">{pending['text'][:300]}</div>
  <div class="hl-meta">p.{pending['page']}</div>
</div>
""", unsafe_allow_html=True)

                        # Agent 自动处理 or 手动填 note
                        if st.session_state.agent_ready:
                            hl_note_auto = st.text_input(
                                "Note (optional)", key=f"hl_note_auto_{pid}",
                                placeholder="Add a note, or leave blank for Agent to analyze",
                                label_visibility="collapsed"
                            )
                            c_save, c_agent, c_discard = st.columns([2, 2, 1])
                            with c_save:
                                if st.button("Save", key=f"hl_save_{pid}", type="primary"):
                                    hid = save_highlight(
                                        paper_id=pid,
                                        content=pending["text"],
                                        page_number=pending["page"],
                                        context=pending["context"],
                                        note=hl_note_auto or None,
                                    )
                                    add_highlight_to_vector_db(hid, pending["text"], pid, paper["title"])
                                    st.session_state.pending_highlight = None
                                    st.session_state.pop(f"last_hl_{pid}", None)
                                    st.rerun()
                            with c_agent:
                                if st.button("✦ Ask Agent", key=f"hl_agent_{pid}"):
                                    # Agent 自动分析划线 + 联系 My Thesis 给出写作建议
                                    if pid not in st.session_state.paper_chats:
                                        st.session_state.paper_chats[pid] = []
                                    if pid not in st.session_state.paper_threads:
                                        st.session_state.paper_threads[pid] = f"paper_{pid}_{int(time.time())}"
                                    with st.spinner("Agent analyzing..."):
                                        try:
                                            resp = st.session_state.assistant.analyze_highlight_for_thesis(
                                                paper_id=pid,
                                                highlight_text=pending["text"],
                                                page=pending["page"],
                                                thread_id=st.session_state.paper_threads[pid],
                                            )
                                        except Exception as e:
                                            resp = f"Error: {e}"
                                    st.session_state.paper_chats[pid].append({"role": "user", "content": f'✦ 划线分析："{pending["text"][:80]}..."'})
                                    st.session_state.paper_chats[pid].append({"role": "agent", "content": resp})
                                    # 同时在 session_state 里缓存建议，供 Highlights tab 显示
                                    if "hl_suggestions" not in st.session_state:
                                        st.session_state.hl_suggestions = {}
                                    st.session_state.hl_suggestions[pending["text"][:60]] = resp
                                    st.session_state.pending_highlight = None
                                    st.session_state.pop(f"last_hl_{pid}", None)
                                    st.rerun()
                            with c_discard:
                                if st.button("✕", key=f"hl_discard_{pid}"):
                                    st.session_state.pending_highlight = None
                                    st.session_state.pop(f"last_hl_{pid}", None)
                                    st.rerun()
                        else:
                            hl_note_m = st.text_input("Note", key=f"hl_note_m_{pid}", label_visibility="collapsed", placeholder="Note...")
                            c_save, c_discard = st.columns([3, 1])
                            with c_save:
                                if st.button("Save", key=f"hl_save_m_{pid}", type="primary"):
                                    hid = save_highlight(
                                        paper_id=pid,
                                        content=pending["text"],
                                        page_number=pending["page"],
                                        context=pending["context"],
                                        note=hl_note_m or None,
                                    )
                                    add_highlight_to_vector_db(hid, pending["text"], pid, paper["title"])
                                    st.session_state.pending_highlight = None
                                    st.rerun()
                            with c_discard:
                                if st.button("✕", key=f"hl_discard_m_{pid}"):
                                    st.session_state.pending_highlight = None
                                    st.rerun()

                        st.markdown("<hr>", unsafe_allow_html=True)

                    # ── 已保存的划线列表（HTML 组件，卡片内含跳转/删除按钮）──
                    highlights = get_highlights_by_paper(pid)
                    hl_action = render_highlights_panel(highlights, pid)
                    if hl_action:
                        act = hl_action.get("action")
                        if act == "jump":
                            # 跳转到对应页（0-indexed）
                            st.session_state[f"pdf_page_{pid}"] = (hl_action.get("page") or 1) - 1
                            # 清除组件值防止重复触发
                            if f"hl_panel_{pid}" in st.session_state:
                                del st.session_state[f"hl_panel_{pid}"]
                            st.rerun()
                        elif act == "delete":
                            hid = hl_action.get("id")
                            if hid:
                                from database import get_db_connection
                                conn = get_db_connection()
                                conn.execute("DELETE FROM highlights WHERE id=?", (hid,))
                                conn.commit()
                                conn.close()
                                if f"hl_panel_{pid}" in st.session_state:
                                    del st.session_state[f"hl_panel_{pid}"]
                                st.rerun()

        # ── Tab: Highlights（汇总视图）──────────────────────────────
        with tab_highlights:
            highlights = get_highlights_by_paper(pid)
            _thesis_set = bool(get_my_thesis().get("argument") or get_my_thesis().get("title"))
            if not highlights:
                st.markdown("<div style='color:#aaa;padding:24px 0;font-size:0.88rem;'>No highlights yet. Open the Read tab and select text in the PDF.</div>", unsafe_allow_html=True)
            else:
                for h in highlights:
                    tags_html = "".join(f"<span class='tag-pill'>{t}</span>" for t in (h.get("tags") or []))
                    note_html = f"<div style='font-size:0.76rem;color:#888;margin-top:4px;'>💬 {h['note']}</div>" if h.get("note") else ""
                    suggestion = h.get("writing_suggestion") or ""
                    suggestion_html = ""
                    if suggestion:
                        suggestion_html = f"<div style='font-size:0.75rem;color:#7a6a3e;background:#fffde7;border-left:3px solid #c8a96e;padding:6px 10px;margin-top:6px;border-radius:0 4px 4px 0;white-space:pre-wrap;'><span style='font-weight:600;'>✦ Writing Suggestion</span><br>{suggestion[:400]}{'...' if len(suggestion)>400 else ''}</div>"
                    st.markdown(f"""
<div class="hl-card">
  <div class="hl-text">{h['content']}</div>
  <div class="hl-meta">p.{h['page_number'] or '?'} &nbsp;{tags_html}</div>
  {note_html}
  {suggestion_html}
</div>
""", unsafe_allow_html=True)
                    btn_col1, btn_col2, _ = st.columns([2, 2, 6])
                    with btn_col1:
                        cite_key = f"({authors[0].split()[-1] if authors else 'Unknown'}, {year})" if authors else f"({year})"
                        if st.button(f"Cite {cite_key}", key=f"cite_hl_{h['id']}"):
                            st.code(cite_key, language=None)
                    with btn_col2:
                        if _thesis_set and st.session_state.agent_ready:
                            if st.button("✦ Analyze", key=f"analyze_hl_{h['id']}"):
                                if pid not in st.session_state.paper_threads:
                                    st.session_state.paper_threads[pid] = f"paper_{pid}_{int(time.time())}"
                                with st.spinner("Analyzing..."):
                                    try:
                                        resp = st.session_state.assistant.analyze_highlight_for_thesis(
                                            paper_id=pid,
                                            highlight_text=h["content"],
                                            page=h.get("page_number", 1),
                                            thread_id=st.session_state.paper_threads[pid],
                                        )
                                        update_highlight_suggestion(h["id"], resp)
                                    except Exception as e:
                                        resp = f"Error: {e}"
                                st.rerun()

        # ── Tab: Citations ─────────────────────────────────────────
        with tab_cite:
            apa  = get_apa(paper)
            result_mla = generate_citation.invoke({"paper_id": pid, "style": "mla"})
            mla  = json.loads(result_mla).get("citation", "") if json.loads(result_mla).get("success") else ""
            result_bib = generate_citation.invoke({"paper_id": pid, "style": "bibtex"})
            bibtex = json.loads(result_bib).get("citation", "") if json.loads(result_bib).get("success") else ""

            if apa:
                st.markdown("**APA 7th**")
                st.markdown(f"<div class='cite-block'>{apa}</div>", unsafe_allow_html=True)
                st.code(apa, language=None)
            if mla:
                st.markdown("**MLA 9th**")
                st.markdown(f"<div class='cite-block'>{mla}</div>", unsafe_allow_html=True)
            if bibtex:
                st.markdown("**BibTeX**")
                st.code(bibtex, language="bibtex")

        # ── Tab: Info ──────────────────────────────────────────────
        with tab_info:
            # ── Notebook 入口 ───────────────────────────────────────
            _existing_notes = paper.get("notes") or ""
            st.markdown(
                "<div style='font-size:0.72rem;color:#aaa;text-transform:uppercase;"
                "letter-spacing:.1em;margin-bottom:12px;'>Notes</div>",
                unsafe_allow_html=True
            )
            _nb_c1, _nb_c2, _nb_c3, _ = st.columns([2, 2, 2, 4])
            with _nb_c1:
                _nb_label = "📓 Open Notebook" if _existing_notes else "📓 New Notebook"
                if st.button(_nb_label, key=f"open_nb_{pid}", use_container_width=True):
                    st.session_state["notebook_open"] = pid
                    st.rerun()
            with _nb_c2:
                if st.session_state.agent_ready:
                    if st.button("✦ Generate", key=f"gen_notes_info_{pid}", use_container_width=True):
                        with st.spinner("Generating..."):
                            import datetime
                            try:
                                _note_thread = f"notes_{pid}_{int(time.time())}"
                                _gen_msg = (
                                    f"请为 paper_id={pid} 生成完整阅读笔记。\n"
                                    "步骤：\n"
                                    "1. 调用 search_paper_content 多次（建议4-6次），分别检索：核心论点、研究背景、主要论证、关键概念定义、结论建议\n"
                                    "2. 调用 get_paper_details 获取元数据\n"
                                    "3. 生成以下 Markdown 格式的完整阅读笔记并调用 save_paper_notes(paper_id, notes) 保存：\n\n"
                                    f"{st.session_state.assistant.NOTE_TEMPLATE}\n"
                                    "填写说明：\n"
                                    "  - {abstract_summary}：2-4句话概括论文核心主张\n"
                                    "  - {core_arguments}：编号列表，每条1-2句话，至少3条\n"
                                    "  - {key_points}：按论文各节分块，每块写2-4个重点观点\n"
                                    "  - {key_concepts}：列出专业术语及中文含义，至少6组\n"
                                    f"  - {{date}}：{datetime.date.today().strftime('%Y-%m-%d')}\n"
                                )
                                st.session_state.assistant.global_chat(_gen_msg, _note_thread)
                            except Exception as _e:
                                st.error(f"生成失败：{_e}")
                        st.session_state["notebook_open"] = pid
                        st.rerun()
            with _nb_c3:
                if _existing_notes:
                    st.markdown(
                        "<div style='font-size:0.75rem;color:#aaa;padding-top:8px;'>已有笔记</div>",
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        "<div style='font-size:0.75rem;color:#bbb;padding-top:8px;'>— 暂无笔记 —</div>",
                        unsafe_allow_html=True
                    )

            st.markdown("<hr style='margin:16px 0;'>", unsafe_allow_html=True)

            col_l, col_r = st.columns([3, 2])
            with col_l:
                if paper.get("abstract"):
                    st.markdown("**Abstract**")
                    st.markdown(f"<div class='paper-abstract'>{paper['abstract']}</div>", unsafe_allow_html=True)
                    st.markdown("")

                # ── 关键词/标签管理 ──
                st.markdown("<div style='font-size:0.78rem;color:#999;text-transform:uppercase;letter-spacing:.06em;margin-top:8px;margin-bottom:8px;'>Tags & Keywords</div>", unsafe_allow_html=True)
                cur_kws = paper.get("keywords") or []

                # 显示当前标签，每个标签旁边有删除按钮
                if cur_kws:
                    cols_tags = st.columns(min(len(cur_kws), 4) + 1)
                    for ti, kw in enumerate(cur_kws):
                        col_idx = ti % 4
                        with cols_tags[col_idx]:
                            if st.button(f"✕ {kw}", key=f"rm_tag_{pid}_{ti}", help=f"Remove tag: {kw}"):
                                new_kws = [k for k in cur_kws if k != kw]
                                update_paper_keywords(pid, new_kws)
                                st.rerun()

                # 添加新标签
                _tag_key = f"new_tag_input_{pid}"
                # 建议已有标签供快速点选
                all_existing = get_all_keywords()
                suggestions = [k for k in all_existing if k not in cur_kws]

                add_col, btn_col = st.columns([4, 1])
                with add_col:
                    new_tag = st.text_input(
                        "Add tag", placeholder="Type a tag and press Add...",
                        label_visibility="collapsed", key=_tag_key
                    )
                with btn_col:
                    if st.button("Add", key=f"btn_add_tag_{pid}", type="primary"):
                        tag_val = st.session_state.get(_tag_key, "").strip()
                        if tag_val and tag_val not in cur_kws:
                            update_paper_keywords(pid, cur_kws + [tag_val])
                            st.rerun()

                # 快捷选已有标签
                if suggestions:
                    st.markdown("<div style='font-size:0.74rem;color:#aaa;margin-top:4px;margin-bottom:4px;'>Quick add:</div>", unsafe_allow_html=True)
                    # 用 columns 显示快捷按钮，每行最多 5 个
                    chunk_size = 5
                    for chunk_start in range(0, min(len(suggestions), 15), chunk_size):
                        chunk = suggestions[chunk_start:chunk_start + chunk_size]
                        tag_cols = st.columns(len(chunk))
                        for ci, sug in enumerate(chunk):
                            with tag_cols[ci]:
                                if st.button(f"+ {sug}", key=f"quick_tag_{pid}_{sug}"):
                                    update_paper_keywords(pid, cur_kws + [sug])
                                    st.rerun()

            with col_r:
                if paper.get("doi"):
                    st.markdown(f"**DOI** `{paper['doi']}`")
                if paper.get("file_path"):
                    st.markdown(f"**File** `{os.path.basename(paper['file_path'])}`")
                st.markdown(f"**Added** {paper.get('created_at', '')[:10]}")

        # ── Tab: Paper Agent ───────────────────────────────────────
        with tab_agent:
            if not st.session_state.agent_ready:
                st.markdown("<div style='color:#aaa;font-size:0.88rem;padding:16px 0;'>Connect an AI engine in the sidebar to use Paper Agent.</div>", unsafe_allow_html=True)
            else:
                if pid not in st.session_state.paper_chats:
                    st.session_state.paper_chats[pid] = []
                if pid not in st.session_state.paper_threads:
                    st.session_state.paper_threads[pid] = f"paper_{pid}_{int(time.time())}"

                st.markdown("<div style='font-size:0.82rem;color:#888;margin-bottom:12px;'>This agent specializes in this paper. Highlights you ask it to analyze are automatically saved.</div>", unsafe_allow_html=True)

                # 逐条渲染消息，agent 回复下方加保存按钮
                messages = st.session_state.paper_chats[pid]
                for m_idx, msg in enumerate(messages):
                    if msg["role"] == "user":
                        st.markdown(
                            f"<div style='display:flex;justify-content:flex-end;margin-bottom:4px;'>"
                            f"<div class='msg-user'>{msg['content']}</div></div>",
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            f"<div class='msg-agent' style='margin-bottom:4px;'>{msg['content']}</div>",
                            unsafe_allow_html=True
                        )
                        # 在每条 agent 回复下方显示保存按钮
                        _resp_text = msg["content"]
                        _existing_nb = get_paper_by_id(pid).get("notes") or ""
                        _bk1, _bk2, _bk3, _ = st.columns([2, 2, 2, 4])
                        with _bk1:
                            if st.button("📓 存为新笔记", key=f"nb_new_btn_{pid}_{m_idx}", use_container_width=True):
                                if _existing_nb:
                                    # 已有笔记 → 确认是否覆盖（用 session_state 做两步确认）
                                    st.session_state[f"nb_overwrite_confirm_{pid}_{m_idx}"] = True
                                    st.rerun()
                                else:
                                    import datetime
                                    new_note = f"*{datetime.date.today().strftime('%Y-%m-%d')} · Paper Agent*\n\n{_resp_text}"
                                    update_paper_notes(pid, new_note)
                                    st.session_state["notebook_open"] = pid
                                    st.rerun()
                        with _bk2:
                            if st.button("➕ 追加到笔记", key=f"nb_append_btn_{pid}_{m_idx}", use_container_width=True):
                                import datetime
                                appended = ((_existing_nb.rstrip() + "\n\n---\n\n") if _existing_nb else "") + \
                                           f"*{datetime.date.today().strftime('%Y-%m-%d')} · Paper Agent*\n\n{_resp_text}"
                                update_paper_notes(pid, appended)
                                st.session_state["notebook_open"] = pid
                                st.rerun()
                        with _bk3:
                            if st.button("📓 Open Notebook", key=f"nb_open_btn_{pid}_{m_idx}", use_container_width=True):
                                st.session_state["notebook_open"] = pid
                                st.rerun()
                        # 覆盖确认
                        if st.session_state.get(f"nb_overwrite_confirm_{pid}_{m_idx}"):
                            st.markdown(
                                "<div style='font-size:0.78rem;color:#c0392b;padding:4px 0;'>"
                                "⚠️ 已有笔记，确认覆盖？</div>",
                                unsafe_allow_html=True
                            )
                            _ov1, _ov2, _ = st.columns([2, 2, 6])
                            with _ov1:
                                if st.button("确认覆盖", key=f"nb_ov_yes_{pid}_{m_idx}", type="primary"):
                                    import datetime
                                    new_note = f"*{datetime.date.today().strftime('%Y-%m-%d')} · Paper Agent*\n\n{_resp_text}"
                                    update_paper_notes(pid, new_note)
                                    st.session_state.pop(f"nb_overwrite_confirm_{pid}_{m_idx}", None)
                                    st.session_state["notebook_open"] = pid
                                    st.rerun()
                            with _ov2:
                                if st.button("取消", key=f"nb_ov_no_{pid}_{m_idx}"):
                                    st.session_state.pop(f"nb_overwrite_confirm_{pid}_{m_idx}", None)
                                    st.rerun()
                        st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)

                user_in = st.chat_input("Ask about this paper...", key=f"paper_chat_{pid}")
                if user_in:
                    st.session_state.paper_chats[pid].append({"role": "user", "content": user_in})
                    with st.spinner(""):
                        try:
                            resp = st.session_state.assistant.paper_chat(
                                pid, user_in, st.session_state.paper_threads[pid]
                            )
                        except Exception as e:
                            resp = f"Error: {e}"
                    st.session_state.paper_chats[pid].append({"role": "agent", "content": resp})
                    st.rerun()

    else:
        # ──── 主页 / 文件夹 / 全库视图 ────
        # lib_view: "home" | "folder_{id}" | "all" | "agent"
        _lib_view = st.session_state.get("lib_view", "home")
        all_collections = get_all_collections()

        # ── 顶部工具栏 ──
        _tb1, _tb2, _tb3 = st.columns([5, 2, 1])
        with _tb1:
            _search_q = st.text_input("search", placeholder="Search papers...", label_visibility="collapsed", key="lib_search")
        with _tb2:
            _search_mode = st.radio(
                "sm", ["Title", "Semantic"],
                label_visibility="collapsed", horizontal=True, key="lib_search_mode"
            )
        with _tb3:
            if st.button("＋ Import", key="btn_open_import", use_container_width=True):
                _import_dialog()

        # 有搜索词时直接显示搜索结果，忽略视图层级
        if _search_q:
            if _search_mode == "Semantic":
                with st.spinner(""):
                    _sem = semantic_search_highlights(_search_q, 10)
                if _sem:
                    st.markdown(f"<div class='page-sub'>{len(_sem)} semantic matches for \"{_search_q}\"</div>", unsafe_allow_html=True)
                    for _r in _sem:
                        _pt = _r["metadata"].get("paper_title", "Unknown")
                        _sim = 1 - (_r.get("distance") or 0)
                        st.markdown(f"""<div class="hl-card"><div class="hl-text">{_r['content']}</div>
<div class="hl-meta">from <em>{_pt}</em> &nbsp;·&nbsp; {_sim:.0%} match</div></div>""", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='color:#aaa;font-size:0.88rem;padding:24px 0;'>No semantic matches found.</div>", unsafe_allow_html=True)
            else:
                _sr = search_papers(_search_q)
                st.markdown(f"<div class='page-sub'>{len(_sr)} results for \"{_search_q}\"</div>", unsafe_allow_html=True)
                for _sp in _sr:
                    render_paper_card(_sp, all_collections=all_collections)

        # ── 文件夹主页 ──────────────────────────────────────────────────
        elif _lib_view == "home":
            # 顶部：标题 + 新建文件夹
            _ht1, _ht2, _ht3 = st.columns([3, 3, 1])
            with _ht1:
                st.markdown("<div class='page-header' style='margin-bottom:20px;'>Library</div>", unsafe_allow_html=True)
            with _ht2:
                _nc_name = st.text_input("nf", placeholder="New folder name...", label_visibility="collapsed", key="new_coll_input")
            with _ht3:
                if st.button("New folder", key="btn_create_coll"):
                    _nc = st.session_state.get("new_coll_input", "").strip()
                    if _nc:
                        try:
                            create_collection(_nc)
                            st.rerun()
                        except Exception:
                            st.error("已存在")

            # 文件夹网格（3 列）
            _all_papers_count = len(get_all_papers())
            _all_hl_count = len(get_all_highlights())

            # 固定卡片：All Papers + Agent
            _COLS = 3
            _cards = []  # 每项: (icon, name, meta, click_view, is_special)
            _cards.append(("📚", "All Papers", f"{_all_papers_count} papers · {_all_hl_count} highlights", "all", False))
            for _c in all_collections:
                _cards.append(("📁", _c["name"], f"{_c['paper_count']} papers", f"folder_{_c['id']}", False))

            # 渲染网格
            for _row_start in range(0, len(_cards), _COLS):
                _row_cards = _cards[_row_start:_row_start + _COLS]
                _gcols = st.columns(_COLS)
                for _ci, (_icon, _cname, _cmeta, _cview, _is_special) in enumerate(_row_cards):
                    with _gcols[_ci]:
                        _border_color = "#1a1a1a" if _is_special else "#e8e8e4"
                        _bg = "#1a1a1a" if _is_special else "#fff"
                        _fg = "#fff" if _is_special else "#1a1a1a"
                        _fg_meta = "#999" if _is_special else "#aaa"
                        st.markdown(f"""
<div class='folder-card' style='background:{_bg};border-color:{_border_color};'>
  <div class='folder-card-icon'>{_icon}</div>
  <div class='folder-card-name' style='color:{_fg};'>{_cname}</div>
  <div class='folder-card-meta' style='color:{_fg_meta};'>{_cmeta}</div>
</div>""", unsafe_allow_html=True)
                        if st.button("Open", key=f"open_view_{_cview}", use_container_width=True):
                            st.session_state["lib_view"] = _cview
                            st.rerun()
                        # 文件夹删除按钮
                        if _cview.startswith("folder_"):
                            _fid_del = int(_cview.split("_")[1])
                            if st.button("Delete folder", key=f"del_coll_{_fid_del}"):
                                delete_collection(_fid_del)
                                st.rerun()

        # ── 文件夹内视图 ────────────────────────────────────────────────
        elif _lib_view.startswith("folder_"):
            _fid = int(_lib_view.split("_")[1])
            _cur_coll = next((c for c in all_collections if c["id"] == _fid), None)
            if not _cur_coll:
                st.session_state["lib_view"] = "home"
                st.rerun()
            else:
                # 面包屑
                _bc1, _bc2 = st.columns([1, 8])
                with _bc1:
                    if st.button("← Back", key="back_to_home"):
                        st.session_state["lib_view"] = "home"
                        st.rerun()
                with _bc2:
                    st.markdown(f"<div style='font-size:0.8rem;color:#aaa;padding-top:10px;'>Library / {_cur_coll['name']}</div>", unsafe_allow_html=True)

                # 文件夹标题
                st.markdown(f"<div class='page-header'>{_cur_coll['name']}</div>", unsafe_allow_html=True)

                # 文件夹内论文和 tag
                _fp_list = get_papers_in_collection(_fid)
                _f_all_kws = sorted({t for p in _fp_list for t in (p.get("keywords") or [])})
                _f_active_tags = st.session_state.get(f"_ftag_{_fid}", [])

                # Tag pills（st.pills 原生多选）
                if _f_all_kws:
                    _f_sel = st.pills(
                        "Filter by tag", _f_all_kws,
                        selection_mode="multi",
                        key=f"fpills_{_fid}",
                        label_visibility="collapsed",
                    )
                    _f_active_tags = list(_f_sel) if _f_sel else []
                    st.session_state[f"_ftag_{_fid}"] = _f_active_tags

                # 按 tag 过滤
                _fdisplay = _fp_list
                if _f_active_tags:
                    _fdisplay = [p for p in _fp_list if any(t in (p.get("keywords") or []) for t in _f_active_tags)]

                _ftotal = len(_fdisplay)
                if _f_active_tags:
                    _ts = ", ".join(f"#{t}" for t in _f_active_tags)
                    st.markdown(f"<div class='page-sub'>{_ftotal} papers tagged {_ts}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='page-sub'>{_ftotal} papers in this folder</div>", unsafe_allow_html=True)

                if not _fdisplay:
                    st.markdown("<div style='text-align:center;padding:48px 0;color:#aaa;'><div style='font-size:0.95rem;margin-bottom:6px;color:#777;'>No papers in this folder yet.</div><div style='font-size:0.82rem;'>Add papers from All Papers view.</div></div>", unsafe_allow_html=True)
                else:
                    for _fp in _fdisplay:
                        render_paper_card(_fp, all_collections=all_collections)

                # ── Folder Agent 入口 ────────────────────────────────────
                st.markdown("<div style='border-top:1px solid #e8e8e4;margin:28px 0 18px;'></div>", unsafe_allow_html=True)
                _fa_title = f"✦ Agent · {_cur_coll['name']}"
                st.markdown(f"<div style='font-size:0.92rem;font-weight:500;color:#1a1a1a;margin-bottom:4px;'>{_fa_title}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:0.78rem;color:#aaa;margin-bottom:14px;'>AI assistant scoped to {_cur_coll['paper_count']} papers in this folder</div>", unsafe_allow_html=True)

                if not st.session_state.agent_ready:
                    st.markdown("<div style='font-size:0.82rem;color:#aaa;padding:8px 0;'>Connect AI engine in the sidebar to use agent.</div>", unsafe_allow_html=True)
                else:
                    _folder_chat_key = f"_folder_chat_{_fid}"
                    _folder_thread_key = f"_folder_thread_{_fid}"
                    if _folder_chat_key not in st.session_state:
                        st.session_state[_folder_chat_key] = []
                    if _folder_thread_key not in st.session_state:
                        st.session_state[_folder_thread_key] = f"folder_{_fid}_{int(time.time())}"

                    # 构造 folder-scoped 的系统上下文
                    _fp_titles = [p.get('title','') for p in _fp_list]
                    _folder_ctx = f"You are a research assistant. Focus ONLY on the {len(_fp_list)} papers in the folder '{_cur_coll['name']}': {', '.join(_fp_titles[:10])}{'...' if len(_fp_titles)>10 else ''}. Use your tools to retrieve details."

                    # 快捷提示
                    _fqa1, _fqa2 = st.columns(2)
                    with _fqa1:
                        if st.button(f"✦ 概述本 folder 文献", key=f"fqa_overview_{_fid}", use_container_width=True):
                            _fq = f"请概述 folder '{_cur_coll['name']}' 中所有文献的核心主张和相互关系。"
                            st.session_state[_folder_chat_key].append({"role": "user", "content": _fq})
                            with st.spinner(""):
                                try:
                                    _fr = st.session_state.assistant.global_chat(_folder_ctx + "\n\n" + _fq, st.session_state[_folder_thread_key])
                                except Exception as _e:
                                    _fr = f"Error: {_e}"
                            st.session_state[_folder_chat_key].append({"role": "agent", "content": _fr})
                            st.rerun()
                    with _fqa2:
                        if st.button(f"✦ 找共同论点", key=f"fqa_common_{_fid}", use_container_width=True):
                            _fq = f"分析 folder '{_cur_coll['name']}' 中各文献的共同论点和分歧点。"
                            st.session_state[_folder_chat_key].append({"role": "user", "content": _fq})
                            with st.spinner(""):
                                try:
                                    _fr = st.session_state.assistant.global_chat(_folder_ctx + "\n\n" + _fq, st.session_state[_folder_thread_key])
                                except Exception as _e:
                                    _fr = f"Error: {_e}"
                            st.session_state[_folder_chat_key].append({"role": "agent", "content": _fr})
                            st.rerun()

                    # 对话历史
                    if st.session_state[_folder_chat_key]:
                        _fch = "<div class='msg-wrap'>"
                        for _fm in st.session_state[_folder_chat_key]:
                            if _fm["role"] == "user":
                                _fch += f"<div style='display:flex;justify-content:flex-end;'><div class='msg-user'>{_fm['content']}</div></div>"
                            else:
                                _fch += f"<div class='msg-agent'>{_fm['content']}</div>"
                        _fch += "</div>"
                        st.markdown(_fch, unsafe_allow_html=True)
                        _fc_clear, _ = st.columns([1, 7])
                        with _fc_clear:
                            if st.button("Clear", key=f"fclear_{_fid}"):
                                st.session_state[_folder_chat_key] = []
                                st.session_state[_folder_thread_key] = f"folder_{_fid}_{int(time.time())}"
                                st.rerun()

                    _folder_input = st.chat_input(f"Ask about papers in '{_cur_coll['name']}'...", key=f"fchat_input_{_fid}")
                    if _folder_input:
                        st.session_state[_folder_chat_key].append({"role": "user", "content": _folder_input})
                        with st.spinner(""):
                            try:
                                _fr = st.session_state.assistant.global_chat(_folder_ctx + "\n\n" + _folder_input, st.session_state[_folder_thread_key])
                            except Exception as _e:
                                _fr = f"Error: {_e}"
                        st.session_state[_folder_chat_key].append({"role": "agent", "content": _fr})
                        st.rerun()

        # ── All Papers 视图 ─────────────────────────────────────────────
        elif _lib_view == "all":
            # 面包屑
            if st.button("← Back", key="back_from_all"):
                st.session_state["lib_view"] = "home"
                st.rerun()

            st.markdown("<div class='page-header'>All Papers</div>", unsafe_allow_html=True)

            # Tag pill 筛选（st.pills 原生多选）
            all_kws = get_all_keywords()
            _active_tags = st.session_state.get("_lib_active_tags", [])
            if all_kws:
                _sel_tags = st.pills(
                    "Filter by tag", all_kws,
                    selection_mode="multi",
                    key="gtag_pills",
                    label_visibility="collapsed",
                )
                _active_tags = list(_sel_tags) if _sel_tags else []
                st.session_state["_lib_active_tags"] = _active_tags

            papers = get_all_papers()
            if _active_tags:
                papers = [p for p in papers if any(t in (p.get("keywords") or []) for t in _active_tags)]

            total = len(papers)
            if _active_tags:
                tag_str = ", ".join(f"#{t}" for t in _active_tags)
                st.markdown(f"<div class='page-sub'>{total} papers tagged {tag_str}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='page-sub'>{total} papers in your library</div>", unsafe_allow_html=True)

            if not papers:
                st.markdown("""
<div style='text-align:center;padding:60px 0;color:#aaa;'>
  <div style='font-size:2rem;margin-bottom:12px;'>⬜</div>
  <div style='font-size:0.95rem;margin-bottom:6px;color:#777;'>Your library is empty</div>
  <div style='font-size:0.82rem;'>Click ＋ Import to add your first paper</div>
</div>""", unsafe_allow_html=True)
            else:
                for paper in papers:
                    render_paper_card(paper, all_collections=all_collections)




# ─────────────────────────────────────────
# ── Tab: Agent ──
# ─────────────────────────────────────────
with tab_agent:
    st.markdown("<div class='page-header'>Global Agent</div>", unsafe_allow_html=True)
    st.markdown("<div class='page-sub'>Ask anything about your entire library — cross-paper analysis, citation generation, semantic search.</div>", unsafe_allow_html=True)

    if not st.session_state.agent_ready:
        st.markdown("""
<div style='background:#fafaf9;border:1px solid #e8e8e4;border-radius:8px;padding:32px;text-align:center;'>
  <div style='font-size:0.9rem;color:#777;margin-bottom:8px;'>No AI engine connected</div>
  <div style='font-size:0.82rem;color:#aaa;'>Configure your API key in the sidebar and click Connect.</div>
</div>
""", unsafe_allow_html=True)
        # 提示示例
        st.markdown("")
        st.markdown("**What you can ask:**")
        examples = [
            "Process /path/to/paper.pdf and save it to my library",
            "List all papers about content moderation",
            "Find my highlights about platform liability",
            "Generate APA citation for paper #1",
            "Compare the arguments in papers #1 and #2",
        ]
        for ex in examples:
            st.markdown(f"<div style='font-size:0.82rem;color:#888;padding:4px 0;'>· {ex}</div>", unsafe_allow_html=True)
    else:
        # ── 快捷指令面板 ────────────────────────────────────────────
        _ga_thesis = get_my_thesis()
        _thesis_ready = bool(_ga_thesis.get("argument") or _ga_thesis.get("title"))
        _all_colls = get_all_collections()

        # ── Quick Prompts（始终展示，分组排列）──────────────────────
        def _send_quick_prompt(prompt_text: str):
            st.session_state.global_chat.append({"role": "user", "content": prompt_text})
            with st.spinner(""):
                try:
                    resp = st.session_state.assistant.global_chat(
                        prompt_text, st.session_state.global_thread
                    )
                except Exception as e:
                    resp = f"Error: {e}"
            st.session_state.global_chat.append({"role": "agent", "content": resp})
            st.rerun()

        # ── 研究方向建议（始终可用）──
        st.markdown(
            "<div style='font-size:0.72rem;color:#aaa;text-transform:uppercase;letter-spacing:.1em;margin-bottom:10px;'>Discover</div>",
            unsafe_allow_html=True
        )
        _disc_c1, _disc_c2 = st.columns(2)
        with _disc_c1:
            if st.button("✦ 研究方向建议", key="qp_directions", use_container_width=True):
                _direction_prompt = (
                    "请分析我的整个文献库，为我提出 3-5 个可行的研究方向或论文选题。\n\n"
                    "步骤：\n"
                    "1. 调用 list_all_papers 获取文献列表\n"
                    "2. 对每篇论文调用 search_paper_content 检索核心主张、研究缺口、未来方向\n"
                    "3. 综合分析后，按以下格式输出每个方向：\n\n"
                    "### 方向N：[具体题目]\n"
                    "**核心问题**：这个方向要回答什么问题？\n"
                    "**可用文献**：列出2-3篇文库中可直接支撑的文献\n"
                    "**研究缺口**：现有文献没有回答什么？你的研究如何填补？\n"
                    "**难度评估**：★☆☆ 入门 / ★★☆ 中等 / ★★★ 挑战\n\n"
                    "优先推荐：文献交叉点丰富、具有比较视角（如中美/欧美）、或有明显理论空白的方向。"
                )
                _send_quick_prompt(_direction_prompt)
        with _disc_c2:
            if st.button("✦ 文献脉络梳理", key="qp_lineage", use_container_width=True):
                _lineage_prompt = (
                    "请梳理我文献库中所有论文的学术谱系：\n\n"
                    "1. 调用 list_all_papers 列出所有文献\n"
                    "2. 识别它们之间的理论传承、对话或批判关系\n"
                    "3. 输出：\n"
                    "   - **核心争论轴**：文献库中最主要的几组理论分歧\n"
                    "   - **谱系图（文字版）**：A → B（批判）→ C（回应）这样的关系链\n"
                    "   - **空白地带**：哪些问题还没有文献覆盖？"
                )
                _send_quick_prompt(_lineage_prompt)

        if _thesis_ready or _all_colls:
            st.markdown(
                "<div style='font-size:0.72rem;color:#aaa;text-transform:uppercase;letter-spacing:.1em;margin:14px 0 10px;'>Write</div>",
                unsafe_allow_html=True
            )

            write_prompts = []
            if _thesis_ready:
                _t_arg = _ga_thesis.get("argument") or _ga_thesis.get("title", "")
                write_prompts += [
                    ("🔍 找支撑材料",      f'请在我的所有划线中，语义搜索与以下论点最相关的内容：\n"{_t_arg[:200]}"\n\n列出最相关的5条划线，并说明每条如何支撑这个论点。'),
                    ("📝 生成综述草稿",    f'基于我的文献库和划线，为以下论点生成一段文献综述草稿（300-500字，引用具体文献）：\n"{_t_arg[:200]}"'),
                    ("🗂️ 整理论证结构",   f'分析我文献库中所有文献和划线，为以下论点构建一个三层论证结构（主论点→支撑论点→证据）：\n"{_t_arg[:200]}"'),
                    ("⚖️ 找反驳观点",      f'在我的文献库中，找出可能与以下论点产生张力或反驳关系的观点和划线：\n"{_t_arg[:200]}"'),
                ]

            if _all_colls:
                for coll in _all_colls[:3]:
                    write_prompts.append((
                        f"📁 分析「{coll['name']}」",
                        f"请分析 Collection「{coll['name']}」中的所有文献，梳理它们的核心观点和研究脉络，指出文献之间的联系和分歧。"
                    ))

            for i in range(0, len(write_prompts), 2):
                row_cols = st.columns(2)
                for j, (label, prompt_text) in enumerate(write_prompts[i:i+2]):
                    with row_cols[j]:
                        if st.button(label, key=f"qp_w_{i+j}", use_container_width=True):
                            _send_quick_prompt(prompt_text)

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        # 对话历史
        if st.session_state.global_chat:
            chat_html = "<div class='msg-wrap'>"
            for msg in st.session_state.global_chat:
                if msg["role"] == "user":
                    chat_html += f"<div style='display:flex;justify-content:flex-end;'><div class='msg-user'>{msg['content']}</div></div>"
                else:
                    chat_html += f"<div class='msg-agent'>{msg['content']}</div>"
            chat_html += "</div>"
            st.markdown(chat_html, unsafe_allow_html=True)

            c_clear, _ = st.columns([1, 7])
            with c_clear:
                if st.button("Clear", key="clear_global"):
                    st.session_state.global_chat = []
                    st.session_state.global_thread = f"global_{int(time.time())}"
                    st.rerun()
        else:
            # 空状态提示
            st.markdown("""
<div style='padding:24px 0;color:#aaa;font-size:0.85rem;'>
  <div style='margin-bottom:8px;color:#666;'>Ask the global agent:</div>
  <div style='padding:3px 0;'>· Process /path/to/paper.pdf</div>
  <div style='padding:3px 0;'>· Find my highlights about platform liability</div>
  <div style='padding:3px 0;'>· Generate APA for paper #1</div>
</div>
""", unsafe_allow_html=True)

        user_in = st.chat_input("Ask the global agent...", key="global_chat_input")
        if user_in:
            st.session_state.global_chat.append({"role": "user", "content": user_in})
            with st.spinner(""):
                try:
                    resp = st.session_state.assistant.global_chat(
                        user_in, st.session_state.global_thread
                    )
                except Exception as e:
                    resp = f"Error: {e}"
            st.session_state.global_chat.append({"role": "agent", "content": resp})
            st.rerun()





