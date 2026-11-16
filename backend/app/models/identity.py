import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Table, Column, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "permission_id",
        Uuid(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class User(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "users"

    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(254), unique=True)
    pin_hash: Mapped[str | None] = mapped_column(String(255))
    account_type: Mapped[str] = mapped_column(String(20), default="customer", index=True)
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    customer: Mapped["Customer | None"] = relationship(back_populates="user", uselist=False)
    roles: Mapped[list["Role"]] = relationship(secondary=user_roles, back_populates="users")
    sessions: Mapped[list["AuthSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Role(UUIDPrimaryKey, Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(40), unique=True)
    users: Mapped[list[User]] = relationship(secondary=user_roles, back_populates="roles")
    permissions: Mapped[list["Permission"]] = relationship(secondary=role_permissions, back_populates="roles")


class Permission(UUIDPrimaryKey, Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(80), unique=True)
    roles: Mapped[list[Role]] = relationship(secondary=role_permissions, back_populates="permissions")


class AuthSession(UUIDPrimaryKey, Base):
    __tablename__ = "auth_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="sessions")


class LoginAttempt(UUIDPrimaryKey, Base):
    __tablename__ = "login_attempts"
    __table_args__ = (Index("ix_login_attempts_client_time", "client_hash", "occurred_at"),)

    phone_hash: Mapped[str] = mapped_column(String(64), index=True)
    client_hash: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    succeeded: Mapped[bool] = mapped_column(Boolean, default=False)


class Customer(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "customers"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), unique=True)
    full_name: Mapped[str] = mapped_column(String(160))
    preferred_language: Mapped[str] = mapped_column(String(5), default="en", server_default="en")

    user: Mapped[User] = relationship(back_populates="customer")
    addresses: Mapped[list["CustomerAddress"]] = relationship(back_populates="customer", cascade="all, delete-orphan")
    qr_tokens: Mapped[list["CustomerQrToken"]] = relationship(back_populates="customer", cascade="all, delete-orphan")
    notification_preferences: Mapped["NotificationPreference | None"] = relationship(
        back_populates="customer", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def phone(self) -> str:
        return self.user.phone


class CustomerAddress(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "customer_addresses"

    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(40), default="Home")
    address: Mapped[str] = mapped_column(String(500))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    customer: Mapped[Customer] = relationship(back_populates="addresses")


class CustomerQrToken(UUIDPrimaryKey, Base):
    __tablename__ = "customer_qr_tokens"

    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    customer: Mapped[Customer] = relationship(back_populates="qr_tokens")


class RegistrationRequest(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "registration_requests"
    __table_args__ = (Index("ix_registration_requests_phone_created", "phone", "created_at"),)

    full_name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(20))
    preferred_language: Mapped[str] = mapped_column(String(5), default="en")
    whatsapp_order_updates: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    whatsapp_marketing: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    consent_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
