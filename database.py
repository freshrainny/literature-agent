"""
数据库模块
- SQLite：存储文献元数据（标题、作者、摘要、引用等）
- ChromaDB：向量数据库，存储划线内容，支持语义搜索
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "literature.db")
CHROMA_PATH = os.path.join(os.path.dirname(__file__), "data", "chroma_db")


def get_db_connection():
    """获取 SQLite 数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 让结果可以用列名访问
    return conn


def init_database():
    """初始化数据库表结构"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 文献表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            authors TEXT,           -- JSON 数组格式
            year INTEGER,
            journal TEXT,
            doi TEXT UNIQUE,
            abstract TEXT,
            keywords TEXT,          -- JSON 数组格式
            file_path TEXT,         -- 本地 PDF 路径
            full_text TEXT,         -- 全文（用于搜索）
            citation_apa TEXT,      -- APA 格式引用
            citation_mla TEXT,      -- MLA 格式引用
            citation_bibtex TEXT,   -- BibTeX 格式
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            notes TEXT              -- 用户自己的笔记
        )
    """)

    # 划线高亮表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS highlights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id INTEGER NOT NULL,
            content TEXT NOT NULL,      -- 划线的文字内容
            page_number INTEGER,        -- 在第几页
            context TEXT,               -- 前后文（±100字）
            color TEXT DEFAULT 'yellow',-- 高亮颜色标记
            tags TEXT,                  -- JSON 数组，用户标签
            note TEXT,                  -- 用户对这段划线的注释
            writing_suggestion TEXT,    -- Agent 生成的写作建议
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (paper_id) REFERENCES papers(id)
        )
    """)
    # 兼容旧库：若 writing_suggestion 列不存在则添加
    try:
        cursor.execute("ALTER TABLE highlights ADD COLUMN writing_suggestion TEXT")
        conn.commit()
    except Exception:
        pass  # 列已存在，忽略

    # Collections（主题文件夹）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            color TEXT DEFAULT '#c8b89a',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # 论文 ↔ Collection 多对多
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS paper_collections (
            paper_id INTEGER NOT NULL,
            collection_id INTEGER NOT NULL,
            PRIMARY KEY (paper_id, collection_id),
            FOREIGN KEY (paper_id) REFERENCES papers(id),
            FOREIGN KEY (collection_id) REFERENCES collections(id)
        )
    """)

    # My Thesis 配置（全局单行 key-value）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("✅ 数据库初始化完成")


# ─────────────────────────────────────────
# 文献 CRUD
# ─────────────────────────────────────────

def save_paper(title: str, authors: list, year: int = None,
               journal: str = None, doi: str = None, abstract: str = None,
               keywords: list = None, file_path: str = None,
               full_text: str = None) -> int:
    """保存文献到数据库，返回 paper_id"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO papers
            (title, authors, year, journal, doi, abstract, keywords, file_path, full_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title,
            json.dumps(authors, ensure_ascii=False) if authors else "[]",
            year,
            journal,
            doi,
            abstract,
            json.dumps(keywords, ensure_ascii=False) if keywords else "[]",
            file_path,
            full_text
        ))
        conn.commit()
        paper_id = cursor.lastrowid
        return paper_id
    finally:
        conn.close()


def update_paper_keywords(paper_id: int, keywords: list):
    """更新文献的关键词/标签列表"""
    conn = get_db_connection()
    conn.execute(
        "UPDATE papers SET keywords=? WHERE id=?",
        (json.dumps(keywords, ensure_ascii=False), paper_id)
    )
    conn.commit()
    conn.close()


def get_all_keywords() -> list:
    """获取所有文献的关键词去重列表，按频率排序"""
    conn = get_db_connection()
    rows = conn.execute("SELECT keywords FROM papers WHERE keywords IS NOT NULL").fetchall()
    conn.close()
    from collections import Counter
    counter = Counter()
    for row in rows:
        try:
            kws = json.loads(row[0]) if row[0] else []
            for k in kws:
                if k.strip():
                    counter[k.strip()] += 1
        except Exception:
            pass
    return [k for k, _ in counter.most_common()]


def update_citations(paper_id: int, apa: str = None, mla: str = None, bibtex: str = None):
    """更新引用格式"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE papers SET citation_apa=?, citation_mla=?, citation_bibtex=?
        WHERE id=?
    """, (apa, mla, bibtex, paper_id))
    conn.commit()
    conn.close()


def get_all_papers() -> list:
    """获取所有文献"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM papers ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        d = dict(row)
        d["authors"] = json.loads(d["authors"]) if d["authors"] else []
        d["keywords"] = json.loads(d["keywords"]) if d["keywords"] else []
        result.append(d)
    return result


