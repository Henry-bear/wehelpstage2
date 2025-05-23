from fastapi import FastAPI, Query, Request, Header, Body, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
import json
import mysql.connector
import re
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt, uuid
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import requests
import random
import string
from dotenv import load_dotenv
from mysql.connector import pooling
import os
import glob, time
load_dotenv()
app=FastAPI()


# JWT 設定
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"

# 設置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],  # 允許所有 HTTP 方法
    allow_headers=["*"],  # 允許所有標頭
)

# 建立連線池
dbconfig ={
     "host": "127.0.0.1",
     "user": os.getenv("DB_USER"),
     "password": os.getenv("DB_PASSWORD"),
     "database": os.getenv("DB_NAME")
}

cnxpool = pooling.MySQLConnectionPool(
     pool_name="taipeipool",
     pool_size=10,
     pool_reset_session=True,
     **dbconfig
)

# 讀取 JSON 檔案
with open("data/taipei-attractions.json", "r", encoding="utf-8") as file:
	data = json.load(file)

# 過濾圖片 URL
def filter_images(image_string):
	urls = image_string.split("https://")
	valid_urls = ["https://" + url for url in urls  if re.search(r"\.(jpg|png|jpeg)$", url, re.IGNORECASE)]
	return valid_urls



# 插入資料到 MySQL
def insert_data_to_db():
    try:
        db = cnxpool.get_connection()
        cursor = db.cursor()

        for attraction in data["result"]["results"]:
            # 先檢查資料是否已存在
            cursor.execute("SELECT id FROM attractions WHERE name = %s AND address = %s", (attraction["name"], attraction["address"]))
            existing_record = cursor.fetchone()

            if existing_record is None:
                # 插入新資料
                cursor.execute(
                 "INSERT INTO attractions (name, category, description, address, transport, mrt, lat, lng) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (attraction["name"], attraction["CAT"], attraction["description"], attraction["address"], attraction["direction"], attraction["MRT"], attraction["latitude"], attraction["longitude"])
                )


                attraction_id = cursor.lastrowid

                # 儲存過濾後的圖片 URL
                image_urls = filter_images(attraction["file"])
                for url in image_urls:
                    cursor.execute("INSERT INTO images (attraction_id, url) VALUES (%s, %s)", (attraction_id, url))

        db.commit()
    except mysql.connector.Error as err:
        print(f"Error: {err}")
    finally:
        cursor.close()
        db.close()

insert_data_to_db()


# Static Pages (Never Modify Code in this Block)
@app.get("/", include_in_schema=False)
async def index(request: Request):
	return FileResponse("./static/index.html", media_type="text/html")
@app.get("/attraction/{id}", include_in_schema=False)
async def attraction(request: Request, id: int):
	return FileResponse("./static/attraction.html", media_type="text/html")
@app.get("/booking", include_in_schema=False)
async def booking(request: Request):
	return FileResponse("./static/booking.html", media_type="text/html")
@app.get("/thankyou", include_in_schema=False)
async def thankyou(request: Request):
	return FileResponse("./static/thankyou.html", media_type="text/html")
@app.get("/member", include_in_schema=False)
async def member(request: Request):
	return FileResponse("./static/member.html", media_type="text/html")

# 景點資料結構
class Attraction(BaseModel):
    id: int
    name: str
    category: str
    description: str
    address: str
    transport: str
    mrt: Optional[str]
    lat: float
    lng: float
    images: List[str]

class Mrts(BaseModel):
    data: List[str]

class Error(BaseModel):
    error: bool
    message: str

# 註冊用資料結構
class UserRegister(BaseModel):
     name: str
     username: EmailStr     # e-mail
     password: str
# 登入用資料結構
class UserLogin(BaseModel):
     username: str
     password: str

# 預定行程資料結構
class BookingCreate(BaseModel):
     attractionId: int
     date: str
     time: str
     price: int

# 聯絡人資訊資料結構
class ContactInfo(BaseModel):
     name: str
     email: EmailStr
     phone: str

