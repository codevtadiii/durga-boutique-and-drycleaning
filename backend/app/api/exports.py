import json
import tempfile
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission, require_same_origin
from app.core.config import get_settings
from app.core.database import Base, engine
from app.models import AuditLog, DataExport, User

router = APIRouter(prefix="/api/v1/staff/data-exports", tags=["data exports"])
EXPORT_TTL_DAYS = 7
EXCLUDED_ROW_TABLES = {"auth_sessions", "login_attempts"}
REDACTED_FIELDS = {"users": {"pin_hash"}, "customer_qr_tokens": {"token_hash"}}


def _export_path(storage_key: str) -> Path:
    root = Path(get_settings().media_root).resolve()
    path = (root / storage_key).resolve()
    if root not in path.parents:
        raise HTTPException(status_code=404, detail="Export was not found")
    return path


def _json_rows(staging: Path, table, counts: dict[str, int], connection) -> None:
    count = 0
    with (staging / f"{table.name}.json").open("w", encoding="utf-8", newline="") as text_file:
        text_file.write("[\n")
        rows = connection.execution_options(yield_per=1000).execute(select(table)).mappings()
        for row in rows:
            if table.name in EXCLUDED_ROW_TABLES:
                continue
            if count:
                text_file.write(",\n")
            values = dict(row)
            for field in REDACTED_FIELDS.get(table.name, set()):
                values[field] = None
            json.dump(values, text_file, ensure_ascii=False, default=str)
            count += 1
        text_file.write("\n]\n")
    counts[table.name] = count


def _create_archive(export: DataExport, db: Session) -> dict[str, Any]:
    root = Path(get_settings().media_root).resolve()
    archive_path = _export_path(export.storage_key or "")
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    table_counts: dict[str, int] = {}
    media_files: list[tuple[Path, str]] = []
    media_root = root
    if media_root.exists():
        for path in media_root.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            resolved = path.resolve()
            if media_root not in resolved.parents or resolved == archive_path:
                continue
            relative = path.relative_to(media_root)
            if relative.parts and relative.parts[0] == "exports":
                continue
            media_files.append((path, relative.as_posix()))

    with tempfile.TemporaryDirectory(prefix="durga-export-") as temporary_directory:
        staging = Path(temporary_directory)
        with engine.connect() as connection:
            connection = connection.execution_options(isolation_level="REPEATABLE READ")
            with connection.begin():
                for table in Base.metadata.sorted_tables:
                    _json_rows(staging, table, table_counts, connection)
        with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for table in Base.metadata.sorted_tables:
                archive.write(staging / f"{table.name}.json", f"database/{table.name}.json")
            for file_path, relative_name in media_files:
                archive.write(file_path, f"media/{relative_name}")
            manifest = {
                "format": "durga-data-export-v1",
                "export_id": str(export.id),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": export.expires_at.isoformat() if export.expires_at else None,
                "database_tables": table_counts,
                "media_files": len(media_files),
                "excluded_row_tables": sorted(EXCLUDED_ROW_TABLES),
                "redacted_fields": {table_name: sorted(fields) for table_name, fields in REDACTED_FIELDS.items()},
                "notes": [
                    "Database records are exported as UTF-8 JSON, one file per table.",
                    "Private media files are stored under the media/ folder.",
                    "Authentication sessions and login attempt rows are excluded; PIN and QR token hashes are redacted.",
                    "This archive is a data export and does not include a database schema migration or restore script.",
                ],
            }
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
            archive.writestr(
                "README.txt",
                "Durga Boutique data export\n\n"
                "Keep this archive in owner-controlled secure storage. It contains customer contact details, order records, "
                "photos, and financial data. Database rows are UTF-8 JSON under database/; private images are under media/. "
                "The archive is not a one-click restore package. Use a reviewed schema and restore procedure before importing it.\n",
            )

    export.manifest = manifest
    export.status = "ready"
    db.add(
        AuditLog(
            actor_user_id=export.requested_by_user_id,
            action="data_export.completed",
            entity_type="data_export",
            entity_id=export.id,
            before_after_summary={"tables": len(table_counts), "media_files": len(media_files)},
        )
    )
    return {"tables": len(table_counts), "media_files": len(media_files), "size_bytes": archive_path.stat().st_size}


def _expire_old_exports(db: Session, now: datetime, actor_id: UUID) -> None:
    rows = db.scalars(select(DataExport).where(DataExport.status == "ready", DataExport.expires_at <= now))
    for export in rows:
        if export.storage_key:
            _export_path(export.storage_key).unlink(missing_ok=True)
        export.status = "expired"
        db.add(
            AuditLog(
                actor_user_id=actor_id,
                action="data_export.expired",
                entity_type="data_export",
                entity_id=export.id,
            )
        )


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_same_origin)])
def create_data_export(
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("backup:export")),
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    _expire_old_exports(db, now, actor.id)
    export_id = uuid.uuid4()
    export = DataExport(
        id=export_id,
        requested_by_user_id=actor.id,
        status="building",
        storage_key=f"exports/{export_id}.zip",
        expires_at=now + timedelta(days=EXPORT_TTL_DAYS),
        created_at=now,
    )
    db.add(export)
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="data_export.requested",
            entity_type="data_export",
            entity_id=export_id,
            before_after_summary={"expires_at": export.expires_at.isoformat()},
        )
    )
    db.commit()
    db.refresh(export)
    try:
        counts = _create_archive(export, db)
        db.commit()
    except Exception as error:
        db.rollback()
        _export_path(export.storage_key or "").unlink(missing_ok=True)
        failed = db.get(DataExport, export_id)
        if failed:
            failed.status = "failed"
            db.add(
                AuditLog(
                    actor_user_id=actor.id,
                    action="data_export.failed",
                    entity_type="data_export",
                    entity_id=export_id,
                )
            )
            db.commit()
        raise HTTPException(status_code=500, detail="The data export could not be completed") from error
    return {
        "id": str(export.id),
        "status": export.status,
        "download_url": f"/api/v1/staff/data-exports/{export.id}/download",
        "expires_at": export.expires_at.isoformat(),
        **counts,
    }


@router.get("/{export_id}/download")
def download_data_export(
    export_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("backup:export")),
) -> FileResponse:
    export = db.get(DataExport, export_id)
    if export is None or export.requested_by_user_id != actor.id:
        raise HTTPException(status_code=404, detail="Export was not found")
    if export.status != "ready" or not export.storage_key:
        raise HTTPException(status_code=409, detail="This export is not ready to download")
    if export.expires_at is None or export.expires_at <= datetime.now(timezone.utc):
        export.status = "expired"
        _export_path(export.storage_key).unlink(missing_ok=True)
        db.add(
            AuditLog(
                actor_user_id=actor.id,
                action="data_export.expired",
                entity_type="data_export",
                entity_id=export.id,
            )
        )
        db.commit()
        raise HTTPException(status_code=410, detail="This export has expired. Create a new one.")
    path = _export_path(export.storage_key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Export file is unavailable")
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="data_export.downloaded",
            entity_type="data_export",
            entity_id=export.id,
        )
    )
    db.commit()
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"durga-data-export-{export.created_at:%Y%m%d}.zip",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )
