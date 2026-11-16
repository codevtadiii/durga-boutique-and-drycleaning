from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.auth import router as auth_router
from app.api.closings import router as closings_router
from app.api.catalog import router as catalog_router
from app.api.customers import customer_router, staff_router
from app.api.finance import router as finance_router
from app.api.exports import router as exports_router
from app.api.preferences import router as preferences_router
from app.api.photos import customer_router as customer_photo_router
from app.api.photos import staff_router as staff_photo_router
from app.api.reports import router as reports_router
from app.api.orders import booking_router, customer_router as customer_order_router, public_router, staff_router as staff_order_router
from app.api.notifications import router as notifications_router
from app.core.config import get_settings
from app.core.database import Base, engine
import app.models  # noqa: F401 - register every model before creating development tables

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.auto_create_schema:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(catalog_router)
app.include_router(customer_router)
app.include_router(staff_router)
app.include_router(preferences_router)
app.include_router(closings_router)
app.include_router(customer_photo_router)
app.include_router(staff_photo_router)
app.include_router(finance_router)
app.include_router(exports_router)
app.include_router(reports_router)
app.include_router(public_router)
app.include_router(booking_router)
app.include_router(staff_order_router)
app.include_router(customer_order_router)
app.include_router(notifications_router)


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["operations"])
def ready() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Database is unavailable") from error
    return {"status": "ready"}
