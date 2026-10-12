from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from database import Base


class StaffUser(Base):
    """A WASAC staff member who can sign in to the staff dashboard."""

    __tablename__ = "staff_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="officer")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
