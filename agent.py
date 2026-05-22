"""
Agent 层
- GlobalAgent：总 Agent，管理整个文献库，可跨文献分析、综述生成
- PaperAgent：单篇文献 Agent，深度分析单篇论文
支持多种 LLM：OpenAI / Claude / Gemini / 任意 OpenAI 兼容接口
"""

import os
import sys
from typing import Optional, Literal
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from tools import ALL_TOOLS, get_paper_details, generate_citation
from database import init_database, get_paper_by_id, get_my_thesis

# ─────────────────────────────────────────
# LLM 工厂
# ─────────────────────────────────────────

LLM_PROVIDERS = {
    "openai":    {"label": "OpenAI",             "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]},
    "claude":    {"label": "Anthropic Claude",   "models": ["claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-4-5", "claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"]},
    "gemini":    {"label": "Google Gemini",      "models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]},
    "deepseek":  {"label": "DeepSeek",           "models": ["deepseek-chat", "deepseek-reasoner"]},
    "moonshot":  {"label": "Moonshot (Kimi)",    "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"]},
    "qwen":      {"label": "通义千问 (Qwen)",     "models": ["qwen-max", "qwen-plus", "qwen-turbo", "qwen-long"]},
    "zhipu":     {"label": "智谱 GLM",           "models": ["glm-4", "glm-4-flash", "glm-3-turbo"]},
    "ollama":    {"label": "Ollama (本地)",       "models": ["llama3.1", "qwen2.5", "mistral", "gemma2"]},
    "custom":    {"label": "自定义 OpenAI 兼容",  "models": []},
}


def create_llm(provider: str, model: str, api_key: str = None,
               base_url: str = None, temperature: float = 0):
    """
    创建 LLM 实例，支持多种提供商。
    所有非 OpenAI 官方的 API 都通过 langchain-openai 的 base_url 机制适配。
    """
    # 默认 base_url（各提供商的兼容端点）
    DEFAULT_URLS = {
        "claude":   None,           # 用 langchain-anthropic
        "gemini":   None,           # 用 langchain-google-genai
        "deepseek": "https://api.deepseek.com",
        "moonshot": "https://api.moonshot.cn/v1",
        "qwen":     "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "zhipu":    "https://open.bigmodel.cn/api/paas/v4",
        "ollama":   "http://localhost:11434/v1",
    }

    # 优先使用用户自定义 base_url，否则用默认
    resolved_url = base_url if base_url else DEFAULT_URLS.get(provider)

    if provider == "claude":
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=model,
                api_key=api_key or os.getenv("ANTHROPIC_API_KEY"),
                temperature=temperature,
            )
        except ImportError:
            raise ImportError("请安装：pip install langchain-anthropic")

    elif provider == "gemini":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=model,
                google_api_key=api_key or os.getenv("GOOGLE_API_KEY"),
                temperature=temperature,
            )
        except ImportError:
            raise ImportError("请安装：pip install langchain-google-genai")

    else:
        # OpenAI / DeepSeek / Moonshot / Qwen / 智谱 / Ollama / Custom
        # 这些都兼容 OpenAI SDK
        from langchain_openai import ChatOpenAI
        kwargs = {
            "model": model,
            "temperature": temperature,
        }
        key = api_key or os.getenv("OPENAI_API_KEY")
        if key:
            kwargs["api_key"] = key
        elif provider == "ollama":
            kwargs["api_key"] = "ollama"  # Ollama 不需要真实 key
        if resolved_url:
            kwargs["base_url"] = resolved_url
        return ChatOpenAI(**kwargs)


# ─────────────────────────────────────────
# 总 Agent（Global Agent）
# ─────────────────────────────────────────

def _build_thesis_context() -> str:
    """从数据库读取 My Thesis 配置，生成可注入 prompt 的文本块"""
    t = get_my_thesis()
    if not any(t.values()):
        return ""
    lines = ["\n## 用户正在撰写的论文 (My Thesis)"]
    if t["title"]:
        lines.append(f"- 论文题目：{t['title']}")
    if t["argument"]:
        lines.append(f"- 核心论点：{t['argument']}")
    if t["keywords"]:
        lines.append(f"- 关键概念：{t['keywords']}")
    if t["outline"]:
        lines.append(f"- 章节大纲：{t['outline']}")
    lines.append("")
    lines.append("当回答问题时，请始终考虑这篇论文的需求。指出前文内容可以如何支撑论文的哪个论点，或如何延伸、反驳、作为论据使用。")
    return "\n".join(lines)


