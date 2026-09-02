"""
Public marketplace endpoints — no auth required to browse
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload
from typing import Optional, List
import math

from api.deps import get_db
from api.models.database import Dataset, DatasetFile, User, DatasetCollection, DatasetReview, DatasetWishlist, DataRequest
from api.schemas.schemas import (
    DatasetOut, DatasetListItem, DatasetListResponse,
    ReviewOut, CollectionOut, DataRequestOut, DataRequestCreate
)
from api.deps import get_optional_user as get_current_user, get_current_user as require_user
from config import settings

router = APIRouter(tags=["Market Public"])


def _dataset_query(only_verified=True):
    q = select(Dataset).options(
        selectinload(Dataset.seller),
        selectinload(Dataset.files),
    )
    if only_verified:
        q = q.where(
            Dataset.status == "verified",
            Dataset.visibility == "public",
        )
    return q


@router.get("/datasets", response_model=DatasetListResponse)
async def list_datasets(
    q: Optional[str]    = Query(None),
    domain: Optional[str] = Query(None),
    format: Optional[str] = Query(None),
    price_type: Optional[str] = Query(None),  # free | paid
    country: Optional[str] = Query(None),
    license: Optional[str] = Query(None),
    sort: str = Query("newest"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    year_min: Optional[int] = Query(None),
    year_max: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    base_q = _dataset_query()

    # Filters
    if q:
        like = f"%{q}%"
        base_q = base_q.where(
            or_(
                Dataset.title.ilike(like),
                Dataset.description.ilike(like),
                Dataset.domain.ilike(like),
            )
        )
    if domain:
        base_q = base_q.where(Dataset.domain.ilike(f"%{domain}%"))
    if country:
        base_q = base_q.where(Dataset.country.ilike(f"%{country}%"))
    if license:
        base_q = base_q.where(Dataset.license == license)
    if price_type == "free":
        base_q = base_q.where(Dataset.price_naira == 0)
    elif price_type == "paid":
        base_q = base_q.where(Dataset.price_naira > 0)
    if year_min:
        base_q = base_q.where(Dataset.year_collected >= year_min)
    if year_max:
        base_q = base_q.where(Dataset.year_collected <= year_max)
    if format:
        # Filter by datasets that have a file in this format
        from ..models import DatasetFile
        sub = select(DatasetFile.dataset_id).where(DatasetFile.format == format.lower())
        base_q = base_q.where(Dataset.id.in_(sub))

    # Sort
    sort_map = {
        "newest":      Dataset.published_at.desc(),
        "oldest":      Dataset.published_at.asc(),
        "downloads":   Dataset.download_count.desc(),
        "rating":      Dataset.average_rating.desc(),
        "price_asc":   Dataset.price_naira.asc(),
        "price_desc":  Dataset.price_naira.desc(),
    }
    base_q = base_q.order_by(sort_map.get(sort, Dataset.published_at.desc()))

    # Count
    count_q = select(func.count()).select_from(base_q.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    # Paginate
    offset = (page - 1) * per_page
    result = await db.execute(base_q.offset(offset).limit(per_page))
    datasets = result.scalars().all()

    return DatasetListResponse(
        items=[DatasetListItem.model_validate(d) for d in datasets],
        total=total,
        page=page,
        per_page=per_page,
        pages=max(1, math.ceil(total / per_page)),
    )


@router.get("/datasets/{slug}", response_model=DatasetOut)
async def get_dataset(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        _dataset_query().where(Dataset.slug == slug)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return DatasetOut.model_validate(dataset)


@router.post("/datasets/{slug}/view")
async def record_view(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Dataset).where(Dataset.slug == slug))
    dataset = result.scalar_one_or_none()
    if dataset:
        dataset.view_count = (dataset.view_count or 0) + 1
        await db.commit()
    return {"ok": True}


@router.get("/datasets/{slug}/preview")
async def preview_dataset(slug: str, db: AsyncSession = Depends(get_db)):
    """Return first 10 rows of tabular dataset as JSON (no auth needed)."""
    result = await db.execute(
        select(Dataset).where(Dataset.slug == slug, Dataset.status == "verified")
    )
    dataset = result.scalar_one_or_none()
    if not dataset or not dataset.sample_file_path:
        raise HTTPException(status_code=404, detail="Preview not available")

    from ..storage import get_file_bytes, settings as s
    import pandas as pd, io

    try:
        csv_bytes = get_file_bytes(s.S3_BUCKET_SAMPLES, dataset.sample_file_path)
        df = pd.read_csv(io.BytesIO(csv_bytes))
        return {
            "columns": list(df.columns),
            "rows": df.head(settings.SAMPLE_PREVIEW_ROWS).to_dict(orient="records"),
            "total_columns": len(df.columns),
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Preview generation failed")


@router.get("/datasets/{slug}/schema")
async def dataset_schema(slug: str, db: AsyncSession = Depends(get_db)):
    """Return column names and dtypes without any row data."""
    result = await db.execute(
        select(Dataset).where(Dataset.slug == slug, Dataset.status == "verified")
    )
    dataset = result.scalar_one_or_none()
    if not dataset or not dataset.sample_file_path:
        raise HTTPException(status_code=404, detail="Schema not available")

    from ..storage import get_file_bytes, settings as s
    import pandas as pd, io

    try:
        csv_bytes = get_file_bytes(s.S3_BUCKET_SAMPLES, dataset.sample_file_path)
        df = pd.read_csv(io.BytesIO(csv_bytes), nrows=0)
        return {
            "columns": [{"name": c, "dtype": str(df[c].dtype)} for c in df.columns]
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Schema extraction failed")


@router.get("/domains")
async def list_domains(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Dataset.domain, func.count(Dataset.id).label("count"))
        .where(Dataset.status == "verified", Dataset.visibility == "public", Dataset.domain.isnot(None))
        .group_by(Dataset.domain)
        .order_by(func.count(Dataset.id).desc())
    )
    domains = result.all()
    return [{"domain": d, "count": c} for d, c in domains]


@router.get("/trending")
async def trending_datasets(db: AsyncSession = Depends(get_db)):
    """Top 12 datasets by download_count in last 7 days (simplified: by download_count)."""
    result = await db.execute(
        _dataset_query()
        .order_by(Dataset.download_count.desc())
        .limit(12)
    )
    return [DatasetListItem.model_validate(d) for d in result.scalars().all()]


@router.get("/featured")
async def featured_datasets(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        _dataset_query().where(Dataset.featured == True).limit(8)
    )
    return [DatasetListItem.model_validate(d) for d in result.scalars().all()]


@router.get("/collections", response_model=List[CollectionOut])
async def list_collections(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DatasetCollection).order_by(DatasetCollection.is_curated.desc(), DatasetCollection.created_at.desc())
    )
    return result.scalars().all()


@router.get("/collections/{collection_id}", response_model=CollectionOut)
async def get_collection(collection_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DatasetCollection).where(DatasetCollection.id == collection_id))
    col = result.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    return col


@router.get("/datasets/{slug}/reviews", response_model=List[ReviewOut])
async def get_reviews(
    slug: str,
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Dataset).where(Dataset.slug == slug))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    offset = (page - 1) * 10
    rev_result = await db.execute(
        select(DatasetReview)
        .options(selectinload(DatasetReview.reviewer))
        .where(DatasetReview.dataset_id == dataset.id)
        .order_by(DatasetReview.created_at.desc())
        .offset(offset).limit(10)
    )
    return rev_result.scalars().all()


@router.get("/sellers/{username}")
async def seller_profile(username: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == username))
    seller = result.scalar_one_or_none()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    datasets_result = await db.execute(
        _dataset_query().where(Dataset.seller_id == seller.id).limit(20)
    )
    datasets = datasets_result.scalars().all()

    return {
        "id": str(seller.id),
        "full_name": seller.full_name,
        "username": seller.username,
        "institution": seller.institution,
        "bio": seller.bio,
        "avatar_path": seller.avatar_path,
        "datasets": [DatasetListItem.model_validate(d) for d in datasets],
        "total_datasets": len(datasets),
    }


@router.get("/requests", response_model=List[DataRequestOut])
async def list_data_requests(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DataRequest).where(DataRequest.status == "open")
        .order_by(DataRequest.created_at.desc()).limit(50)
    )
    return result.scalars().all()


@router.post("/requests", response_model=DataRequestOut)
async def create_data_request(
    body: DataRequestCreate,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    req = DataRequest(requester_id=current_user.id, **body.model_dump())
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return req
