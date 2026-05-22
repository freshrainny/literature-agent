# 📚 Librarian — AI 学术文献管理工具

> 为法学、社会科学研究者设计的文献管理系统。导入 PDF，划线批注，AI 辅助分析，一键生成综述草稿。

---

## 🚀 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动应用
streamlit run app.py
```

启动后浏览器自动打开。在侧边栏 **AI Engine** 处填入 API Key 并点击 Connect，即可使用全部 AI 功能。

> 不连接 AI 也可以正常使用文献管理、划线、笔记等基础功能。

---

## ✨ 核心功能

### 📁 Library — 文献库

- **文件夹视图**：首页显示所有文件夹卡片 + All Papers 入口
- **导入论文**：点击右上角 ＋ Import，上传 PDF 自动解析元数据（标题、作者、年份、期刊），支持 CrossRef DOI 查询补全
- **Agent 处理**：上传后可一键调用 AI 自动提取全文关键词、摘要
- **搜索**：支持标题/摘要全文搜索，以及基于 highlights 的语义向量搜索
- **Tag 筛选**：点击 pill 标签快速过滤，支持多选

### 📄 文献详情

点击任意论文卡片的 **Open** 进入详情页，包含五个 Tab：

| Tab | 功能 |
|-----|------|
| **Read** | PDF 阅读器，鼠标框选文字即可创建划线 |
| **Highlights** | 汇总所有划线，支持一键分析与论文论点的关联性 |
| **Citations** | 自动生成 APA / MLA / BibTeX 引用格式 |
| **Info** | 摘要、关键词管理、文件信息 |
| **Paper Agent** | 针对本篇论文的专属 AI 对话 |

### 🗂️ 文件夹（Collections）

- 创建任意数量的文件夹（如"第一章文献"、"平台责任"）
- 论文卡片右上角 **⊞** 按钮，弹窗选择加入/移出哪个文件夹
- 每个文件夹内置专属 **Folder Agent**，AI 分析仅聚焦该文件夹内的文献

### 📓 Notebook — 阅读笔记

- 每篇论文可拥有一份 Markdown 格式的阅读笔记
- **AI 一键生成**：Agent 自动检索论文全文，生成包含核心主张、论证脉络、关键概念的结构化笔记
- 笔记以仿真纸张样式展示，支持全屏编辑

### ✦ Agent 分析

**Paper Agent（单篇）**
- 针对单篇论文的上下文感知对话
- 分析划线与你的论文论点的关联，生成写作建议
- 自动追加分析结果到笔记

**Folder Agent（文件夹级）**
- 分析范围限定在当前文件夹内的文献
- 快捷提示：概述文献群、找共同论点/分歧点
- 每个文件夹有独立的对话历史

**Global Agent（全库）**
- 跨文献分析，研究方向建议，文献脉络梳理
- 找支撑材料、生成综述草稿、整理论证结构、找反驳观点

---

## 🛠️ 支持的 AI 模型

| 提供商 | 推荐模型 | 获取 API Key |
|--------|---------|-------------|
| OpenAI | gpt-4o / gpt-4o-mini | https://platform.openai.com/api-keys |
| Anthropic Claude | claude-sonnet-4-5 | https://console.anthropic.com/ |
| Google Gemini | gemini-2.0-flash | https://aistudio.google.com/ |
| DeepSeek | deepseek-chat | https://platform.deepseek.com/ |
| 通义千问 | qwen-max | https://dashscope.aliyuncs.com/ |
| 智谱 GLM | glm-4 | https://open.bigmodel.cn/ |
| Moonshot / Kimi | moonshot-v1-32k | https://platform.moonshot.cn/ |
| Ollama 本地 | llama3.1 / qwen2.5 | 本地部署，无需 Key |
| 自定义接口 | — | 任意 OpenAI 兼容格式 |

> 💡 推荐 **DeepSeek**，价格极低，中文效果出色，适合高频使用。

---

## 📁 项目结构

```
literature_agent/
├── app.py              # Streamlit 主应用（UI + 交互逻辑）
├── agent.py            # LangGraph ReAct Agent（Global / Paper）
├── database.py         # SQLite 数据库操作（论文、划线、文件夹等）
├── tools.py            # Agent 工具函数（搜索、引用生成等）
├── pdf_viewer.py       # PDF 阅读器组件（基于 fitz）
├── _pdf_component/     # 自定义 Streamlit 组件：PDF 划线交互
├── _hl_component/      # 自定义 Streamlit 组件：划线面板
├── requirements.txt    # Python 依赖
├── .env.example        # 环境变量示例
├── data/               # SQLite 数据库文件（自动生成）
└── uploads/            # 上传的 PDF 文件（自动生成）
```

---

## ⚙️ 配置说明

复制 `.env.example` 为 `.env`，可预设常用配置：

```env
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
```

也可以直接在应用侧边栏的 AI Engine 面板中填写，每次启动都会保留。

---

## 🧰 技术栈

| 层 | 技术 |
|----|------|
| UI 框架 | [Streamlit](https://streamlit.io/) 1.57+ |
| AI Agent | [LangGraph](https://langchain-ai.github.io/langgraph/) ReAct |
| LLM 接入 | LangChain（支持 OpenAI / Anthropic / Google 等） |
| PDF 处理 | [PyMuPDF (fitz)](https://pymupdf.readthedocs.io/) |
| 向量检索 | [ChromaDB](https://www.trychroma.com/)（本地，零配置） |
| 数据存储 | SQLite（本地文件，零配置） |
| 字体 | Inter + Lora（Google Fonts） |

---

## 🎨 设计理念

Librarian 的界面参考了 Notion 的简洁与 Zotero 的学术气质：

- **米白 + 暖棕**的色系，久看不疲劳
- **衬线体（Lora）** 用于标题和引用，强调阅读感
- 信息密度适中，不堆叠组件，呼吸感充足
- 所有 AI 入口用 **✦** 标识，与普通操作区分

---

## 📄 License

MIT — 自由使用、修改、分发。
