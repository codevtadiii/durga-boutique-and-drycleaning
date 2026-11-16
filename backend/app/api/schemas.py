from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LoginInput(BaseModel):
    phone: str = Field(min_length=10, max_length=20)
    pin: str = Field(min_length=6, max_length=12, pattern=r"^\d+$")


class RegistrationRequestInput(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    phone: str = Field(min_length=10, max_length=20)
    preferred_language: Literal["en", "te"] = "en"
    whatsapp_order_updates: bool = False
    whatsapp_marketing: bool = False


class CustomerCreateInput(RegistrationRequestInput):
    pin: str = Field(min_length=6, max_length=12, pattern=r"^\d+$")


class PinResetInput(BaseModel):
    pin: str = Field(min_length=6, max_length=12, pattern=r"^\d+$")


class RegistrationApproveInput(BaseModel):
    pin: str = Field(min_length=6, max_length=12, pattern=r"^\d+$")


class CustomerProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    phone: str
    preferred_language: str


class RegistrationRequestView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    phone: str
    preferred_language: str
    status: str
    created_at: datetime


class PhotoView(BaseModel):
    id: UUID
    garment_id: UUID
    content_type: str
    size_bytes: int
