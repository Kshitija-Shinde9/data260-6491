from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from database import Base


class Recall(Base):
    __tablename__ = "recalls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_name = Column(String(255), nullable=False)
    supplier = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True, default="")
    description = Column(String(2000), nullable=True, default="")
    recall_type = Column(String(100), nullable=True, default="")

    notes = relationship("RecallNote")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)

    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="sessions")

class RecallNote(Base):
    __tablename__ = "recall_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recall_id = Column(Integer, ForeignKey("recalls.id"), nullable=False)
    note = Column(String(500), nullable=False)
    created_at = Column(DateTime, nullable=False)