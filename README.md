# Crawler Skill

這是一個功能強大的網頁爬蟲工具，專為將網頁內容轉換為乾淨的 Markdown 格式而設計。它內建了 **三級回退機制 (3-tier fallback chain)**，確保在面對各種反爬蟲限制或 API 故障時，仍能穩定獲取資料。

## 🌟 核心特性

- **三級自動回退**：依序嘗試 Firecrawl → Jina Reader → 本地 Scrapling。
- **高品質輸出**：自動將 HTML 轉換為格式精美的 Markdown。
- **繞過障礙**：具備 CAPTCHA 檢測、Cloudflare 繞過及隱身 (Stealth) 爬取能力。
- **靈活配置**：支援 Firecrawl 雲端 API 或 **自託管 (Self-hosted)** 實例。
- **開箱即用**：內建所有必要的依賴管理 (透過 `uv`)。

---

## 🛠 運作機制

| 層級 | 技術模組 | 說明 |
|:--- | :--- | :--- |
| **Tier 1** | **Firecrawl** | 首選方案。支援強大的結構化提取，可配置 `FIRECRAWL_API_KEY` 使用。 |
| **Tier 2** | **Jina Reader** | 免費方案。使用 `r.jina.ai` 代理，快速且不需 Key。 |
| **Tier 3** | **Scrapling** | 本地保險。在本地啟動 Headless 瀏覽器，具備 Stealth 模式繞過強效防禦。 |

---

## 🚀 快速開始

### 1. 前置需求
- 安裝 [Python 3.11+](https://www.python.org/)
- 安裝 [uv](https://github.com/astral-sh/uv) (推薦的 Python 依賴管理器)

### 2. 基本使用
使用 `uv` 直接執行腳本，不需手動安裝虛擬環境：

```bash
uv run skills/crawler-skill/scripts/crawl.py --url https://example.com
```

### 3. 環境變數配置
若要使用 Firecrawl 或自託管服務，請設定以下環境變數：

- `FIRECRAWL_API_KEY`: 你的 Firecrawl API 密鑰。
- `FIRECRAWL_API_URL`: (選填) 指向自託管實例 (例如 `http://localhost:3002`)。

---

## 🤖 作為 Claude Skill 使用

本專案已針對 **Claude Code** 進行優化。當你將此專案目錄加入 Claude 的路徑時，Claude 會自動識別此技能。

**觸發範例：**
- "幫我摘要這個網頁：https://example.com"
- "抓取 https://docs.python.org 的內容並存成 markdown"
- "這篇文章在說什麼？ https://vercel.com/blog/..."

---

## 🧪 開發與測試

執行完整的單元測試套件：

```bash
cd skills/crawler-skill/scripts
uv run pytest ../tests/ -v
```

目前已包含 51 項自動化測試，涵蓋了所有回退邏輯與邊際案例。

## 📁 檔案結構

```text
crawler-skill/
├── README.md           # 專案說明文件
├── skills/
│   └── crawler-skill/
│       ├── SKILL.md    # Claude 技能定義
│       ├── scripts/    # 核心爬蟲腳本
│       └── tests/      # 自動化測試套件
└── reports/            # 預設輸出目錄
```
