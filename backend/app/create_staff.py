from getpass import getpass
from datetime import datetime, timezone

from sqlalchemy import select

from app.api.auth import normalize_phone
from app.core.database import SessionLocal
from app.core.security import password_hash
from app.models import Permission, Role, User


ROLE_PERMISSIONS = {
    "manager": {
        "dashboard:read", "customer:read", "customer:create", "customer:lookup", "service:manage",
        "order:read", "order:create", "order:verify", "order:confirm", "order:status", "order:delivery",
        "garment:write", "garment:photo", "payment:read", "payment:record", "refund:record",
        "expense:read", "expense:write", "analytics:read", "report:export", "closing:read", "closing:write",
        "notification:read", "notification:send",
    },
    "order_staff": {
        "dashboard:read", "customer:read", "customer:create", "customer:lookup", "order:read", "order:create",
        "order:verify", "order:confirm", "order:status", "order:delivery", "garment:write", "garment:photo",
        "notification:read", "notification:send",
    },
    "finance_staff": {
        "dashboard:read", "payment:read", "payment:record", "refund:record", "expense:read", "expense:write",
        "analytics:read", "report:export", "closing:read", "closing:write",
    },
}


def main() -> None:
    phone = normalize_phone(input("Staff mobile number: ").strip())
    role_name = input("Role (manager, order_staff, finance_staff): ").strip().lower()
    permissions_to_grant = ROLE_PERMISSIONS.get(role_name)
    if permissions_to_grant is None:
        raise SystemExit("Choose manager, order_staff, or finance_staff.")
    pin = getpass("Choose a 6-12 digit staff PIN: ").strip()
    if not pin.isdigit() or not 6 <= len(pin) <= 12:
        raise SystemExit("PIN must contain 6 to 12 digits.")
    if getpass("Enter the PIN again: ").strip() != pin:
        raise SystemExit("PINs did not match.")

    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.phone == phone)):
            raise SystemExit("An account already uses that mobile number. No changes were made.")
        role = db.scalar(select(Role).where(Role.name == role_name))
        if role is None:
            role = Role(name=role_name)
        permissions = []
        for code in sorted(permissions_to_grant):
            permission = db.scalar(select(Permission).where(Permission.code == code))
            if permission is None:
                permission = Permission(code=code)
            permissions.append(permission)
        role.permissions = permissions
        staff = User(
            phone=phone,
            pin_hash=password_hash.hash(pin),
            account_type="staff",
            phone_verified_at=datetime.now(timezone.utc),
            roles=[role],
        )
        db.add(staff)
        db.commit()
    print(f"Staff account created with role: {role_name}.")


if __name__ == "__main__":
    main()
