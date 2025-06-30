# 台北一日遊 | Taipei Day Trip

一個提供旅遊預約體驗的全端專案，實作使用者會員系統、行程預約、付款流程等功能，前後端皆自建，並成功部署至 AWS EC2。整合 TapPay 金流模組，模擬完整下單付款流程，具備完整資料庫設計與 RESTful API 實作。

🔗 Demo 網站：**http://13.211.187.91:8000/**  
🔐 可註冊帳號，自行測試所有功能（無需金流綁卡）

---

## 📁 目錄結構 (File Structure)

```bash
.
├── templates/             # HTML 模板頁面（index.html, booking.html, thankyou.html）
├── static/                # 靜態資源 (CSS / JS)
├── app.py                 # FastAPI 主程式
├── database.py            # 資料庫連線與連線池設定
├── .env                   # 機密資訊與設定
└── requirements.txt       # Python 相依套件列表
```

## 🛠 使用技術 (Tech Stack)

### Frontend
- HTML / CSS / JavaScript（原生）
- IntersectionObserver 動畫效果
- TapPay SDK 金流整合
- RWD 響應式設計（含 360px、768px、1200px 斷點）

### Backend
- FastAPI + Pydantic
- RESTful API 設計（註冊、登入、預約、訂單）
- JWT 身份驗證機制
- MySQL 資料庫設計與操作
- Connection Pool（提升資料庫效能）
- python-dotenv 管理機密資訊

### Deploy
- AWS EC2（Ubuntu）
- Uvicorn + systemd 服務啟動
- MySQL 雲端資料庫

---

## 🧩 功能簡介

### `/` 首頁（index.html）
- 景點清單與搜尋（支援無限滾動載入）
- 點擊進入景點詳細頁面

### `/attraction/<id>` 景點詳情頁
- 輪播圖展示、景點說明、交通資訊
- 行程預約（選擇日期、時段、金額）

### `/booking` 行程預約頁
- 顯示會員預約內容
- 可刪除預約，填寫聯絡資訊後付款

### `/thankyou` 成功頁
- 顯示付款成功與訂單編號

---

## 🧪 技術亮點

### ✅ JWT 身份驗證
- 前端登入後儲存 JWT Token，並附帶於 API 請求中
- 後端驗證身份，提供會員資料與保護 API

### ✅ TapPay 金流整合
- 導入 TapPay SDK，實作信用卡欄位與驗證
- 提交付款資訊後建立訂單並導向成功頁面

### ✅ AWS EC2 實體部署
- 使用 SSH 連線與 `.pem` 金鑰
- 實作自動啟動服務與靜態資源托管
- 可供外部訪問與實機測試
