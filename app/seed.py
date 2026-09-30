"""
Seed script — creates an initial admin user for development.

Usage:
    python -m app.seed
"""

from app.database import SessionLocal, engine, Base
from app.models.user import User, UserRole, UserStatus
from app.services.auth_service import hash_password


def seed():
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Check if admin already exists
        existing = db.query(User).filter(User.role == UserRole.ADMIN).first()
        if existing:
            print(f"Admin already exists: {existing.email} / {existing.mobile_number}")
            return

        admin = User(
            full_name="System Admin",
            mobile_number="+201000000000",
            email="admin@cardriver.com",
            hashed_password=hash_password("admin123"),
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
            notes="Default admin account — change password immediately.",
        )
        db.add(admin)
        db.commit()
        print(f"[SUCCESS] Admin created: phone={admin.mobile_number}, password=admin123")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
