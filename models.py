from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

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
