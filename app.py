from fastapi import FastAPI, Query, Request, Header
from fastapi.responses import FileResponse, JSONResponse
import json
import mysql.connector
import re
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
app=FastAPI()


# JWT 設定
JWT_SECRET = "12345678"
JWT_ALGORITHM = "HS256"

# 設置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],  # 允許所有 HTTP 方法
    allow_headers=["*"],  # 允許所有標頭
)

# 連接 MySQL
db = mysql.connector.connect(
	host="127.0.0.1",
	user="root",
	password="12345678",
	database="taipei_attractions"
)
cursor = db.cursor()

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
        db = mysql.connector.connect(
            host="127.0.0.1",
            user="root",
            password="12345678",
            database="taipei_attractions"
        )
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
        db = mysql.connector.connect(
            host="127.0.0.1",
            user="root",
            password="12345678",
            database="taipei_attractions"
        )
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
        db = mysql.connector.connect(
            host="127.0.0.1",
            user="root",
            password="12345678",
            database="taipei_attractions"
        )
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
        db = mysql.connector.connect(
            host="127.0.0.1",
            user="root",
            password="12345678",
            database="taipei_attractions"
        )
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
          db = mysql.connector.connect (
               host="127.0.0.1",
               user="root",
               password="12345678",
               database="taipei_attractions"
          )
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
        db = mysql.connector.connect (
               host="127.0.0.1",
               user="root",
               password="12345678",
               database="taipei_attractions"
        )
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
        return {"data": {
             "id": payload["id"],
             "name": payload["name"],
             "username": payload["username"]
        }}
    except Exception:
         # 解碼失敗，代表未登入
        return {"data": None}
# 設定靜態檔案資料夾
app.mount("/static", StaticFiles(directory="static"), name="static")