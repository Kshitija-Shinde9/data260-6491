from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


SUPPLIER_CODE_PATTERN = r"^SUP-[0-9]{4}$"
RECALL_CODE_PATTERN = r"^REC-[0-9]{4}$"


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    headquarters: str = Field(min_length=1, max_length=255)
    supplier_code: str = Field(pattern=SUPPLIER_CODE_PATTERN)


class SupplierUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    headquarters: Optional[str] = Field(default=None, min_length=1, max_length=255)
    supplier_code: Optional[str] = Field(default=None, pattern=SUPPLIER_CODE_PATTERN)


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    headquarters: str
    supplier_code: str
    created_at: datetime
    updated_at: datetime


class RecallCreate(BaseModel):
    product_name: str = Field(min_length=1, max_length=255)
    recall_code: str = Field(pattern=RECALL_CODE_PATTERN)
    supplier_id: int
    affected_units: int = Field(default=0, ge=0)
    email: str = ""
    description: str = ""
    recall_type: str = ""


class RecallUpdate(BaseModel):
    product_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    recall_code: Optional[str] = Field(default=None, pattern=RECALL_CODE_PATTERN)
    supplier_id: Optional[int] = None
    affected_units: Optional[int] = Field(default=None, ge=0)
    email: Optional[str] = None
    description: Optional[str] = None
    recall_type: Optional[str] = None


class RecallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_name: str
    recall_code: str
    affected_units: int
    supplier_id: int
    email: str = ""
    description: str = ""
    recall_type: str = ""
    created_at: datetime
    updated_at: datetime