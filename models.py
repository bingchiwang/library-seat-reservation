from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_admin = Column(Boolean, default=False)
    warning_count = Column(Integer, default=0)
    last_warning_time = Column(DateTime, nullable=True)
    banned_until = Column(DateTime, nullable=True)

class Seat(Base):
    __tablename__ = "seats"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True) 
    
    bookings = relationship("Booking", back_populates="seat")

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    user_name = Column(String, index=True)
    seat_id = Column(Integer, ForeignKey("seats.id"))
    start_time = Column(DateTime)
    end_time = Column(DateTime)

    seat = relationship("Seat", back_populates="bookings")