# 訂單資料結構
class OrderRequest(BaseModel):
     prime: str
     order: BookingCreate
     contact: ContactInfo

# 更新姓名結構
class UserUpdateName(BaseModel):
    name: str


# === TapPay 金流串接函式 ===
def pay_by_prime(prime, amount, contact_name, email, phone):
    url = "https://sandbox.tappaysdk.com/tpc/payment/pay-by-prime"

    headers={
        "Content-Type": "application/json",
        "x-api-key": os.getenv("TAPPAY_PARTNER_KEY")
     }
    payload={
          "prime": prime,
          "partner_key": os.getenv("TAPPAY_PARTNER_KEY"),
          "merchant_id": os.getenv("TAPPAY_MERCHANT_ID"),
          "amount": amount,
          "currency": "TWD",
          "details": "台北一日遊付款",
          "cardholder": {
            "phone_number": phone,
            "name": contact_name,
            "email": email
        },
        "remember": False
     }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()

# 產生訂單編號函式
def generate_order_number():
    today = datetime.now().strftime("%Y%m%d")  # ex 20250417
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))  # ex "A8F1Z9"
    return f"ORD{today}-{rand}"

# API Endpoints
@app.get("/api/attractions", responses={
     200: {"model": Attraction, "description": "正常運作"},
     500: {"model": Error, "description": "伺服器內部錯誤"}
})
def get_attractions(
    page: int = Query(0, alias="page", ge=0), 
    keyword: str = Query(None, alias="keyword")
):
    try:
        db = cnxpool.get_connection()
        cursor = db.cursor(dictionary=True)

        # **固定每頁 12 筆**
        limit = 12  
        offset = page * limit  

        # **根據 keyword 建立 SQL 查詢**
        if keyword:
            sql_query = """
                SELECT 
                    a.id, a.name, a.category, a.description, a.address, 
                    a.transport, a.mrt, a.lat, a.lng,
                    GROUP_CONCAT(i.url) AS images  
                FROM attractions a
                LEFT JOIN images i ON a.id = i.attraction_id  
                WHERE a.mrt = %s OR a.name LIKE %s  
                GROUP BY a.id  
                LIMIT %s OFFSET %s
            """

            cursor.execute(sql_query, (keyword, f"%{keyword}%", limit, offset))
        else:
            sql_query = """
                SELECT 
                    a.id, a.name, a.category, a.description, a.address, 
                    a.transport, a.mrt, a.lat, a.lng,
                    GROUP_CONCAT(i.url) AS images  
                FROM attractions a
                LEFT JOIN images i ON a.id = i.attraction_id
                GROUP BY a.id
                LIMIT %s OFFSET %s
            """
            cursor.execute(sql_query, (limit, offset))

        attractions = cursor.fetchall()

        # 取得總景點數
        if keyword:
            cursor.execute("SELECT COUNT(*) AS total FROM attractions WHERE mrt = %s OR name LIKE %s", (keyword, f"%{keyword}%"))
        else:
            cursor.execute("SELECT COUNT(*) AS total FROM attractions")

        total = cursor.fetchone()["total"]

        # 計算下一頁 page (如果有更多資料)
        next_page = page + 1 if (offset + limit) < total else None

        # 加入圖片 URL
        for attraction in attractions:
            attraction["images"] = attraction["images"].split(",") if attraction["images"] else []

        cursor.close()
        db.close()

        return {
            "nextPage": next_page,
            "data": attractions
        }
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"error": True, "message": "伺服器內部錯誤"}
        )

