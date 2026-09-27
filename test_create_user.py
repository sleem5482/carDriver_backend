import uuid
import traceback
from app.database import SessionLocal
from app.schemas.user import UserCreate
from app.routers.admin_users import create_user
from app.models.user import UserRole, UserStatus

db = SessionLocal()
try:
    # We need a mock admin user
    from app.models.user import User
    admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
    if not admin:
        print("No admin found in db, creating one for test")
        admin = User(
            full_name="admin",
            mobile_number="0000000000",
            email="admin@test.com",
            hashed_password="x",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE
        )
        db.add(admin)
        db.flush()

    body = UserCreate(
        full_name="string",
        mobile_number="string123", # Make unique just in case
        email="UN73oaX123@kuDyXzOdgsfyZ.lsar",
        status=UserStatus.ACTIVE,
        notes="string",
        vehicle_id=None # Let's test without vehicle_id first
    )

    print("Calling create_user...")
    result = create_user(body=body, db=db, admin=admin)
    print("Success:", result)
    db.rollback()

except Exception as e:
    db.rollback()
    traceback.print_exc()
finally:
    db.close()
