from getpass import getpass
from datetime import datetime, timezone

from sqlalchemy import select

from app.api.auth import normalize_phone
from app.core.database import SessionLocal
from app.core.security import password_hash
from app.models import Permission, Role, User


PERMISSIONS = {
    "dashboard:read",
    "customer:read",
    "customer:create",
    "customer:manage",
    "customer:lookup",
    "service:manage",
    "order:read",
    "order:create",
    "order:verify",
    "order:confirm",
    "order:status",
    "order:delivery",
    "garment:write",
    "garment:photo",
    "payment:read",
    "payment:record",
    "refund:record",
    "expense:read",
    "expense:write",
    "analytics:read",
    "report:export",
    "closing:read",
    "closing:write",
    "notification:read",
    "notification:send",
    "settings:manage",
    "backup:export",
}


def main() -> None:
    phone = normalize_phone(input("Owner mobile number: ").strip())
    pin = getpass("Choose a 6-12 digit owner PIN: ").strip()
    if not pin.isdigit() or not 6 <= len(pin) <= 12:
        raise SystemExit("PIN must contain 6 to 12 digits.")
    confirmation = getpass("Enter the PIN again: ").strip()
    if confirmation != pin:
        raise SystemExit("PINs did not match.")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.phone == phone))
        if user is not None:
            raise SystemExit("An account already uses that mobile number. No changes were made.")

        permissions = []
        for code in sorted(PERMISSIONS):
            permission = db.scalar(select(Permission).where(Permission.code == code))
            if permission is None:
                permission = Permission(code=code)
                db.add(permission)
            permissions.append(permission)
        owner_role = db.scalar(select(Role).where(Role.name == "owner"))
        if owner_role is None:
            owner_role = Role(name="owner")
        owner_role.permissions = permissions
        owner = User(
            phone=phone,
            pin_hash=password_hash.hash(pin),
            account_type="staff",
            phone_verified_at=datetime.now(timezone.utc),
            active=True,
        )
        owner.roles.append(owner_role)
        db.add_all([owner_role, owner])
        db.commit()
    print("Owner account created. Sign in from the staff login page.")


if __name__ == "__main__":
    main()