@app.get("/api/attraction/{attractionId}", responses={
    200: {"model": Attraction, "description": "景點資料"},
    400: {"model": Error, "description": "景點編號不正確"},
    500: {"model": Error, "description": "伺服器內部錯誤"}
})
def get_attraction(attractionId: str):
    try:
        attractionId = int(attractionId)  # 轉換成整數
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"error": True, "message": "景點編號必須是數字"}
        )

    try:
        db = cnxpool.get_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SET SESSION group_concat_max_len = 1000000;")

        # 修改 SQL： JOIN attractions 和 images
        cursor.execute("""
            SELECT 
                a.id, a.name, a.category, a.description, a.address, 
                a.transport, a.mrt, a.lat, a.lng,
                GROUP_CONCAT(i.url SEPARATOR '|||') AS images
            FROM attractions a
            LEFT JOIN images i ON a.id = i.attraction_id
            WHERE a.id = %s
            GROUP BY a.id
        """, (attractionId,))

        attraction = cursor.fetchone()
        
        if attraction is None:
            return JSONResponse(
                status_code=400,
                content={"error": True, "message": "查無此景點編號"}
            )


        # 加入圖片 URL
        attraction["images"] = attraction["images"].split("|||") if attraction["images"] else []


        cursor.close()
        db.close()

        return {"data": attraction}
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"error": True, "message": "伺服器內部錯誤"}
        )

@app.get("/api/mrts", responses={
    200: {"model": Mrts, "description": "正常運作"},
    500: {"model": Error, "description": "伺服器內部錯誤"}
})
def get_mrts():
    try:
        db = cnxpool.get_connection()
        cursor = db.cursor(dictionary=True)

        # 取得所有的 MRT 資訊
        # 取得所有 MRT 站名，並按照周邊景點數量排序
        cursor.execute("""
            SELECT mrt, COUNT(*) AS attraction_count 
            FROM attractions 
            WHERE mrt IS NOT NULL 
            GROUP BY mrt 
            ORDER BY attraction_count DESC;
        """)
        mrt_stations = cursor.fetchall()

        cursor.close()
        db.close()

        return {
            "data": [station["mrt"] for station in mrt_stations]
        }
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"error": True, "message": "伺服器內部錯誤"}
        )
# USER API Endpoints
# 會員註冊 API
@app.post("/api/user")
def register_user(user: UserRegister):
    try:
          db = cnxpool.get_connection()
          cursor = db.cursor()

          # 檢查 username 是否已存在
          cursor.execute("SELECT id FROM member WHERE username = %s",(user.username,))
          if cursor.fetchone():
               return JSONResponse(status_code=400, content={"error": True, "message": "此帳號已被註冊"})
          # 將密碼加密
          hashed_pw = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt())
          # 新增新會員資料
          cursor.execute(
               "INSERT INTO member (name, username, password) VALUES (%s, %s, %s)",
               (user.name, user.username, hashed_pw)    
          )
          db.commit()

          return {"ok": True}
    except Exception as e:
        print("註冊失敗錯誤：", e)
        return JSONResponse(status_code=500, content={"error": True, "message": "伺服器錯誤"})
    finally:
        cursor.close()
        db.close()

# 會員登入 API
@app.post("/api/user/auth")
def login_user(user: UserLogin):
    try:
        db= cnxpool.get_connection()
        cursor = db.cursor(dictionary=True)

        # 根據 username 查詢會員資料
        cursor.execute("SELECT * FROM member WHERE username = %s",(user.username,))
        record = cursor.fetchone()

        # 如有此帳號，且密碼正確
        if record and bcrypt.checkpw(user.password.encode("utf-8"), record["password"].encode("utf-8")):
             # 建立 JWT Token 包含會員基本資訊
             payload = {
                  "id": record["id"],
                  "name":record["name"],
                  "username": record["username"],
                  "exp": datetime.now(timezone.utc) + timedelta(days=7)
             }
             token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
             return {"token": token}
        # 登入失敗
        return JSONResponse(status_code=400, content={"error": True, "message": "帳號或密碼錯誤"})
    except Exception:
         return JSONResponse(status_code=500, content={"error": True, "message": "伺服器錯誤"})
    finally:
         cursor.close()
         db.close()
