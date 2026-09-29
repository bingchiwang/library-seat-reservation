from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import os

import models
import schemas
from database import SessionLocal, engine
from facade import LibraryFacade

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

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    return LibraryFacade.get_user_from_token(token, db)

@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    if db.query(models.Seat).count() == 0:
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

@app.post("/api/register", response_model=schemas.User)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    return LibraryFacade.register_user(user, db)

@app.post("/api/login", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    access_token = LibraryFacade.authenticate_user(form_data.username, form_data.password, db)
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/me", response_model=schemas.User)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user

@app.get("/api/users", response_model=list[schemas.User])
def get_all_users(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return LibraryFacade.get_all_users(current_user, db)

@app.get("/api/seats", response_model=list[schemas.Seat])
def read_seats(db: Session = Depends(get_db)):
    return LibraryFacade.get_all_seats(db)

@app.post("/api/bookings", response_model=schemas.Booking)
def create_booking(booking: schemas.BookingCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return LibraryFacade.book_seat(current_user, booking, db)

@app.get("/api/bookings", response_model=list[schemas.Booking])
def read_bookings(db: Session = Depends(get_db)):
    return LibraryFacade.get_all_bookings(db)
    
@app.delete("/api/bookings/{booking_id}")
def delete_booking(booking_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    LibraryFacade.cancel_booking(current_user, booking_id, db)
    return {"message": "預約已取消"}

@app.post("/api/users/{username}/warn")
def warn_user(username: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = LibraryFacade.warn_user(current_user, username, db)
    return {"message": f"已給予 {username} 警告，目前累積 {user.warning_count} 次"}
