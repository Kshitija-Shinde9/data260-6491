from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class NoticeStatus(str, Enum):
    reported = "reported"
    investigating = "investigating"
    resolved = "resolved"


class RecallType(str, Enum):
    packaging = "Packaging / Seal Failure"
    contamination = "Contamination"
    allergen = "Undeclared Allergen"
    quality = "Spoiled or Quality Issue"


class NoticeCreate(BaseModel):
    product_name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=2000)
    status: NoticeStatus = NoticeStatus.reported
    recall_type: RecallType
    noticed_at: datetime


class NoticeUpdate(BaseModel):
    product_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[NoticeStatus] = None
    recall_type: Optional[RecallType] = None
    noticed_at: Optional[datetime] = None


class NoticeOut(BaseModel):
    id: str
    product_name: str
    description: Optional[str] = None
    status: NoticeStatus
    recall_type: RecallType
    noticed_at: datetime
    created_at: datetime
    updated_at: datetime