def get_paper_by_id(paper_id: int) -> Optional[dict]:
    """根据 ID 获取文献"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM papers WHERE id=?", (paper_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["authors"] = json.loads(d["authors"]) if d["authors"] else []
        d["keywords"] = json.loads(d["keywords"]) if d["keywords"] else []
        return d
    return None


def search_papers(query: str) -> list:
    """关键词搜索文献（标题、摘要、关键词）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM papers
        WHERE title LIKE ? OR abstract LIKE ? OR keywords LIKE ?
        ORDER BY created_at DESC
    """, (f"%{query}%", f"%{query}%", f"%{query}%"))
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        d = dict(row)
        d["authors"] = json.loads(d["authors"]) if d["authors"] else []
        d["keywords"] = json.loads(d["keywords"]) if d["keywords"] else []
        result.append(d)
    return result


def delete_paper(paper_id: int):
    """删除文献及其所有划线"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM highlights WHERE paper_id=?", (paper_id,))
    cursor.execute("DELETE FROM papers WHERE id=?", (paper_id,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────
# 划线 CRUD
# ─────────────────────────────────────────

def save_highlight(paper_id: int, content: str, page_number: int = None,
                   context: str = None, color: str = "yellow",
                   tags: list = None, note: str = None) -> int:
    """保存划线内容，返回 highlight_id"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO highlights (paper_id, content, page_number, context, color, tags, note)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        paper_id,
        content,
        page_number,
        context,
        color,
        json.dumps(tags, ensure_ascii=False) if tags else "[]",
        note
    ))
    conn.commit()
    highlight_id = cursor.lastrowid
    conn.close()
    return highlight_id


def get_highlights_by_paper(paper_id: int) -> list:
    """获取某篇文献的所有划线"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM highlights WHERE paper_id=? ORDER BY page_number, id
    """, (paper_id,))
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        d = dict(row)
        d["tags"] = json.loads(d["tags"]) if d["tags"] else []
        result.append(d)
    return result


def get_all_highlights() -> list:
    """获取所有划线（带文献标题）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT h.*, p.title as paper_title, p.authors as paper_authors
        FROM highlights h
        JOIN papers p ON h.paper_id = p.id
        ORDER BY h.created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        d = dict(row)
        d["tags"] = json.loads(d["tags"]) if d["tags"] else []
        result.append(d)
    return result


# ─────────────────────────────────────────
# ChromaDB 向量存储（语义搜索划线 + 论文全文分块 RAG）
# ─────────────────────────────────────────

def _get_chroma_client():
    try:
        import chromadb
        return chromadb.PersistentClient(path=CHROMA_PATH)
    except ImportError:
        print("⚠️ ChromaDB 未安装，语义搜索功能不可用")
        return None


def get_chroma_collection():
    """获取划线用的 ChromaDB collection"""
    client = _get_chroma_client()
    if client is None:
        return None
    return client.get_or_create_collection(
        name="highlights",
        metadata={"hnsw:space": "cosine"}
    )


def get_chroma_chunks_collection():
    """获取论文全文分块用的 ChromaDB collection"""
    client = _get_chroma_client()
    if client is None:
        return None
    return client.get_or_create_collection(
        name="paper_chunks",
        metadata={"hnsw:space": "cosine"}
    )


def add_highlight_to_vector_db(highlight_id: int, content: str,
                                paper_id: int, paper_title: str):
    """将划线内容添加到向量数据库"""
    collection = get_chroma_collection()
    if collection is None:
        return
    try:
        collection.add(
            documents=[content],
            ids=[str(highlight_id)],
            metadatas=[{"paper_id": paper_id, "paper_title": paper_title}]
        )
    except Exception as e:
        print(f"⚠️ 向量存储失败: {e}")


def semantic_search_highlights(query: str, n_results: int = 5) -> list:
    """语义搜索划线内容"""
    collection = get_chroma_collection()
    if collection is None:
        return []
    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        output = []
        for i, doc in enumerate(results["documents"][0]):
            output.append({
                "content": doc,
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i] if "distances" in results else None
            })
        return output
    except Exception as e:
        print(f"⚠️ 语义搜索失败: {e}")
        return []


# ── 论文全文分块 RAG ──────────────────────

def index_paper_chunks(paper_id: int, full_text: str, paper_title: str,
                        chunk_size: int = 800, overlap: int = 200) -> int:
    """
    将论文全文分块并存入向量库。
    返回分块数量。每次调用会先删除该 paper_id 的旧块，避免重复。
    """
    collection = get_chroma_chunks_collection()
    if collection is None:
        return 0

    # 删除已有的旧块
    try:
        existing = collection.get(where={"paper_id": paper_id})
        if existing and existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception:
        pass

    # 分块：按字符滑动窗口，中英文都适用
    chunks = []
    i = 0
    while i < len(full_text):
        chunk = full_text[i:i + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        i += chunk_size - overlap

    if not chunks:
        return 0

    ids = [f"chunk_{paper_id}_{j}" for j in range(len(chunks))]
    metadatas = [{"paper_id": paper_id, "paper_title": paper_title,
                  "chunk_index": j} for j in range(len(chunks))]

    try:
        # ChromaDB 批量上限 5000，分批插入
        batch = 500
        for start in range(0, len(chunks), batch):
            collection.add(
                documents=chunks[start:start + batch],
                ids=ids[start:start + batch],
                metadatas=metadatas[start:start + batch]
            )
    except Exception as e:
        print(f"⚠️ 分块存储失败: {e}")
        return 0

    return len(chunks)


def search_paper_chunks(paper_id: int, query: str, n_results: int = 4) -> list:
    """
    在指定论文的分块中语义搜索，返回最相关的片段。
    用于 Paper Agent 的 RAG 检索。
    """
    collection = get_chroma_chunks_collection()
    if collection is None:
        return []
    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"paper_id": paper_id}
        )
        output = []
        for i, doc in enumerate(results["documents"][0]):
            output.append({
                "content": doc,
                "chunk_index": results["metadatas"][0][i].get("chunk_index", i),
                "distance": results["distances"][0][i] if "distances" in results else None
            })
        return output
    except Exception as e:
        print(f"⚠️ 分块检索失败: {e}")
        return []


