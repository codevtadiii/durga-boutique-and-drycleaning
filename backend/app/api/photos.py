import io
import uuid
import warnings
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, require_customer, require_permission, require_same_origin
from app.api.schemas import PhotoView
from app.core.config import get_settings
from app.models import AuditLog, Garment, Order, OrderItem, UploadedFile, User

staff_router = APIRouter(prefix="/api/v1/staff", tags=["garment photos"])
customer_router = APIRouter(prefix="/api/v1/customer", tags=["garment photos"])
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 20_000_000


def _open_as_webp(raw: bytes) -> bytes:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, or WebP photo")
                image.verify()
            with Image.open(io.BytesIO(raw)) as image:
                clean = ImageOps.exif_transpose(image).convert("RGB")
                output = io.BytesIO()
                clean.save(output, format="WEBP", quality=84, method=4)
                return output.getvalue()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid supported photo") from error


def _photo_query(db: Session, garment_id: uuid.UUID, file_id: uuid.UUID):
    return db.scalar(
        select(UploadedFile)
        .join(Garment, Garment.id == UploadedFile.garment_id)
        .where(Garment.id == garment_id, UploadedFile.id == file_id, UploadedFile.purpose == "intake_photo")
    )


def _file_path(storage_key: str) -> Path:
    root = Path(get_settings().media_root).resolve()
    path = (root / storage_key).resolve()
    if root not in path.parents:
        raise HTTPException(status_code=404, detail="Photo was not found")
    return path


async def _save_photo(garment_id: uuid.UUID, upload: UploadFile, actor: User, db: Session) -> PhotoView:
    raw = await upload.read(MAX_UPLOAD_BYTES + 1)
    if not raw or len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Photos must be 5 MB or smaller")
    webp = _open_as_webp(raw)
    file_id = uuid.uuid4()
    storage_key = f"intake/{file_id}.webp"
    path = _file_path(storage_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(webp)

    record = UploadedFile(
        id=file_id,
        garment_id=garment_id,
        storage_key=storage_key,
        content_type="image/webp",
        size_bytes=len(webp),
        purpose="intake_photo",
    )
    db.add(record)
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="garment.intake_photo.added",
            entity_type="garment",
            entity_id=garment_id,
            before_after_summary={"file_id": str(file_id), "size_bytes": len(webp)},
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    return PhotoView(id=file_id, garment_id=garment_id, content_type="image/webp", size_bytes=len(webp))


@staff_router.post(
    "/garments/{garment_id}/photos",
    response_model=PhotoView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_same_origin)],
)
async def add_intake_photo(
    garment_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("garment:photo")),
) -> PhotoView:
    if db.get(Garment, garment_id) is None:
        raise HTTPException(status_code=404, detail="Garment was not found")
    return await _save_photo(garment_id, file, actor, db)


@staff_router.get("/garments/{garment_id}/photos/{file_id}")
def get_staff_intake_photo(
    garment_id: uuid.UUID,
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("garment:photo")),
) -> FileResponse:
    record = _photo_query(db, garment_id, file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Photo was not found")
    path = _file_path(record.storage_key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Photo file is unavailable")
    return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@customer_router.get("/orders/{order_id}/garments/{garment_id}/photos/{file_id}")
def get_customer_intake_photo(
    order_id: uuid.UUID,
    garment_id: uuid.UUID,
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_customer),
) -> FileResponse:
    record = db.scalar(
        select(UploadedFile)
        .join(Garment, Garment.id == UploadedFile.garment_id)
        .join(OrderItem, OrderItem.id == Garment.order_item_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            UploadedFile.id == file_id,
            Garment.id == garment_id,
            Order.id == order_id,
            Order.customer_id == user.customer.id,
            UploadedFile.purpose == "intake_photo",
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Photo was not found")
    path = _file_path(record.storage_key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Photo file is unavailable")
    return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
