from sqlalchemy.orm import Session
from datetime import datetime
import models
import schemas

class UserRepository:
    @staticmethod
    def get_by_username(db: Session, username: str) -> models.User | None:
        return db.query(models.User).filter(models.User.username == username).first()

    @staticmethod
    def create(db: Session, username: str, hashed_password: str, is_admin: bool) -> models.User:
        db_user = models.User(username=username, hashed_password=hashed_password, is_admin=is_admin)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    @staticmethod
    def get_all(db: Session) -> list[models.User]:
        return db.query(models.User).all()

    @staticmethod
    def update(db: Session, user: models.User):
        db.commit()
        db.refresh(user)


class SeatRepository:
    @staticmethod
    def get_all(db: Session) -> list[models.Seat]:
        return db.query(models.Seat).all()

    @staticmethod
    def count(db: Session) -> int:
        return db.query(models.Seat).count()

    @staticmethod
    def create_defaults(db: Session):
        for i in range(1, 11):
            db.add(models.Seat(name=f"座位 {i}"))
        db.commit()


class BookingRepository:
    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 100) -> list[models.Booking]:
        return db.query(models.Booking).offset(skip).limit(limit).all()

    @staticmethod
    def get_by_id(db: Session, booking_id: int) -> models.Booking | None:
        return db.query(models.Booking).filter(models.Booking.id == booking_id).first()

    @staticmethod
    def get_overlapping(db: Session, seat_id: int, start_time: datetime, end_time: datetime) -> models.Booking | None:
        return db.query(models.Booking).filter(
            models.Booking.seat_id == seat_id,
            models.Booking.start_time < end_time,
            models.Booking.end_time > start_time
        ).first()

    @staticmethod
    def create(db: Session, booking_data: schemas.BookingCreate, username: str) -> models.Booking:
        db_booking = models.Booking(**booking_data.model_dump(), user_name=username)
        db.add(db_booking)
        db.commit()
        db.refresh(db_booking)
        return db_booking

    @staticmethod
    def delete(db: Session, booking: models.Booking):
        db.delete(booking)
        db.commit()

    @staticmethod
    def delete_future_bookings_for_user(db: Session, username: str, after_time: datetime):
        db.query(models.Booking).filter(
            models.Booking.user_name == username,
            models.Booking.start_time > after_time
        ).delete()
        db.commit()
