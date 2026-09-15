from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserCreate(BaseModel):
    username: str
    password: str

class User(BaseModel):
    id: int
    username: str
    
    class Config:
        from_attributes = True

class BookingBase(BaseModel):
    start_time: datetime
    end_time: datetime

class BookingCreate(BookingBase):
    seat_id: int

class Booking(BookingBase):
    id: int
    seat_id: int
    user_name: str

    class Config:
        from_attributes = True

class SeatBase(BaseModel):
    name: str

class SeatCreate(SeatBase):
    pass

class Seat(SeatBase):
    id: int
    bookings: List[Booking] = []

    class Config:
        from_attributes = True
