import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission, require_same_origin
from app.models import AuditLog, OrderItem, Service, ServiceCategory, User

router = APIRouter(prefix="/api/v1/staff", tags=["service catalogue"])
logger = logging.getLogger(__name__)
CATEGORY_DISPLAY_ORDER = ("Men", "Women", "Household", "Kids", "Special Services", "Other Services")


class CategoryInput(BaseModel):
    name_en: str = Field(min_length=2, max_length=100)
    name_te: str = Field(min_length=2, max_length=100)


class CategoryUpdate(BaseModel):
    name_en: str | None = Field(default=None, min_length=2, max_length=100)
    name_te: str | None = Field(default=None, min_length=2, max_length=100)


class ServiceInput(BaseModel):
    category_id: uuid.UUID
    name_en: str = Field(min_length=2, max_length=120)
    name_te: str = Field(min_length=2, max_length=120)
    description_en: str = Field(default="", max_length=2000)
    description_te: str = Field(default="", max_length=2000)
    price_paise: int | None = Field(default=None, ge=0, le=100_000_000)
    quotation_required: bool = False
    price_is_starting: bool = False
    additional_charge_paise: int = Field(default=0, ge=0, le=100_000_000)
    garment_type: str | None = Field(default=None, min_length=2, max_length=100)
    pricing_unit: str = Field(min_length=2, max_length=30)
    turnaround_days: int | None = Field(default=None, ge=0, le=365)
    active: bool = True

    @model_validator(mode="after")
    def require_price_or_quote(self):
        if not self.quotation_required and not self.price_paise:
            raise ValueError("Enter a price or mark this service as awaiting a staff quotation")
        if self.price_is_starting and (not self.quotation_required or not self.price_paise):
            raise ValueError("A starting price must have an amount and require staff confirmation")
        return self


class ServiceUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    name_en: str | None = Field(default=None, min_length=2, max_length=120)
    name_te: str | None = Field(default=None, min_length=2, max_length=120)
    description_en: str | None = Field(default=None, max_length=2000)
    description_te: str | None = Field(default=None, max_length=2000)
    price_paise: int | None = Field(default=None, ge=0, le=100_000_000)
    quotation_required: bool | None = None
    price_is_starting: bool | None = None
    additional_charge_paise: int | None = Field(default=None, ge=0, le=100_000_000)
    garment_type: str | None = Field(default=None, min_length=2, max_length=100)
    pricing_unit: str | None = Field(default=None, min_length=2, max_length=30)
    turnaround_days: int | None = Field(default=None, ge=0, le=365)
    active: bool | None = None


@router.get("/service-categories")
def list_categories(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("service:manage")),
) -> list[dict]:
    rows = db.scalars(
        select(ServiceCategory)
        .where(ServiceCategory.archived_at.is_(None))
        .order_by(
            case({name: index for index, name in enumerate(CATEGORY_DISPLAY_ORDER)}, value=ServiceCategory.name_en, else_=len(CATEGORY_DISPLAY_ORDER)),
            ServiceCategory.name_en,
        )
    )
    return [{"id": str(row.id), "name_en": row.name_en, "name_te": row.name_te, "active": row.active} for row in rows]


@router.get("/services")
def list_services(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("service:manage")),
) -> list[dict]:
    return [
        _service_view(service)
        for service in db.scalars(
            select(Service).where(Service.archived_at.is_(None)).order_by(Service.name_en)
        )
    ]


@router.post("/service-categories", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_same_origin)])
def create_category(
    payload: CategoryInput,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("service:manage")),
) -> dict:
    name_en = payload.name_en.strip()
    name_te = payload.name_te.strip()
    if len(name_en) < 2 or len(name_te) < 2:
        raise HTTPException(status_code=422, detail="Enter both catalogue names")
    if db.scalar(select(ServiceCategory.id).where(
        func.lower(ServiceCategory.name_en) == name_en.lower(),
        ServiceCategory.archived_at.is_(None),
    ).limit(1)):
        raise HTTPException(status_code=409, detail="A catalogue with this English name already exists")
    category = ServiceCategory(name_en=name_en, name_te=name_te, active=True)
    db.add(category)
    db.flush()
    db.add(AuditLog(actor_user_id=actor.id, action="service_category.created", entity_type="service_category", entity_id=category.id))
    db.commit()
    return {"id": str(category.id), "name_en": category.name_en, "name_te": category.name_te, "active": category.active}


