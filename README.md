# 進階貝祖恆等式計算器 Web 版

這是從原 Streamlit `app.py` 拆出的可部署網站版本：

- 模式 1：直接輸入 A、B、C、D
- 模式 2：輸入 SISO 轉移函數 G(s)
- 模式 3：上傳圖片，由 Gemini 辨識 G(s)
- 期望閉迴路極點配置 F、L
- 右側 M、N、X、Y 與左側波浪因子
- 4 個擴展貝祖恆等式項目驗證
- KaTeX 數學公式渲染、RWD 手機版介面

## 本機執行

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app:app --reload
```

開啟 http://127.0.0.1:8000

## 部署

這個專案可直接部署到支援 Docker / Python Web Service 的平台（例如 Render、Railway、Fly.io、雲端 VM）。

啟動指令：

```bash
uvicorn app:app --host 0.0.0.0 --port $PORT
```

或直接使用 Dockerfile。

## Gemini API Key

目前圖片辨識模式沿用你原本的設計：使用者在網頁輸入自己的 Gemini API Key，後端只在該次請求使用，不寫入檔案。

更適合公開多人使用的做法，是改成在部署平台設定 `GEMINI_API_KEY` 環境變數，並拿掉前端 API Key 欄位；目前版本先保留原程式的使用方式。

## 計算引擎說明

原程式使用 Python Control 的 `place` 與 `tf2ss`；此 Web 版以 SciPy 的 `place_poles` / `tf2ss` 完成同等的數值控制系統步驟，SymPy 負責符號轉換與貝祖恆等式化簡。

## Render 部署

1. 將此資料夾內容上傳到 GitHub repository。
2. 在 Render 建立 New → Web Service，連接該 repository。
3. Language 選 Docker；Render 會使用專案內的 Dockerfile。
4. Plan 可先選 Free。
5. 建立服務後，Health Check Path 使用 `/api/health`。
6. 若要讓所有訪客共用網站管理者的 Gemini Key，在 Render 的 Environment Variables 設定 `GEMINI_API_KEY`。不要把 API Key 寫死在 GitHub 程式碼中。

部署完成後 Render 會提供 `https://<service-name>.onrender.com` 公開網址。
