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

# Constants for auth
SECRET_KEY = "mysecretkey"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="圖書館座位預約系統")

os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)

templates = Jinja2Templates(directory="templates")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Auth utils
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
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

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
        token_data = schemas.TokenData(username=username)
    except jwt.PyJWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
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

@app.post("/api/register", response_model=schemas.User)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="此帳號已註冊")
    hashed_password = get_password_hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/api/login", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="帳號或密碼錯誤",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/seats", response_model=list[schemas.Seat])
def read_seats(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    seats = db.query(models.Seat).offset(skip).limit(limit).all()
    return seats

@app.post("/api/bookings", response_model=schemas.Booking)
def create_booking(booking: schemas.BookingCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
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
    if booking.user_name != current_user.username:
        raise HTTPException(status_code=403, detail="您只能取消自己的預約")
    db.delete(booking)
    db.commit()
    return {"message": "預約已取消"}
