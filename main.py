from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import os
import jwt
import hashlib

import models
import schemas
from database import SessionLocal, engine

SECRET_KEY = "mysecretkey"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="圖書館座位預約系統")

os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)

templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password, hashed_password):
    return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password

def get_password_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def check_and_reduce_warnings(user: models.User, db: Session):
    if user.warning_count > 0 and user.last_warning_time:
        now = datetime.now()
        days_passed = (now - user.last_warning_time).days
        if days_passed >= 7:
            warnings_to_remove = days_passed // 7
            user.warning_count = max(0, user.warning_count - warnings_to_remove)
            user.last_warning_time = user.last_warning_time + timedelta(days=7 * warnings_to_remove)
            
            if user.banned_until and user.banned_until < now:
                user.banned_until = None
                
            db.commit()
    return user

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    
    check_and_reduce_warnings(user, db)
    return user

@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    seat_count = db.query(models.Seat).count()
    if seat_count == 0:
        for i in range(1, 11):
            db.add(models.Seat(name=f"座位 {i}"))
        db.commit()
    db.close()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})

@app.get("/admin", response_class=HTMLResponse)
async def read_admin(request: Request):
    return templates.TemplateResponse(request=request, name="admin.html", context={"request": request})

@app.get("/api/users", response_model=list[schemas.User])
def get_all_users(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="權限不足")
    users = db.query(models.User).all()
    for user in users:
        check_and_reduce_warnings(user, db)
    return users

@app.post("/api/register", response_model=schemas.User)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="此帳號已註冊")
    hashed_password = get_password_hash(user.password)
    is_admin = True if user.username.lower() == "admin" else False
    db_user = models.User(username=user.username, hashed_password=hashed_password, is_admin=is_admin)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/api/login", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="帳號或密碼錯誤")
    
    check_and_reduce_warnings(user, db)
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "is_admin": user.is_admin}, 
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/me", response_model=schemas.User)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user

@app.get("/api/seats", response_model=list[schemas.Seat])
def read_seats(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    seats = db.query(models.Seat).offset(skip).limit(limit).all()
    return seats

@app.post("/api/bookings", response_model=schemas.Booking)
def create_booking(booking: schemas.BookingCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = datetime.now()
    
    if current_user.banned_until and current_user.banned_until > now:
        raise HTTPException(status_code=403, detail=f"您已被停權直到 {current_user.banned_until.strftime('%Y-%m-%d %H:%M')}")
    
    if booking.start_time <= now:
        raise HTTPException(status_code=400, detail="必須預約未來時間")
    if booking.start_time > now + timedelta(days=7):
        raise HTTPException(status_code=400, detail="只能預約未來一週內的時間")
        
    if booking.start_time.hour < 8 or booking.end_time.hour > 20 or (booking.end_time.hour == 20 and booking.end_time.minute > 0):
        raise HTTPException(status_code=400, detail="預約時間必須在早上 8 點至晚上 8 點之間")
    
    if booking.start_time.minute != 0 or booking.start_time.second != 0:
        raise HTTPException(status_code=400, detail="預約時間必須是整點 (例如 09:00)")
    if booking.end_time.minute != 0 or booking.end_time.second != 0:
        raise HTTPException(status_code=400, detail="結束時間必須是整點 (例如 10:00)")
        
    duration = (booking.end_time - booking.start_time).total_seconds()
    if duration <= 0 or duration % 3600 != 0:
        raise HTTPException(status_code=400, detail="每次預約時間單位必須為一小時")

    overlapping_booking = db.query(models.Booking).filter(
        models.Booking.seat_id == booking.seat_id,
        models.Booking.start_time < booking.end_time,
        models.Booking.end_time > booking.start_time
    ).first()
    
    if overlapping_booking:
        raise HTTPException(status_code=400, detail="此時段該座位已被預約")
        
    db_booking = models.Booking(**booking.model_dump(), user_name=current_user.username)
    db.add(db_booking)
    db.commit()
    db.refresh(db_booking)
    return db_booking

@app.get("/api/bookings", response_model=list[schemas.Booking])
def read_bookings(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    bookings = db.query(models.Booking).offset(skip).limit(limit).all()
    return bookings
    
@app.delete("/api/bookings/{booking_id}")
def delete_booking(booking_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="找不到此預約")
        
    if booking.user_name != current_user.username and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="您只能取消自己的預約")
        
    now = datetime.now()
    if not current_user.is_admin:
        if (booking.start_time - now).total_seconds() < 3600:
            raise HTTPException(status_code=400, detail="距離預約時間小於1小時，無法取消")
            
    db.delete(booking)
    db.commit()
    return {"message": "預約已取消"}

@app.post("/api/users/{username}/warn")
def warn_user(username: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="只有管理員可以進行記點")
        
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="找不到使用者")
        
    now = datetime.now()
    user.warning_count += 1
    user.last_warning_time = now
    
    if user.warning_count >= 3:
        user.banned_until = now + timedelta(days=3)
        # Delete future bookings
        db.query(models.Booking).filter(
            models.Booking.user_name == user.username,
            models.Booking.start_time > now
        ).delete()
        
    db.commit()
    return {"message": f"已給予 {username} 警告，目前累積 {user.warning_count} 次"}