# 會員登入狀態驗證 API
@app.get("/api/user/auth")
def check_auth(Authorization: Optional[str] = Header(None)):
    # 無 token 視為未登入
    if not Authorization:
         return {"data": None}
    try:
        # 從 header 取出 Bearer token
        scheme, token = Authorization.split()
        if scheme.lower() != "bearer":
              return {"data": None}
        # 解碼 token 並取得會員資料
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

        # 資料庫查詢 avatar_url
        db = cnxpool.get_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT avatar_url FROM member WHERE id = %s", (payload["id"],))
        avatar_data = cursor.fetchone()
        cursor.close()
        db.close()

        return {"data": {
            "id": payload["id"],
            "name": payload["name"],
            "username": payload["username"],
            "avatar_url": avatar_data["avatar_url"] if avatar_data else None
        }}
    except Exception:
         # 解碼失敗，代表未登入
        return {"data": None}
    
# Booking API Endpoints
# 預訂行程 API
@app.post("/api/booking")
def create_booking(booking: BookingCreate = Body(...),Authorization: Optional[str] = Header(None)):
    if not Authorization:
        return JSONResponse(status_code=403, content={"error": True, "message": "未登入使用者"})
    try:
        #解析 JWT
        scheme, token = Authorization.split()
        if scheme.lower() != "bearer":
            return JSONResponse(status_code=403, content={"error": True, "message": "授權格式錯誤"})
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        member_id = payload["id"]
        # 連接資料庫
        db = cnxpool.get_connection()
        cursor = db.cursor()

        # 檢查是否已有預定 → 有的話更新，沒有的話插入
        cursor.execute("SELECT id FROM booking WHERE member_id = %s", (member_id,))
        existing = cursor.fetchone()

        # 假設有預定 → 更新預約資料
        if existing:
            cursor.execute("""
                UPDATE booking SET attraction_id=%s, date=%s, time=%s, price=%s
                WHERE member_id=%s          
            """, (booking.attractionId, booking.date, booking.time, booking.price, member_id))
        # 假設無預定 → 新增預約資料
        else:
             cursor.execute("""
                INSERT INTO booking (member_id, attraction_id, date, time, price)
                VALUES (%s, %s, %s, %s, %s)            
            """, (member_id, booking.attractionId, booking.date, booking.time, booking.price))
        db.commit()
        return {"ok": True}
    
    except Exception as e:
         print("預訂失敗:", e)
         return JSONResponse(status_code=500, content={"error": True, "message":"伺服器錯誤"})
    finally:
         cursor.close()
         db.close()
# 查詢預訂行程 API
@app.get("/api/booking")
def get_booking(Authorization: Optional[str] = Header(None)):
    if not Authorization:
          return {"data": None}
    try:
        #解析 JWT ，取得會員資料
        scheme, token = Authorization.split()
        if scheme.lower() != "bearer":
            return {"data": None}
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        member_id = payload["id"]
        member_name = payload["name"]
        member_email = payload["username"]

        # 連接資料庫
        db = cnxpool.get_connection()
        cursor = db.cursor(dictionary=True)

        # 查詢會員預訂資料 JOIN attractions 取得景點資料與圖片(name, address, image)
        cursor.execute("""
            SELECT
                b.date, b.time, b.price,
                a.id AS attraction_id, a.name, a.address,
                (SELECT url FROM images WHERE attraction_id = a.id LIMIT 1) AS image
            FROM booking b
            JOIN attractions a ON b.attraction_id = a.id
            WHERE b.member_id = %s
        """, (member_id,))
        result = cursor.fetchone()
        # 如果無預訂資料 回傳 null
        if not result:
             return {"data": None}
        # 如果有資料回傳 所需資料
        return {
            "data": {
                "attraction": {
                    "id": result["attraction_id"],
                    "name": result["name"],
                    "address": result["address"],
                    "image": result["image"]
                },
                "date": str(result["date"]),
                "time": result["time"],
                "price": result["price"],
                "contact": {
                    "name": member_name,
                    "email": member_email
                }
            }
        }
    except Exception as e:
        print("取得預定資料錯誤：", e)
        return JSONResponse(status_code=500, content={"error": True, "message": "伺服器錯誤"})

    finally:
        cursor.close()
        db.close()