@router.patch("/service-categories/{category_id}", dependencies=[Depends(require_same_origin)])
def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("service:manage")),
) -> dict:
    category = db.scalar(
        select(ServiceCategory).where(ServiceCategory.id == category_id).with_for_update()
    )
    if category is None or category.archived_at is not None:
        raise HTTPException(status_code=404, detail="Catalogue was not found")
    values = payload.model_dump(exclude_unset=True)
    values = {key: value.strip() if isinstance(value, str) else value for key, value in values.items()}
    if not values or any(value is None or len(value) < 2 for value in values.values()):
        raise HTTPException(status_code=422, detail="Enter valid English and Telugu catalogue names")
    next_name = values.get("name_en", category.name_en)
    duplicate_id = db.scalar(
        select(ServiceCategory.id).where(
            func.lower(ServiceCategory.name_en) == next_name.lower(),
            ServiceCategory.id != category.id,
            ServiceCategory.archived_at.is_(None),
        ).limit(1)
    )
    if duplicate_id:
        raise HTTPException(status_code=409, detail="A catalogue with this English name already exists")
    before = {key: getattr(category, key) for key in values}
    for key, value in values.items():
        setattr(category, key, value)
    db.add(AuditLog(
        actor_user_id=actor.id,
        action="service_category.updated",
        entity_type="service_category",
        entity_id=category.id,
        before_after_summary={"before": before, "after": values},
    ))
    db.commit()
    return {"id": str(category.id), "name_en": category.name_en, "name_te": category.name_te, "active": category.active}


@router.delete("/service-categories/{category_id}", dependencies=[Depends(require_same_origin)])
def delete_category(
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("service:manage")),
) -> dict:
    try:
        category = db.scalar(
            select(ServiceCategory).where(ServiceCategory.id == category_id).with_for_update()
        )
        if category is None or category.archived_at is not None:
            raise HTTPException(status_code=404, detail="Catalogue was not found")

        services = list(db.scalars(
            select(Service).where(Service.category_id == category.id).order_by(Service.id).with_for_update()
        ))
        deleted_services = 0
        archived_services = 0
        had_historical_services = False
        for service in services:
            order_references = db.scalar(
                select(func.count()).select_from(OrderItem).where(OrderItem.service_id == service.id)
            ) or 0
            if order_references:
                had_historical_services = True
                service.active = False
                service.archived_at = service.archived_at or func.now()
                archived_services += 1
                service_action = "archived"
            else:
                db.delete(service)
                deleted_services += 1
                service_action = "deleted"
            db.add(AuditLog(
                actor_user_id=actor.id,
                action=f"service.{service_action}",
                entity_type="service",
                entity_id=service.id,
                before_after_summary={
                    "name_en": service.name_en,
                    "category_name_en": category.name_en,
                    "order_references": int(order_references),
                    "action": service_action,
                    "reason": "catalogue deleted",
                },
            ))

        name_en = category.name_en
        name_te = category.name_te
        if had_historical_services:
            category.active = False
            category.archived_at = func.now()
            action = "archived"
        else:
            db.delete(category)
            action = "deleted"
        db.add(AuditLog(
            actor_user_id=actor.id,
            action=f"service_category.{action}",
            entity_type="service_category",
            entity_id=category_id,
            before_after_summary={
                "name_en": name_en,
                "name_te": name_te,
                "services_deleted": deleted_services,
                "services_archived": archived_services,
                "action": action,
            },
        ))
        db.commit()
        return {
            "id": str(category_id),
            "name_en": name_en,
            "action": action,
            "services_deleted": deleted_services,
            "services_archived": archived_services,
        }
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This catalogue still has linked business records, so it could not be deleted.",
        ) from error
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception("Catalogue deletion failed", extra={"category_id": str(category_id)})
        raise HTTPException(
            status_code=503,
            detail="The catalogue could not be deleted right now. No changes were saved; please try again.",
        ) from error


@router.post("/services", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_same_origin)])
def create_service(
    payload: ServiceInput,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("service:manage")),
) -> dict:
    category = db.scalar(
        select(ServiceCategory).where(ServiceCategory.id == payload.category_id).with_for_update()
    )
    if category is None or category.archived_at is not None or not category.active:
        raise HTTPException(status_code=404, detail="Service category was not found")
    values = payload.model_dump()
    if values["quotation_required"]:
        values["price_paise"] = 0
    service = Service(**values)
    db.add(service)
    db.flush()
    db.add(AuditLog(actor_user_id=actor.id, action="service.created", entity_type="service", entity_id=service.id))
    db.commit()
    return _service_view(service)


