from decimal import Decimal

from auth import get_current_user
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from models import Booking, Property, User
from schemas import AdminStatsResponse, UpdateRoleRequest, UserOut
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/admin", tags=["admin"])


def _verify_admin(user: User):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required")


@router.get("/stats", response_model=AdminStatsResponse)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _verify_admin(current_user)

    total_users = await db.scalar(select(func.count(User.id)))
    total_properties = await db.scalar(select(func.count(Property.id)))
    total_bookings = await db.scalar(select(func.count(Booking.id)))

    # Sum of platform_fee for confirmed/past bookings. Exclude cancelled.
    rev = await db.scalar(
        select(func.sum(Booking.platform_fee))
        .where(Booking.status != "cancelled")
    )
    total_revenue = rev or Decimal("0.00")

    return {
        "total_users": total_users,
        "total_properties": total_properties,
        "total_bookings": total_bookings,
        "total_platform_revenue": total_revenue
    }


@router.get("/users")
async def get_users(
    page: int = 1,
    limit: int = 20,
    search: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _verify_admin(current_user)

    stmt = select(User)
    if search:
        stmt = stmt.where(User.email.ilike(f"%{search}%"))

    stmt = stmt.order_by(User.created_at.desc()).offset((page - 1) * limit).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    return [UserOut.model_validate(u) for u in rows]


@router.put("/users/{user_id}/role", response_model=UserOut)
async def update_user_role(
    user_id: int,
    payload: UpdateRoleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _verify_admin(current_user)

    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = payload.role
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserOut.model_validate(user)


@router.get("/properties/all")
async def list_all_properties_admin(
    page: int = 1,
    limit: int = 20,
    search: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _verify_admin(current_user)

    filters = []
    if search:
        filters.append(Property.title.ilike(f"%{search}%"))

    stmt = (
        select(Property, User)
        .join(User, User.id == Property.host_id)
        .where(*filters)
    )

    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    stmt = stmt.order_by(Property.created_at.desc()).offset((page - 1) * limit).limit(limit)
    rows = (await db.execute(stmt)).all()

    items = []
    for p, host in rows:
        items.append({
            "id": p.id,
            "title": p.title,
            "city": p.city,
            "price_per_night": p.price_per_night,
            "is_available": p.is_available,
            "host": {"id": host.id, "name": host.name, "email": host.email},
            "created_at": p.created_at
        })

    from math import ceil
    return {"items": items, "total": total or 0, "page": page, "pages": ceil((total or 0) / limit)}
