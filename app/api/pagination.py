from fastapi import Query
from typing import Generic, TypeVar, Sequence, List, Dict, Any
from pydantic import BaseModel

try:
    from app.config.settings import PAGE_SIZE
except ImportError:
    PAGE_SIZE = 10

T = TypeVar("T")


class PageParams:
    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number"),
        size: int = Query(PAGE_SIZE, ge=1, le=100, description="Items per page"),
    ):
        self.page = page
        self.size = size if size >= 1 else PAGE_SIZE


class PageResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool


class RecommendationsWrappedResponse(BaseModel, Generic[T]):
    recommendations: PageResponse[T]


def paginate(
    items: Sequence[Any],
    page_params: PageParams,
) -> Dict[str, Any]:
    total_items = len(items)
    size = max(1, getattr(page_params, "size", PAGE_SIZE))

    if total_items == 0:
        total_pages = 0
    else:
        total_pages = (total_items + size - 1) // size

    current_page_requested = max(1, getattr(page_params, "page", 1))

    if total_pages == 0:
        page = 1
    else:
        page = min(current_page_requested, total_pages)

    start_idx = (page - 1) * size
    end_idx = min(start_idx + size, total_items)

    page_items = (
        items[start_idx:end_idx] if total_items > 0 and start_idx < total_items else []
    )

    return {
        "items": page_items,
        "total": total_items,
        "page": page,
        "size": size,
        "pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1 and total_pages > 0,
    }