# 刪除預訂行程 API
@app.delete("/api/booking")
def delete_booking(Authorization: Optional[str] = Header (None)):
    if not Authorization:
          return JSONResponse(status_code=403, content={"error": True, "message": "未登入使用者"})
    try:
        # 解析 JWT，取得會員資料
        scheme, token = Authorization.split()
        if scheme.lower() != "bearer":
            return JSONResponse(status_code=403, content={"error": True, "message": "授權格式錯誤"})
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        member_id = payload["id"]
        # 連接資料庫
        db = cnxpool.get_connection()
        cursor = db.cursor()
        #  刪除會員的預訂資料（
        cursor.execute("DELETE FROM booking WHERE member_id = %s", (member_id,))
        db.commit()

        #  回傳成功訊息
        return {"ok": True}
    
    except Exception as e:
        print("刪除預定失敗：", e)
        return JSONResponse(status_code=500, content={"error": True, "message": "伺服器錯誤"})

    finally:
        cursor.close()
        db.close()

# Order API 
@app.post("/api/orders")
def create_order(order_request: OrderRequest, Authorization: str = Header(None)):
    cursor = None
    db = None
    try:
        # JWT 驗證
        scheme, token = Authorization.split()
        if scheme.lower() != "bearer":
            return JSONResponse(status_code=403, content={"error": True, "message": "授權格式錯誤"})

        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        member_id = payload["id"]

        # 建立訂單號
        order_number = generate_order_number()

        # 資料庫連線
        db = cnxpool.get_connection()
        cursor = db.cursor()

        order = order_request.order
        contact = order_request.contact

        # Step 1 建立 UNPAID 訂單
        cursor.execute("""
            INSERT INTO orders (
                member_id, attraction_id, date, time, price,
                contact_name, contact_email, contact_phone,
                status, order_number
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'UNPAID', %s)
        """, (
            member_id, order.attractionId, order.date, order.time, order.price,
            contact.name, contact.email, contact.phone, order_number
        ))
        db.commit()

        # Step 2: 呼叫 TapPay 金流 API
        result = pay_by_prime(order_request.prime, order.price, contact.name, contact.email, contact.phone)

        # 如果付款成功 更新 orders table => 'PAID'
        if result["status"] == 0:
            rec_trade_id = result["rec_trade_id"]
            cursor.execute("""
                UPDATE orders SET status='PAID', tappay_rec_trade_id=%s
                WHERE order_number=%s
            """, (rec_trade_id, order_number))

            # 付款成功後刪除 booking 資料
            cursor.execute("DELETE FROM booking WHERE member_id = %s", (member_id,))
            db.commit()
            payment_success = True
        else:
            payment_success = False

        return {
            "data": {
                "number": order_number,
                "payment": payment_success
            }
        }
    except Exception as e:
        print("建立訂單失敗：", e)
        return JSONResponse(status_code=500, content={"error": True, "message": "伺服器錯誤"})

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()
# Member Avatar API
@app.post("/api/member/avatar")
def upload_avatar(
    avatar: UploadFile = File(...),
    Authorization: Optional[str] = Header(None)
):
    if not Authorization:
        return JSONResponse(status_code=403, content={"error": True, "message": "未登入使用者"})
    try:
        scheme, token = Authorization.split()
        if scheme.lower() != "bearer":
            return JSONResponse(status_code=403, content={"error": True, "message": "授權格式錯誤"})

        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        member_id = payload["id"]

        filename = avatar.filename
        if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
            return JSONResponse(status_code=400, content={"error": True, "message": "只支援 JPG/PNG 圖片格式"})

        ext = filename.split(".")[-1]
        saved_filename = f"member_{member_id}.{ext}"

        # 統一檔案命名，先刪除舊圖（不論副檔名）
        ext = filename.split(".")[-1].lower()
        saved_filename = f"member_{member_id}.{ext}"
        old_files = glob.glob(f"static/member_photos/member_{member_id}.*")
        for f in old_files:
            os.remove(f)

        saved_path = f"static/member_photos/{saved_filename}"

        # 儲存圖片
        avatar.file.seek(0)
        with open(saved_path, "wb") as buffer:
            buffer.write(avatar.file.read())

        # 回傳帶時間戳避免快取
        avatar_url = f"/static/member_photos/{saved_filename}?t={int(time.time())}"

        # 儲存圖片路徑到資料庫
        db = cnxpool.get_connection()
        cursor = db.cursor()
        cursor.execute("UPDATE member SET avatar_url = %s WHERE id = %s", (avatar_url, member_id))
        db.commit()
        cursor.close()
        db.close()

        return {
            "ok": True,
            "avatar_url": avatar_url
        }
    
    except Exception as e:
        print("上傳錯誤：", e)
        return JSONResponse(status_code=500, content={"error": True, "message": "伺服器錯誤"})
    