@router.patch("/services/{service_id}", dependencies=[Depends(require_same_origin)])
def update_service(
    service_id: uuid.UUID,
    payload: ServiceUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("service:manage")),
) -> dict:
    service = db.scalar(select(Service).where(Service.id == service_id).with_for_update())
    if service is None:
        raise HTTPException(status_code=404, detail="Service was not found")
    if service.archived_at is not None:
        raise HTTPException(status_code=409, detail="Archived services cannot be changed or re-enabled")
    values = payload.model_dump(exclude_unset=True)
    if "category_id" in values and values["category_id"] is None:
        raise HTTPException(status_code=422, detail="Choose a service category")
    if "category_id" in values and values["category_id"]:
        category = db.scalar(
            select(ServiceCategory).where(ServiceCategory.id == values["category_id"]).with_for_update()
        )
        if category is None or category.archived_at is not None or not category.active:
            raise HTTPException(status_code=404, detail="Service category was not found")
    next_quote_required = values.get("quotation_required", service.quotation_required)
    next_price = values.get("price_paise", service.price_paise)
    next_starting = values.get("price_is_starting", service.price_is_starting)
    if next_starting and not next_quote_required:
        raise HTTPException(status_code=422, detail="A starting price must require staff confirmation")
    if next_starting and not next_price:
        raise HTTPException(status_code=422, detail="Enter the starting price amount")
    if next_quote_required and next_price is None:
        values["price_paise"] = 0
    elif not next_quote_required and not next_price:
        raise HTTPException(status_code=422, detail="Enter a price or mark this service as awaiting a staff quotation")
    if values.get("garment_type") == "":
        values["garment_type"] = None
    before = {key: str(getattr(service, key)) if isinstance(getattr(service, key), uuid.UUID) else getattr(service, key) for key in values}
    for key, value in values.items():
        setattr(service, key, value)
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="service.updated",
            entity_type="service",
            entity_id=service.id,
            before_after_summary={"before": before, "after": {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in values.items()}},
        )
    )
    db.commit()
    return _service_view(service)


def _service_view(service: Service) -> dict:
    return {
        "id": str(service.id),
        "category_id": str(service.category_id),
        "category_name_en": service.category.name_en,
        "name_en": service.name_en,
        "name_te": service.name_te,
        "description_en": service.description_en,
        "description_te": service.description_te,
        "price_paise": service.price_paise,
        "quotation_required": service.quotation_required or service.price_paise == 0,
        "price_is_starting": service.price_is_starting,
        "additional_charge_paise": service.additional_charge_paise,
        "garment_type": service.garment_type,
        "pricing_unit": service.pricing_unit,
        "turnaround_days": service.turnaround_days,
        "active": service.active,
    }


@router.delete("/services/{service_id}", dependencies=[Depends(require_same_origin)])
def delete_service(
    service_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("service:manage")),
) -> dict:
    try:
        service = db.scalar(select(Service).where(Service.id == service_id).with_for_update())
        if service is None:
            raise HTTPException(status_code=404, detail="Service was not found")
        if service.archived_at is not None:
            raise HTTPException(status_code=404, detail="Service was not found")

        order_references = db.scalar(
            select(func.count()).select_from(OrderItem).where(OrderItem.service_id == service.id)
        ) or 0
        name = service.name_en
        if order_references:
            service.active = False
            service.archived_at = func.now()
            action = "archived"
        else:
            db.delete(service)
            action = "deleted"

        db.add(AuditLog(
            actor_user_id=actor.id,
            action=f"service.{action}",
            entity_type="service",
            entity_id=service_id,
            before_after_summary={"name_en": name, "order_references": order_references, "action": action},
        ))
        db.commit()
        return {"id": str(service_id), "name_en": name, "action": action, "order_references": order_references}
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This service is still linked to business records, so no changes were made.",
        ) from error
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception("Service deletion failed", extra={"service_id": str(service_id)})
        raise HTTPException(
            status_code=503,
            detail="The service could not be deleted right now. No changes were saved; please try again.",
        ) from error
