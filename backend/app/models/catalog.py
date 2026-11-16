import uuid

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class ServiceCategory(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "service_categories"

    name_en: Mapped[str] = mapped_column(String(100))
    name_te: Mapped[str] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    services: Mapped[list["Service"]] = relationship(back_populates="category")


class Service(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "services"

    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_categories.id", ondelete="RESTRICT"), index=True)
    name_en: Mapped[str] = mapped_column(String(120))
    name_te: Mapped[str] = mapped_column(String(120))
    description_en: Mapped[str] = mapped_column(Text, default="")
    description_te: Mapped[str] = mapped_column(Text, default="")
    price_paise: Mapped[int] = mapped_column(Integer)
    # A zero price is only an internal placeholder when quotation_required is true.
    # API views must expose that state as null so customers never see a fake price.
    garment_type: Mapped[str | None] = mapped_column(String(100))
    quotation_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    price_is_starting: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    additional_charge_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pricing_unit: Mapped[str] = mapped_column(String(30), default="per garment")
    turnaround_days: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    category: Mapped[ServiceCategory] = relationship(back_populates="services")
