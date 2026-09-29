import os
from datetime import datetime
from sqlalchemy.orm import Session
import models
from database import engine, SessionLocal
import hashlib

def get_password_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()

def seed_db():
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # 建立座位
    if db.query(models.Seat).count() == 0:
        for i in range(1, 11):
            db.add(models.Seat(name=f"座位 {i}"))
    
    # 建立管理員 (admin)
    if not db.query(models.User).filter(models.User.username == "admin").first():
        db.add(models.User(
            username="admin", 
            hashed_password=get_password_hash("admin"), 
            is_admin=True
        ))
        
    # 建立一般使用者 (user1)
    user1 = db.query(models.User).filter(models.User.username == "user1").first()
    if not user1:
        user1 = models.User(
            username="user1", 
            hashed_password=get_password_hash("user1"), 
            is_admin=False,
            warning_count=1,
            last_warning_time=datetime.now()
        )
        db.add(user1)
    else:
        user1.warning_count = 1
        user1.last_warning_time = datetime.now()
        
    db.commit()
    db.close()
    print("Database seeded successfully!")

if __name__ == "__main__":
    seed_db()
