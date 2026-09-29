from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import hashlib
import jwt
from fastapi import HTTPException

import models
import schemas

SECRET_KEY = "mysecretkey"
ALGORITHM = "HS256"

class LibraryFacade:
    """
    Facade class that hides the complex business logic of the library system.
    """

    @staticmethod
    def _verify_password(plain_password: str, hashed_password: str) -> bool:
        return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password

    @staticmethod
    def _get_password_hash(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def register_user(user_data: schemas.UserCreate, db: Session) -> models.User:
        db_user = db.query(models.User).filter(models.User.username == user_data.username).first()
        if db_user:
            raise HTTPException(status_code=400, detail="此帳號已註冊")
        
        hashed_password = LibraryFacade._get_password_hash(user_data.password)
        is_admin = True if user_data.username.lower() == "admin" else False
        
        new_user = models.User(username=user_data.username, hashed_password=hashed_password, is_admin=is_admin)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user

    @staticmethod
    def authenticate_user(username: str, password: str, db: Session) -> str:
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user or not LibraryFacade._verify_password(password, user.hashed_password):
            raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
        
        LibraryFacade.check_and_reduce_warnings(user, db)
        
        expire = datetime.utcnow() + timedelta(minutes=60 * 24)
        to_encode = {"sub": user.username, "is_admin": user.is_admin, "exp": expire}
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def get_user_from_token(token: str, db: Session) -> models.User:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if not username:
                raise HTTPException(status_code=401, detail="無效的憑證")
        except jwt.PyJWTError:
            raise HTTPException(status_code=401, detail="憑證驗證失敗")
            
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user:
            raise HTTPException(status_code=401, detail="找不到使用者")
            
        LibraryFacade.check_and_reduce_warnings(user, db)
        return user

    @staticmethod
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

    @staticmethod
    def get_all_users(admin_user: models.User, db: Session) -> list[models.User]:
        if not admin_user.is_admin:
            raise HTTPException(status_code=403, detail="權限不足")
        users = db.query(models.User).all()
        for u in users:
            LibraryFacade.check_and_reduce_warnings(u, db)
        return users

    @staticmethod
    def get_all_seats(db: Session) -> list[models.Seat]:
        return db.query(models.Seat).all()

    @staticmethod
    def get_all_bookings(db: Session) -> list[models.Booking]:
        return db.query(models.Booking).all()

    @staticmethod
    def book_seat(user: models.User, booking_data: schemas.BookingCreate, db: Session) -> models.Booking:
        now = datetime.now()
        
        if user.banned_until and user.banned_until > now:
            raise HTTPException(status_code=403, detail=f"您已被停權直到 {user.banned_until.strftime('%Y-%m-%d %H:%M')}")
        
        if booking_data.start_time <= now:
            raise HTTPException(status_code=400, detail="必須預約未來時間")
        if booking_data.start_time > now + timedelta(days=7):
            raise HTTPException(status_code=400, detail="只能預約未來一週內的時間")
            
        if booking_data.start_time.hour < 8 or booking_data.end_time.hour > 20 or (booking_data.end_time.hour == 20 and booking_data.end_time.minute > 0):
            raise HTTPException(status_code=400, detail="預約時間必須在早上 8 點至晚上 8 點之間")
        
        if booking_data.start_time.minute != 0 or booking_data.start_time.second != 0 or booking_data.end_time.minute != 0 or booking_data.end_time.second != 0:
            raise HTTPException(status_code=400, detail="時間必須是整點 (例如 09:00)")
            
        duration = (booking_data.end_time - booking_data.start_time).total_seconds()
        if duration <= 0 or duration % 3600 != 0:
            raise HTTPException(status_code=400, detail="每次預約時間單位必須為一小時")

        overlapping_booking = db.query(models.Booking).filter(
            models.Booking.seat_id == booking_data.seat_id,
            models.Booking.start_time < booking_data.end_time,
            models.Booking.end_time > booking_data.start_time
        ).first()
        
        if overlapping_booking:
            raise HTTPException(status_code=400, detail="此時段該座位已被預約")
            
        db_booking = models.Booking(**booking_data.model_dump(), user_name=user.username)
        db.add(db_booking)
        db.commit()
        db.refresh(db_booking)
        return db_booking

    @staticmethod
    def cancel_booking(user: models.User, booking_id: int, db: Session):
        booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
        if not booking:
            raise HTTPException(status_code=404, detail="找不到此預約")
            
        if booking.user_name != user.username and not user.is_admin:
            raise HTTPException(status_code=403, detail="您只能取消自己的預約")
            
        if not user.is_admin:
            if (booking.start_time - datetime.now()).total_seconds() < 3600:
                raise HTTPException(status_code=400, detail="距離預約時間小於1小時，無法取消")
                
        db.delete(booking)
        db.commit()
        return True

    @staticmethod
    def warn_user(admin_user: models.User, target_username: str, db: Session):
        if not admin_user.is_admin:
            raise HTTPException(status_code=403, detail="只有管理員可以進行記點")
            
        user = db.query(models.User).filter(models.User.username == target_username).first()
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
        return user
