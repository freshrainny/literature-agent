"""
工具层 - LangChain Tools
Agent 可以调用这些工具来完成各种文献管理任务
"""

import os
import json
import re
import fitz  # PyMuPDF
import requests
from langchain_core.tools import tool
from database import (
    save_paper, save_highlight, get_all_papers, get_paper_by_id,
    search_papers, get_highlights_by_paper, update_citations,
    add_highlight_to_vector_db, semantic_search_highlights, init_database,
    index_paper_chunks, search_paper_chunks, has_paper_chunks,
    update_paper_notes
)


# ─────────────────────────────────────────
# 工具1：解析 PDF 文件
# ─────────────────────────────────────────

@tool
def parse_pdf_file(file_path: str) -> str:
    """
    解析本地 PDF 文件，提取全文文本内容。
    输入：PDF 文件的本地路径
    输出：包含页码的文本内容
    """
    try:
        doc = fitz.open(file_path)
        pages_text = []
        for i, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            if text:
                pages_text.append(f"[第{i}页]\n{text}")
        doc.close()
        full_text = "\n\n".join(pages_text)
        # 返回前3000字符供 Agent 分析，完整文本存数据库
        preview = full_text[:3000] + "...(截断，完整内容已提取)" if len(full_text) > 3000 else full_text
        return json.dumps({
            "success": True,
            "total_pages": len(pages_text),
            "full_text": full_text,
            "preview": preview
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
def extract_pdf_highlights(file_path: str) -> str:
    """
    提取 PDF 中已有的高亮/注释内容（如用 PDF 阅读器标注过的内容）。
    输入：PDF 文件路径
    输出：高亮文字列表（含页码）
    """
    try:
        doc = fitz.open(file_path)
        highlights = []
        for page_num, page in enumerate(doc, start=1):
            for annot in page.annots():
                if annot.type[0] in [8, 9, 10]:  # 高亮、下划线、波浪线
                    # 获取高亮区域的文字
                    rect = annot.rect
                    words = page.get_text("words")
                    highlighted_words = []
                    for word in words:
                        word_rect = fitz.Rect(word[:4])
                        if rect.intersects(word_rect):
                            highlighted_words.append(word[4])
                    if highlighted_words:
                        highlights.append({
                            "page": page_num,
                            "text": " ".join(highlighted_words),
                            "color": str(annot.colors)
                        })
        doc.close()
        return json.dumps({
            "success": True,
            "highlights": highlights,
            "count": len(highlights)
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# ─────────────────────────────────────────
# 工具2：通过 DOI 或标题获取元数据
# ─────────────────────────────────────────

@tool
def fetch_metadata_by_doi(doi: str) -> str:
    """
    通过 DOI 从 CrossRef API 获取文献元数据（标题、作者、期刊、年份等）。
    输入：DOI 字符串，如 "10.1000/xyz123"
    输出：文献元数据 JSON
    """
    try:
        url = f"https://api.crossref.org/works/{doi}"
        headers = {"User-Agent": "LiteratureAgent/1.0 (mailto:user@example.com)"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()["message"]
            authors = []
            for author in data.get("author", []):
                name = f"{author.get('given', '')} {author.get('family', '')}".strip()
                authors.append(name)
            year = None
            if "published-print" in data:
                year = data["published-print"]["date-parts"][0][0]
            elif "published-online" in data:
                year = data["published-online"]["date-parts"][0][0]
            return json.dumps({
                "success": True,
                "title": data.get("title", [""])[0],
                "authors": authors,
                "year": year,
                "journal": data.get("container-title", [""])[0],
                "doi": doi,
                "abstract": data.get("abstract", ""),
                "publisher": data.get("publisher", "")
            }, ensure_ascii=False)
        else:
            return json.dumps({"success": False, "error": f"HTTP {response.status_code}"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
def search_paper_by_title(title: str) -> str:
    """
    通过标题在 CrossRef 搜索文献，获取 DOI 和元数据。
    输入：论文标题（英文效果最好）
    输出：匹配度最高的前3条结果
    """
    try:
        url = "https://api.crossref.org/works"
        params = {
            "query.title": title,
            "rows": 3,
            "select": "DOI,title,author,published-print,published-online,container-title,abstract"
        }
        headers = {"User-Agent": "LiteratureAgent/1.0"}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            items = response.json()["message"]["items"]
            results = []
            for item in items:
                authors = []
                for a in item.get("author", []):
                    authors.append(f"{a.get('given', '')} {a.get('family', '')}".strip())
                year = None
                if "published-print" in item:
                    year = item["published-print"]["date-parts"][0][0]
                elif "published-online" in item:
                    year = item["published-online"]["date-parts"][0][0]
                results.append({
                    "title": item.get("title", [""])[0],
                    "authors": authors,
                    "year": year,
                    "journal": item.get("container-title", [""])[0],
                    "doi": item.get("DOI", ""),
                    "abstract": item.get("abstract", "")[:200] + "..." if item.get("abstract", "") else ""
                })
            return json.dumps({"success": True, "results": results}, ensure_ascii=False)
        else:
            return json.dumps({"success": False, "error": f"HTTP {response.status_code}"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# ─────────────────────────────────────────
# 工具3：存储文献
# ─────────────────────────────────────────

@tool
def save_paper_to_db(title: str, authors_json: str, year: int = None,
                     journal: str = None, doi: str = None,
                     abstract: str = None, keywords_json: str = None,
                     file_path: str = None, full_text: str = None) -> str:
    """
    将文献信息保存到数据库。
    输入：文献各字段信息。authors_json 和 keywords_json 为 JSON 数组字符串，如 '["张三", "李四"]'
    输出：保存成功的 paper_id
    """
    try:
        authors = json.loads(authors_json) if authors_json else []
        keywords = json.loads(keywords_json) if keywords_json else []
        paper_id = save_paper(
            title=title, authors=authors, year=year,
            journal=journal, doi=doi, abstract=abstract,
            keywords=keywords, file_path=file_path, full_text=full_text
        )
        return json.dumps({"success": True, "paper_id": paper_id,
                           "message": f"文献「{title}」已保存，ID={paper_id}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
def save_highlight_to_db(paper_id: int, content: str, page_number: int = None,
                          context: str = None, note: str = None,
                          tags_json: str = None) -> str:
    """
    保存划线/高亮内容到数据库，同时加入向量库以支持语义搜索。
    输入：paper_id（文献ID）、content（划线文字）、page_number（页码）、note（备注）
    输出：保存结果
    """
    try:
        tags = json.loads(tags_json) if tags_json else []
        highlight_id = save_highlight(
            paper_id=paper_id, content=content,
            page_number=page_number, context=context,
            note=note, tags=tags
        )
        # 同步到向量数据库
        paper = get_paper_by_id(paper_id)
        paper_title = paper["title"] if paper else "未知文献"
        add_highlight_to_vector_db(highlight_id, content, paper_id, paper_title)

        return json.dumps({"success": True, "highlight_id": highlight_id,
                           "message": f"划线已保存（ID={highlight_id}）"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# ─────────────────────────────────────────
# 工具4：引用生成
# ─────────────────────────────────────────

@tool
def generate_citation(paper_id: int, style: str = "apa") -> str:
    """
    为指定文献生成引用格式。
    输入：paper_id（文献ID），style（引用格式：apa / mla / bibtex）
    输出：格式化的引用字符串
    """
    try:
        paper = get_paper_by_id(paper_id)
        if not paper:
            return json.dumps({"success": False, "error": f"未找到 ID={paper_id} 的文献"})

        title = paper["title"] or "Unknown Title"
        authors = paper["authors"] or []
        year = paper["year"] or "n.d."
        journal = paper["journal"] or ""
        doi = paper["doi"] or ""

        style = style.lower()

        if style == "apa":
            citation = _format_apa(authors, year, title, journal, doi)
        elif style == "mla":
            citation = _format_mla(authors, title, journal, year)
        elif style == "bibtex":
            citation = _format_bibtex(paper_id, authors, year, title, journal, doi)
        else:
            citation = _format_apa(authors, year, title, journal, doi)

        # 保存引用到数据库
        apa = _format_apa(authors, year, title, journal, doi)
        mla = _format_mla(authors, title, journal, year)
        bibtex = _format_bibtex(paper_id, authors, year, title, journal, doi)
        update_citations(paper_id, apa=apa, mla=mla, bibtex=bibtex)

        return json.dumps({
            "success": True,
            "style": style,
            "citation": citation
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


def _format_apa(authors, year, title, journal, doi):
    """APA 7th 格式"""
    if not authors:
        author_str = "Unknown Author"
    elif len(authors) == 1:
        author_str = _apa_name(authors[0])
    elif len(authors) <= 20:
        author_str = ", ".join(_apa_name(a) for a in authors[:-1])
        author_str += f", & {_apa_name(authors[-1])}"
    else:
        author_str = ", ".join(_apa_name(a) for a in authors[:19])
        author_str += f", ... {_apa_name(authors[-1])}"

    citation = f"{author_str} ({year}). {title}."
    if journal:
        citation += f" *{journal}*."
    if doi:
        citation += f" https://doi.org/{doi}"
    return citation


def _format_mla(authors, title, journal, year):
    """MLA 9th 格式"""
    if not authors:
        author_str = "Unknown Author"
    elif len(authors) == 1:
        parts = authors[0].split()
        if len(parts) >= 2:
            author_str = f"{parts[-1]}, {' '.join(parts[:-1])}"
        else:
            author_str = authors[0]
    else:
        parts = authors[0].split()
        first = f"{parts[-1]}, {' '.join(parts[:-1])}" if len(parts) >= 2 else authors[0]
        author_str = f"{first}, et al."

    citation = f'{author_str}. "{title}."'
    if journal:
        citation += f" *{journal}*,"
    if year:
        citation += f" {year}."
    return citation


def _format_bibtex(paper_id, authors, year, title, journal, doi):
    """BibTeX 格式"""
    key = f"paper{paper_id}"
    if authors:
        parts = authors[0].split()
        key = (parts[-1] if parts else "unknown") + str(year or "nd")
        key = re.sub(r'[^a-zA-Z0-9]', '', key)

    bib = f"@article{{{key},\n"
    bib += f'  title = {{{title}}},\n'
    if authors:
        bib += f'  author = {{{" and ".join(authors)}}},\n'
    if year:
        bib += f'  year = {{{year}}},\n'
    if journal:
        bib += f'  journal = {{{journal}}},\n'
    if doi:
        bib += f'  doi = {{{doi}}},\n'
    bib += "}"
    return bib


def _apa_name(full_name: str) -> str:
    """将全名转换为 APA 格式（姓, 名首字母.）"""
    parts = full_name.strip().split()
    if len(parts) == 0:
        return full_name
    last = parts[-1]
    initials = ". ".join(p[0].upper() for p in parts[:-1] if p) + "." if len(parts) > 1 else ""
    return f"{last}, {initials}" if initials else last


# ─────────────────────────────────────────
# 工具5：查询数据库
# ─────────────────────────────────────────

@tool
def list_all_papers(query: str = "") -> str:
    """
    列出数据库中所有文献，可以传入关键词进行过滤。
    输入：query（可选，搜索关键词，为空则返回全部）
    输出：文献列表（JSON）
    """
    try:
        if query:
            papers = search_papers(query)
        else:
            papers = get_all_papers()

        result = []
        for p in papers:
            result.append({
                "id": p["id"],
                "title": p["title"],
                "authors": p["authors"],
                "year": p["year"],
                "journal": p["journal"],
                "doi": p["doi"],
                "created_at": p["created_at"]
            })
        return json.dumps({
            "success": True,
            "count": len(result),
            "papers": result
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
def get_paper_details(paper_id: int) -> str:
    """
    获取指定文献的完整信息，包括摘要、引用格式、划线列表。
    输入：paper_id
    输出：完整文献信息
    """
    try:
        paper = get_paper_by_id(paper_id)
        if not paper:
            return json.dumps({"success": False, "error": f"未找到 ID={paper_id} 的文献"})

        highlights = get_highlights_by_paper(paper_id)
        paper["highlights"] = highlights
        paper["highlights_count"] = len(highlights)
        # 不返回全文（太长），只返回摘要
        paper.pop("full_text", None)
        return json.dumps({"success": True, "paper": paper}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
def semantic_search_in_highlights(query: str, n_results: int = 5) -> str:
    """
    在所有划线内容中进行语义搜索，找到与查询最相关的划线。
    适合：「找找我读到的关于平台责任的观点」这类自然语言查询。
    输入：query（自然语言查询），n_results（返回数量，默认5）
    输出：最相关的划线内容及来源文献
    """
    try:
        results = semantic_search_highlights(query, n_results)
        return json.dumps({
            "success": True,
            "query": query,
            "results": results
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# ─────────────────────────────────────────
# 工具6：全流程一键处理
# ─────────────────────────────────────────

@tool
def process_pdf_and_save(file_path: str) -> str:
    """
    全流程处理：解析 PDF → 自动识别 DOI → 获取元数据 → 保存到数据库 → 提取已有高亮。
    这是处理新论文的一键工具，Agent 会在需要时调用其他专项工具补充信息。
    输入：PDF 文件路径
    输出：处理结果汇总（paper_id、元数据、提取的高亮数量）
    """
    try:
        # 1. 解析 PDF
        doc = fitz.open(file_path)
        pages_text = []
        for i, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            if text:
                pages_text.append(f"[第{i}页]\n{text}")

        # 提取已有高亮
        highlights_found = []
        for page_num, page in enumerate(doc, start=1):
            for annot in page.annots():
                if annot.type[0] in [8, 9, 10]:
                    rect = annot.rect
                    words = page.get_text("words")
                    highlighted_words = [
                        w[4] for w in words if fitz.Rect(w[:4]).intersects(rect)
                    ]
                    if highlighted_words:
                        highlights_found.append({
                            "page": page_num,
                            "text": " ".join(highlighted_words)
                        })
        doc.close()

        full_text = "\n\n".join(pages_text)

        # 2. 尝试从全文中找 DOI
        doi_match = re.search(r'10\.\d{4,}/[^\s,;\"\']+', full_text)
        doi = doi_match.group(0).rstrip('.') if doi_match else None

        # 3. 尝试从前两页提取标题（简单启发式：第一段非短行的文字）
        first_page_text = pages_text[0] if pages_text else ""
        lines = [l.strip() for l in first_page_text.split('\n') if len(l.strip()) > 20]
        guessed_title = lines[0] if lines else os.path.basename(file_path).replace('.pdf', '')

        return json.dumps({
            "success": True,
            "file_path": file_path,
            "total_pages": len(pages_text),
            "full_text_length": len(full_text),
            "full_text": full_text,  # Agent 可以用这个分析
            "guessed_title": guessed_title,
            "found_doi": doi,
            "existing_highlights": highlights_found,
            "highlights_count": len(highlights_found),
            "message": "PDF 解析完成，请继续获取元数据并保存到数据库"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# ─────────────────────────────────────────
# 工具7：论文全文分块索引（RAG 基础）
# ─────────────────────────────────────────

@tool
def build_paper_index(paper_id: int) -> str:
    """
    将指定论文的全文分块并建立向量索引，为 RAG 检索做准备。
    首次导入论文后调用一次即可，后续 search_paper_content 可直接使用。
    输入：paper_id（文献ID）
    输出：建立的分块数量
    """
    try:
        paper = get_paper_by_id(paper_id)
        if not paper:
            return json.dumps({"success": False, "error": f"未找到 paper_id={paper_id}"})
        full_text = paper.get("full_text") or ""
        if not full_text.strip():
            return json.dumps({"success": False, "error": "该文献没有全文内容，请先通过 process_pdf_and_save 解析 PDF"})
        n = index_paper_chunks(paper_id, full_text, paper["title"])
        return json.dumps({
            "success": True,
            "paper_id": paper_id,
            "chunks": n,
            "message": f"已为「{paper['title']}」建立 {n} 个分块索引，现在可以使用 search_paper_content 检索原文"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
def search_paper_content(paper_id: int, query: str, n_results: int = 4) -> str:
    """
    在指定论文的原文中语义检索相关段落。这是 Paper Agent 的核心 RAG 工具。
    先确保已调用 build_paper_index 建立索引（或论文通过 Auto-process 导入时会自动建立）。
    输入：paper_id（文献ID），query（检索问题，用自然语言描述想找的内容），n_results（返回段落数，默认4）
    输出：最相关的原文段落列表，每段约800字
    示例：search_paper_content(1, "平台责任的例外情形") → 返回论文中讨论该主题的原文片段
    """
    try:
        # 检查索引是否存在，没有则自动建立
        if not has_paper_chunks(paper_id):
            paper = get_paper_by_id(paper_id)
            if not paper:
                return json.dumps({"success": False, "error": f"未找到 paper_id={paper_id}"})
            full_text = paper.get("full_text") or ""
            if not full_text.strip():
                return json.dumps({
                    "success": False,
                    "error": "该文献尚未建立全文索引，且没有全文内容。请先通过 Import 页面上传 PDF 并使用 Auto-process 处理。"
                })
            index_paper_chunks(paper_id, full_text, paper["title"])

        results = search_paper_chunks(paper_id, query, n_results)
        if not results:
            return json.dumps({"success": False, "error": "未找到相关内容，可能索引为空"})

        formatted = []
        for r in results:
            formatted.append({
                "chunk_index": r["chunk_index"],
                "content": r["content"],
                "relevance": f"{(1 - (r['distance'] or 0)):.0%}" if r.get("distance") is not None else "N/A"
            })

        return json.dumps({
            "success": True,
            "paper_id": paper_id,
            "query": query,
            "results": formatted,
            "tip": "以上是原文中与你的问题最相关的段落，请基于这些内容回答"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
def save_paper_notes(paper_id: int, notes: str) -> str:
    """
    将 Agent 生成的结构化阅读笔记保存到数据库。
    notes 为 Markdown 格式的完整笔记内容。
    输入：paper_id（文献ID），notes（Markdown 格式的笔记内容）
    输出：保存结果
    """
    try:
        paper = get_paper_by_id(paper_id)
        if not paper:
            return json.dumps({"success": False, "error": f"未找到 paper_id={paper_id}"})
        update_paper_notes(paper_id, notes)
        return json.dumps({
            "success": True,
            "paper_id": paper_id,
            "message": f"笔记已保存到「{paper['title']}」（共 {len(notes)} 字）"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# 所有可用工具列表（供 Agent 使用）
ALL_TOOLS = [
    process_pdf_and_save,
    parse_pdf_file,
    extract_pdf_highlights,
    fetch_metadata_by_doi,
    search_paper_by_title,
    save_paper_to_db,
    save_highlight_to_db,
    generate_citation,
    list_all_papers,
    get_paper_details,
    semantic_search_in_highlights,
    build_paper_index,
    search_paper_content,
    save_paper_notes,
]