GLOBAL_SYSTEM_PROMPT_BASE = """你是一个专业的学术文献管理助手。你帮助用户管理整个文献库。

## 你的能力
- **处理 PDF**：解析论文，提取全文，自动获取元数据
- **管理文献库**：增删查改，关键词搜索
- **跨文献分析**：比较多篇论文的观点，梳理研究脉络
- **生成引用**：APA、MLA、BibTeX 格式
- **语义搜索**：在所有划线中搜索相关内容

## 处理新 PDF 的标准流程
1. 调用 `process_pdf_and_save` 解析文件，获取全文和猜测标题
2. 有 DOI → 调用 `fetch_metadata_by_doi` 获取准确元数据
3. 无 DOI → 调用 `search_paper_by_title` 在 CrossRef 搜索
4. 调用 `save_paper_to_db` 保存，记录返回的 paper_id
5. **调用 `build_paper_index(paper_id)` 为全文建立 RAG 分块索引**（重要！这样 Paper Agent 才能检索原文）
6. 如果 PDF 中有已标注高亮，调用 `save_highlight_to_db` 逐一保存
7. 自动生成 APA 引用

## 回复规范
- 中文回复，语气专业简洁
- 明确说明每一步在做什么
- 完成后给出结构化摘要（文献信息 + 引用 + 划线数量）
- authors_json 格式：'["姓名1", "姓名2"]'
- keywords_json 格式：'["词1", "词2"]'

## 输出格式规范（用于 Markdown 内容）
- 层级清晰：用 `##` / `###` 区分章节，不要超过三级
- 列表项简洁：每条不超过 2 句话，用**加粗**标注核心观点
- 表格用于对比类内容（如关键概念、多文献对照）
- 不要输出冗余的"首先/其次/最后"套话
- 研究方向/题目建议格式：每条一个 `### 方向N：题目`，下跟「核心问题」「可用文献」「研究缺口」三项
"""


def get_global_system_prompt() -> str:
    """动态构建 Global Agent prompt，包含最新的 My Thesis 上下文"""
    return GLOBAL_SYSTEM_PROMPT_BASE + _build_thesis_context()


# ─────────────────────────────────────────
# 单篇文献 Agent（Paper Agent）
# ─────────────────────────────────────────

def make_paper_system_prompt(paper: dict) -> str:
    authors = ", ".join(paper.get("authors") or []) or "未知"
    pid = paper.get('id')
    thesis_ctx = _build_thesis_context()
    return f"""你是专门负责分析这篇论文的学术助手。

## 论文信息
- 标题：{paper.get('title', '未知')}
- 作者：{authors}
- 年份：{paper.get('year', '未知')}
- 期刊：{paper.get('journal', '未知')}
- 摘要：{(paper.get('abstract') or '')[:500]}

## 当前论文 ID
paper_id = {pid}

## 你的能力

### 1. 检索原文（RAG）——最重要
你没有全文，但可以用 `search_paper_content` 工具检索相关段落：
```
search_paper_content(paper_id={{pid}}, query="你想找的内容")
```
**任何问题都先用这个工具检索相关段落，再基于上下文回答，不要根据摘要猜测。**

### 2. 管理划线
- `save_highlight_to_db`：保存划线到数据库
- `get_paper_details`：查看这篇文献已有的划线

### 3. 其他
- `generate_citation`：生成 APA / MLA / BibTeX 引用
{thesis_ctx}
## 回复规范
- 中文回复，学术风格
- 回答问题前先调用 `search_paper_content` 检索相关原文，不要根据摘要猜测
- 引用原文时注明是论文原文
- 保存划线后告知已存储
- 若有 My Thesis 上下文，每次分析划线时都要给出「写作建议」：指出这段话可以用在论文的哪个论点，建议直接引用/转述/反驳，以及可以如何延伸
"""