def has_paper_chunks(paper_id: int) -> bool:
    """检查某篇论文是否已建立分块索引"""
    collection = get_chroma_chunks_collection()
    if collection is None:
        return False
    try:
        result = collection.get(where={"paper_id": paper_id}, limit=1)
        return len(result["ids"]) > 0
    except Exception:
        return False


# ─────────────────────────────────────────
# Collections CRUD
# ─────────────────────────────────────────

def get_all_collections() -> list:
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM collections ORDER BY name").fetchall()
    conn.close()
    result = []
    for row in rows:
        d = dict(row)
        # 计算该 collection 的论文数量
        cnt_conn = get_db_connection()
        cnt = cnt_conn.execute(
            "SELECT COUNT(*) FROM paper_collections WHERE collection_id=?", (d["id"],)
        ).fetchone()[0]
        cnt_conn.close()
        d["paper_count"] = cnt
        result.append(d)
    return result


def create_collection(name: str, description: str = "", color: str = "#c8b89a") -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO collections (name, description, color) VALUES (?, ?, ?)",
        (name.strip(), description.strip(), color)
    )
    conn.commit()
    cid = cursor.lastrowid
    conn.close()
    return cid


def delete_collection(collection_id: int):
    conn = get_db_connection()
    conn.execute("DELETE FROM paper_collections WHERE collection_id=?", (collection_id,))
    conn.execute("DELETE FROM collections WHERE id=?", (collection_id,))
    conn.commit()
    conn.close()


def add_paper_to_collection(paper_id: int, collection_id: int):
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO paper_collections (paper_id, collection_id) VALUES (?, ?)",
            (paper_id, collection_id)
        )
        conn.commit()
    finally:
        conn.close()


def remove_paper_from_collection(paper_id: int, collection_id: int):
    conn = get_db_connection()
    conn.execute(
        "DELETE FROM paper_collections WHERE paper_id=? AND collection_id=?",
        (paper_id, collection_id)
    )
    conn.commit()
    conn.close()


def get_papers_in_collection(collection_id: int) -> list:
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT p.* FROM papers p
        JOIN paper_collections pc ON p.id = pc.paper_id
        WHERE pc.collection_id = ?
        ORDER BY p.created_at DESC
    """, (collection_id,)).fetchall()
    conn.close()
    result = []
    for row in rows:
        d = dict(row)
        d["authors"] = json.loads(d["authors"]) if d["authors"] else []
        d["keywords"] = json.loads(d["keywords"]) if d["keywords"] else []
        result.append(d)
    return result


def get_collections_for_paper(paper_id: int) -> list:
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT c.* FROM collections c
        JOIN paper_collections pc ON c.id = pc.collection_id
        WHERE pc.paper_id = ?
        ORDER BY c.name
    """, (paper_id,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ─────────────────────────────────────────
# My Thesis / Config
# ─────────────────────────────────────────

def get_config(key: str, default: str = "") -> str:
    conn = get_db_connection()
    row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    conn.close()
    return row[0] if row else default


def set_config(key: str, value: str):
    conn = get_db_connection()
    conn.execute(
        "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
        (key, value)
    )
    conn.commit()
    conn.close()


def get_my_thesis() -> dict:
    """获取 My Thesis 配置"""
    return {
        "title":    get_config("thesis_title"),
        "argument": get_config("thesis_argument"),
        "keywords": get_config("thesis_keywords"),
        "outline":  get_config("thesis_outline"),
    }


def save_my_thesis(title: str, argument: str, keywords: str, outline: str):
    """保存 My Thesis 配置"""
    set_config("thesis_title",    title)
    set_config("thesis_argument", argument)
    set_config("thesis_keywords", keywords)
    set_config("thesis_outline",  outline)


# ─────────────────────────────────────────
# Paper notes 更新
# ─────────────────────────────────────────

def update_paper_notes(paper_id: int, notes: str):
    """更新论文的 notes 字段（用于存储 Agent 生成的结构化阅读笔记）"""
    conn = get_db_connection()
    conn.execute("UPDATE papers SET notes=? WHERE id=?", (notes, paper_id))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────
# Highlight writing_suggestion 更新
# ─────────────────────────────────────────

def update_highlight_suggestion(highlight_id: int, suggestion: str):
    conn = get_db_connection()
    conn.execute(
        "UPDATE highlights SET writing_suggestion=? WHERE id=?",
        (suggestion, highlight_id)
    )
    conn.commit()
    conn.close()


# 初始化
if __name__ == "__main__":
    init_database()
