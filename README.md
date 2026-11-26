#  AI 智慧排班助理 (AI Scheduling Agent)

LLM 自然語言推理+排班管理系統。這不是一個聊天機器人，是掛上AI Agent的排班系統。

使用者只需透過口語指令（如：「下週三幫我排早班」），AI 即可自動完成查詢、衝突驗證、權限檢查及入庫操作。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.13-blue.svg)
![Vue](https://img.shields.io/badge/vue-3.0-green.svg)
![CUDA](https://img.shields.io/badge/CUDA-Supported-orange.svg)

---

## 核心說明

**語義編譯器 (Semantic Compiler)**：深度優化台灣口語理解，能精準推理「大後天」、「下週五」、「整個月」等相對時間，並自動對齊員工與節目實體清單。
**多層級權限防火牆**：
**管理員 (Admin)**：擁有上帝視角，可進行全域操作、帳號維護及臨時調整單日工時上限。
**製作人 (Producer)**：跨部門操作權限，可幫任何人排班，但受限於 **「Ownership 擁有權」** 規則——僅能刪除或修改自己親自排定的班表。
**一般員工 (Staff)**：僅能查詢所屬部門班表，並管理自己的排班與請假。
**持久化動作記憶庫**：系統具備 30 天滾動對話記憶，AI 會記得您過去的所有動作細節，支援上下文檢索。
**即時工時合規引擎**：排班時自動計算每日有效工時上限，防止超時違規，並在前端表格中即時標註「臨時調整」狀態。
**防災自動化機制**：內建背景巡邏任務，自動對接政府防災假資訊，全自動加註【颱風停班】標籤，無需人工干預。

---

## 技術架構

**前端**：Vue 3 (Composition API), Vite, Tailwind CSS, Pinia
**後端**：FastAPI (Python 3.13), SQLModel (Pydantic + SQLAlchemy)
**資料庫**：SQLite (支援非同步 aiosqlite), 具備 CASCADE 連鎖刪除與外鍵約束。
**AI 引擎**：OpenAI API 協議相容（支援本地端 GGUF 模型透過 `llama-cpp-python` 驅動）。
**部署**：Docker / Docker Compose。

---

##  PC 伺服器部署指引 (支援 GPU 加速)

本專案特別優化了本地 PC 伺服器的部署體驗，允許您利用顯示卡（NVIDIA GPU）來驅動 AI。

### 1. 硬體需求
**GPU**: NVIDIA RTX 30 系列或以上 (建議 12GB VRAM 以上)。
**軟體**: 需安裝最新版 NVIDIA Driver、Docker Desktop 及 **NVIDIA Container Toolkit**。

### 2. 啟動指令 (GPU 版)
1. **下載模型**：請至 Hugging Face (如 [Qwen2.5-Coder-14B-GGUF](https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct-GGUF)) 下載模型檔案。
2. **存放模型**：將下載的 `.gguf` 檔案放入根目錄的 `models/` 資料夾。
3. **執行啟動**：
```sh
docker-compose -f docker-compose.pc_server.yml up -d --build
```
*註：此模式下系統會自動在容器內編譯 CUDA 加速環境。*

---

##  快速啟動 (開發者模式)

### 環境設定（選用）
首次啟動前可依需要複製環境變數範本並自訂設定：
```sh
cp .env.example .env
```
*若未建立 `.env` 或未設定 `ADMIN_INITIAL_PASSWORD`，系統於首次初始化資料庫時會自動產生隨機 `SECRET_KEY` 與一次性 `admin` 初始密碼（顯示於終端機，請登入後修改）。*

### macOS 一鍵啟動（推薦）
確認已完成後端虛擬環境（`.venv`）與模型（`models/*.gguf`）放置後，直接雙擊專案根目錄的 `start_all.command`（或在終端機執行 `./start_all.command`），即可同時啟動 **Agent (8080)**、**後端 (8000)** 與 **前端 (5173)**。

### 手動啟動

#### 1. 後端啟動
```sh
# 1. 建立並啟動虛擬環境
python -m venv .venv
source .venv/bin/activate

# 2. 安裝依賴
pip install -r requirements.txt

# 3. 初始化資料庫 (自動建立 Table 與預設 Admin 帳號)
python -m app.core.init_db

# 4. 啟動服務 (0.0.0.0 允許區網連入)
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

#### 2. 前端啟動
```sh
cd frontend
npm install
npm run dev -- --host
```

#### 3. Agent 大腦啟動 (LLM 伺服器)
本系統依賴相容 OpenAI API 規格的推論伺服器。若使用本地 GGUF 模型，請執行：
```sh
# 確保已安裝 llama-cpp-python[server]
python -m llama_cpp.server --model ./models/your_model_name.gguf --port 8080 --n_ctx 8192
```

---

## 🌐 區域網路 (LAN) 測試說明

若要讓同事在同一個公司網路內連線測試：
1.  **取得您的 IP**：在終端機輸入 `ifconfig` (Mac) 或 `ipconfig` (Win)，找到 `192.168.x.x` 地址。
2.  **連線網址**：請同事在瀏覽器輸入 `http://[您的IP]:5173`。
3.  **注意**：請確保您的防火牆已允許 5173 與 8000 埠口的連入。

---

##  AI 互動範例

您可以直接對 Agent 下達指令：
*   **精準排班**：「幫我幫王大明排明天早上的班，節目是早安新聞。」
*   **範圍註銷**：「幫我把七月份所有的排班全部拿掉。」
*   **跨部門查詢**：「下禮拜二裝配組有哪些人上班？」
*   **請假登記**：「我下週三要請事假 8 小時。」
*   **權限測試**：(製作人角色)「幫我刪掉系統管理員排的班。」-> *系統將攔截並提示權限不足*。


---

## 🙏 致謝 (Acknowledgments)
本專案的核心推理能力由 [Qwen2.5-Coder](https://github.com/QwenLM/Qwen2.5-Coder) 系列模型驅動。特別感謝 **阿里雲 Qwen 團隊** 開源了如此強大的模型，讓本系統在中文語義理解與任務規劃上具備極高的準確度。

---

## 📄 開源協議
本專案採用 [MIT License](LICENSE) 協議。歡迎任何形式的 Contribution 與建議！