# ─────────────────────────────────────────
# Assistant 类（对外统一接口）
# ─────────────────────────────────────────

class LiteratureAssistant:
    """
    文献管理助手
    - global_agent：总 Agent，管理整个文献库
    - paper_agents：每篇论文对应一个独立 Agent（按需创建，懒加载）
    """

    def __init__(self, provider: str, model: str, api_key: str = None,
                 base_url: str = None):
        init_database()
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

        # 创建总 Agent（prompt 动态读取 My Thesis）
        llm = create_llm(provider, model, api_key, base_url, temperature=0)
        memory = MemorySaver()
        self._global_agent = create_react_agent(
            model=llm,
            tools=ALL_TOOLS,
            prompt=get_global_system_prompt(),
            checkpointer=memory,
        )
        self._global_memory = memory

        # 单篇 Agent 缓存（paper_id -> agent）
        self._paper_agents: dict = {}
        self._paper_memories: dict = {}

    def _get_paper_agent(self, paper_id: int):
        """懒加载：按需创建或复用单篇文献 Agent"""
        if paper_id not in self._paper_agents:
            paper = get_paper_by_id(paper_id)
            if not paper:
                raise ValueError(f"未找到 paper_id={paper_id} 的文献")
            llm = create_llm(
                self.provider, self.model,
                self.api_key, self.base_url, temperature=0
            )
            mem = MemorySaver()
            agent = create_react_agent(
                model=llm,
                tools=ALL_TOOLS,
                prompt=make_paper_system_prompt(paper),
                checkpointer=mem,
            )
            self._paper_agents[paper_id] = agent
            self._paper_memories[paper_id] = mem
        return self._paper_agents[paper_id]

    def _run_agent(self, agent, message: str, thread_id: str) -> str:
        """运行 Agent 并返回最后一条 AI 消息"""
        config = {"configurable": {"thread_id": thread_id}}
        result = agent.invoke(
            {"messages": [HumanMessage(content=message)]},
            config=config
        )
        for msg in reversed(result["messages"]):
            if hasattr(msg, "content") and msg.__class__.__name__ == "AIMessage":
                return msg.content
        return "完成"

    # ── 总 Agent 对话 ────────────────────
    def global_chat(self, message: str, thread_id: str = "global") -> str:
        return self._run_agent(self._global_agent, message, thread_id)

    # 阅读笔记 Markdown 模板（与 Content_Moderation_as_Systems_Thinking_笔记.md 保持一致）
    NOTE_TEMPLATE = """\
# {title} —— 阅读笔记

## 引文

{apa_citation}

---

## 基本信息

| 项目 | 内容 |
|------|------|
| **作者** | {authors} |
| **期刊** | {journal} |
| **年份** | {year} |
| **全文共** | {total_pages} 页 |

---

## 摘要

{abstract_summary}

---

## 全文总结

### 核心论点

{core_arguments}

---

## 重点观点重述

{key_points}

---

## 关键概念对照

| 英文 | 中文/释义 |
|------|---------|
{key_concepts}

---

*整理时间：{date}*
"""

    def process_pdf(self, pdf_path: str, thread_id: str = "global") -> str:
        import datetime
        today = datetime.date.today().strftime("%Y-%m-%d")
        thesis = get_my_thesis()
        thesis_note = ""
        if any(thesis.values()):
            thesis_note = (
                f"\n\n【附加要求】用户正在撰写论文：{thesis.get('title', '')}，"
                f"核心论点：{thesis.get('argument', '')}。"
                "在「重点观点重述」中，请在每个重要观点后用一句话注明：「与用户论文的关联：……」"
                "以及「可用于论文第X部分/支撑某论点」。"
            )

        msg = (
            f"请按以下完整流程处理论文：{pdf_path}\n\n"
            "═══ 第一阶段：导入与索引 ═══\n"
            "1. 调用 process_pdf_and_save 解析 PDF 获取全文和 DOI\n"
            "2. 有 DOI → fetch_metadata_by_doi；无 DOI → search_paper_by_title\n"
            "3. 调用 save_paper_to_db 保存，记下返回的 paper_id\n"
            "4. 调用 build_paper_index(paper_id) 为全文建立 RAG 分块索引\n"
            "5. 如有已有高亮，调用 save_highlight_to_db 逐一保存\n"
            "6. 调用 generate_citation 生成 APA 引用\n\n"
            "═══ 第二阶段：生成结构化阅读笔记 ═══\n"
            "完成第一阶段后，调用 search_paper_content 多次（建议4-6次），分别检索：\n"
            "  - 论文核心论点/thesis\n"
            "  - 研究背景与问题\n"
            "  - 主要论证与子观点\n"
            "  - 关键概念定义\n"
            "  - 结论与政策建议\n\n"
            "然后用以下 Markdown 模板生成完整阅读笔记，并调用 save_paper_notes(paper_id, notes) 保存：\n\n"
            f"{self.NOTE_TEMPLATE}\n"
            "填写说明：\n"
            "  - {{abstract_summary}}：2-4句话概括论文核心主张（不是摘要原文，而是你的理解）\n"
            "  - {{core_arguments}}：编号列表，每条1-2句话，至少3条\n"
            "  - {{key_points}}：按论文各节分块，每块写2-4个重点观点（用**加粗**标注重要句子）\n"
            "  - {{key_concepts}}：列出论文中出现的专业术语及其中文含义，至少6组\n"
            f"  - {{date}}：{today}\n"
            f"{thesis_note}\n\n"
            "完成后输出：论文标题、paper_id、分块数、APA引用、笔记字数。"
        )
        return self.global_chat(msg, thread_id)

    # ── 单篇文献 Agent 对话 ──────────────
    def paper_chat(self, paper_id: int, message: str,
                   thread_id: str = None) -> str:
        agent = self._get_paper_agent(paper_id)
        tid = thread_id or f"paper_{paper_id}"
        return self._run_agent(agent, message, tid)

    def invalidate_paper_agent(self, paper_id: int):
        """当文献信息更新后，清除对应 Agent 缓存"""
        self._paper_agents.pop(paper_id, None)
        self._paper_memories.pop(paper_id, None)

    def refresh_thesis_context(self):
        """My Thesis 更新后调用：重建 Global Agent 并清空所有 Paper Agent 缓存"""
        llm = create_llm(
            self.provider, self.model,
            self.api_key, self.base_url, temperature=0
        )
        memory = MemorySaver()
        self._global_agent = create_react_agent(
            model=llm,
            tools=ALL_TOOLS,
            prompt=get_global_system_prompt(),
            checkpointer=memory,
        )
        self._global_memory = memory
        self._paper_agents.clear()
        self._paper_memories.clear()

    def analyze_highlight_for_thesis(self, paper_id: int, highlight_text: str,
                                     page: int, thread_id: str) -> str:
        """
        保存划线并触发 Paper Agent 生成写作建议。
        返回 Agent 的完整分析文本。
        """
        agent = self._get_paper_agent(paper_id)
        thesis = get_my_thesis()
        thesis_note = ""
        if any(thesis.values()):
            thesis_note = (
                f"\n\n请结合我的论文需求（{thesis.get('argument') or thesis.get('title') or ''}）"
                "给出具体的写作建议：① 这段话支撑哪个论点 ② 建议直接引用/转述/反驳 ③ 可以如何延伸讨论"
            )
        msg = (
            f"我从第 {page} 页划线了这段文字：\n\n\"{highlight_text}\"\n\n"
            f"请帮我：\n"
            f"1. 用一句话总结其核心观点\n"
            f"2. 建议 2-3 个标签\n"
            f"3. 自动保存这条划线（paper_id={paper_id}，page={page}）\n"
            f"{thesis_note}"
        )
        return self._run_agent(agent, msg, thread_id)


# ─────────────────────────────────────────
# 命令行测试入口
# ─────────────────────────────────────────

if __name__ == "__main__":
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ 请设置 OPENAI_API_KEY")
        sys.exit(1)

    assistant = LiteratureAssistant("openai", "gpt-4o-mini", api_key)
    print("🎓 文献管理 Agent（输入 quit 退出）")
    while True:
        msg = input("\n你：").strip()
        if msg.lower() in ("quit", "q"):
            break
        print("Agent：", assistant.global_chat(msg))
