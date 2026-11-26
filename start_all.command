#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  echo "[ERROR] 找不到虛擬環境：$PYTHON_BIN"
  echo "請先建立並安裝套件："
  echo "  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  read -r -p "按 Enter 鍵關閉..."
  exit 1
fi

MODEL_PATH="$SCRIPT_DIR/models/qwen2.5-coder-14b-instruct-q5_0.gguf"
if [ ! -f "$MODEL_PATH" ]; then
  MODEL_PATH="$(find "$SCRIPT_DIR/models" -maxdepth 1 -name '*.gguf' | head -n 1)"
fi

if [ -z "$MODEL_PATH" ] || [ ! -f "$MODEL_PATH" ]; then
  echo "[ERROR] 在 models/ 找不到任何 .gguf 模型檔案。"
  read -r -p "按 Enter 鍵關閉..."
  exit 1
fi

if [ ! -d "$SCRIPT_DIR/frontend/node_modules" ]; then
  echo "[INFO] 偵測到尚未安裝前端套件，正在執行 npm install..."
  (cd "$SCRIPT_DIR/frontend" && npm install)
fi

PIDS=()

cleanup() {
  echo ""
  echo "[INFO] 正在關閉所有服務..."
  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
  echo "[INFO] 所有服務已停止。"
}

trap cleanup EXIT INT TERM

echo "=========================================="
echo "  AI 智慧排班助理 - 一鍵啟動腳本"
echo "=========================================="
echo "專案目錄: $SCRIPT_DIR"
echo "模型檔案: $MODEL_PATH"
echo ""

# 1. 啟動 Agent LLM 伺服器 (Port 8080)
echo "[1/3] 啟動 Agent (llama_cpp.server) 於 Port 8080..."
"$PYTHON_BIN" -m llama_cpp.server --model "$MODEL_PATH" --port 8080 --n_ctx 8192 &
PIDS+=($!)

# 2. 啟動後端 FastAPI (Port 8000)
echo "[2/3] 啟動後端 (uvicorn) 於 Port 8000..."
"$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
PIDS+=($!)

# 3. 啟動前端 Vite (Port 5173)
echo "[3/3] 啟動前端 (Vite) 於 Port 5173..."
(cd "$SCRIPT_DIR/frontend" && npm run dev -- --host) &
PIDS+=($!)

echo ""
echo "[OK] 三個服務已啟動："
echo "  - 前端畫面: http://localhost:5173"
echo "  - 後端 API: http://localhost:8000/docs"
echo "  - Agent LLM: http://127.0.0.1:8080/v1"
echo ""
echo "按 Ctrl+C 或關閉此視窗即可同時停止所有服務。"
echo "=========================================="

wait
