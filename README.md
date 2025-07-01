# 台北一日遊 | Taipei Day Trip

一個提供旅遊預約體驗的全端專案，實作使用者會員系統、行程預約、付款流程等功能，前後端皆自建，並成功部署至 AWS EC2。整合 TapPay 金流模組，模擬完整下單付款流程，具備完整資料庫設計與 RESTful API 實作。

---

## 📁 目錄結構 (File Structure)
本專案使用 FastAPI + 原生 HTML/CSS/JS，並採用扁平化資料夾結構，主要內容如下：
```bash
taipei-day-trip/
├── app.py # FastAPI 主應用
├── .env # 機密資訊 (.env)
├── taipei-attractions.json # 景點資料初始化用
├── static/ # 前端靜態檔案（所有 HTML、CSS、JS、圖片）
│ ├── index.html # 首頁
│ ├── attraction.html # 景點頁面
│ ├── booking.html # 預定行程頁
│ ├── member.html # 會員中心頁
│ ├── thankyou.html # 訂單完成頁
│ ├── main.css # 全站樣式表
│ ├── icon_*.png # icon 圖片素材
│ └── member_photos/ # 上傳頭像資料夾
```

## 🛠 使用技術 (Tech Stack)

### Frontend
- HTML / CSS / JavaScript（原生）
- IntersectionObserver 動畫效果
- TapPay SDK 金流整合
- RWD 響應式設計（含 360px、768px、1200px 斷點）

### Backend
- FastAPI 
- RESTful API 設計（註冊、登入、預約、訂單）
- JWT 身份驗證機制
- MySQL 資料庫設計與操作
- Connection Pool（提升資料庫效能）
- python-dotenv 管理機密資訊

### Deploy
- AWS EC2（Ubuntu）
- 使用 `uvicorn` 指令手動啟動 FastAPI 
- MySQL 安裝在 EC2 上並本機連線
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

---
### 🧪 Demo 帳號

- 會員：aa@123.com / 123456

---

## 📎 專案連結

[http://13.211.187.91:8000/](http://13.211.187.91:8000/)

---

## 👨‍💻 作者

陳昱仲  
E-mail:volcano1107@gmail.com