# Order History API
@app.get("/api/orders/history")
def get_order_history(
    page: int = Query(0, ge=0),
    size: int = Query(5, ge=1),
    Authorization: Optional[str] = Header(None)):

    if not Authorization:
        return {"data": [],"nextPage": None}

    try:
        # 驗證 JWT
        scheme, token = Authorization.split()
        if scheme.lower() != "bearer":
            return {"data": [], "nextPage": None}

        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        member_id = payload["id"]

        db = cnxpool.get_connection()
        cursor = db.cursor(dictionary=True)

        offset = page * size

        cursor.execute("""
            SELECT 
                o.order_number AS number,
                o.date,
                o.time,
                o.status,
                a.name AS attractionName,
                (SELECT url FROM images WHERE attraction_id = a.id LIMIT 1) AS attractionImage
            FROM orders o
            JOIN attractions a ON o.attraction_id = a.id
            WHERE o.member_id = %s
            ORDER BY o.id DESC
            LIMIT %s OFFSET %s
        """, (member_id, size, offset))

        orders = cursor.fetchall()
        # 計算總筆數
        cursor.execute("SELECT COUNT(*) AS total FROM orders WHERE member_id = %s", (member_id,))
        total = cursor.fetchone()["total"]

        next_page = page + 1 if offset + size < total else None

        return {"data": orders, "nextPage": next_page}

    except Exception as e:
        print("取得歷史訂單失敗：", e)
        return JSONResponse(status_code=500, content={"error": True, "message": "伺服器錯誤"})
    finally:
        if cursor: cursor.close()
        if db: db.close()

# Order UpdateName API

@app.patch("/api/user/name")
def update_user_name(data: UserUpdateName, Authorization: Optional[str] = Header(None)):
    if not Authorization:
        return JSONResponse(status_code=403, content={"error": True, "message": "未登入使用者"})

    db = None
    cursor = None
    try:
        scheme, token = Authorization.split()
        if scheme.lower() != "bearer":
            return JSONResponse(status_code=403, content={"error": True, "message": "授權格式錯誤"})

        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        member_id = payload["id"]


        # 驗證姓名有效性
        new_name = data.name.strip()
        if not new_name or len(new_name) < 2 or len(new_name) > 20:
            return JSONResponse(
                status_code=400,
                content={"error": True, "message": "請輸入有效的姓名（長度需在 2~20 字之間）"}
            )

        db = cnxpool.get_connection()
        cursor = db.cursor()
        
        cursor.execute("UPDATE member SET name = %s WHERE id = %s", (data.name, member_id))
        db.commit()

        # 產生新的 token 並回傳
        new_payload = {
            "id": payload["id"],
            "name": data.name,
            "username": payload["username"],
            "exp": int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp())
        }
        new_token = jwt.encode(new_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

        return {
            "ok": True,
            "token": new_token
        }
    except Exception as e:
        print("更新姓名錯誤：", e)
        return JSONResponse(status_code=500, content={"error": True, "message": "伺服器錯誤"})
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

# 設定靜態檔案資料夾
app.mount("/static", StaticFiles(directory="static"), name="static")