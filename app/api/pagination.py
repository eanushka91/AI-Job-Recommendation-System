from fastapi import Query
from typing import Generic, TypeVar, Sequence, List, Optional, Dict, Any
from pydantic import BaseModel
from app.config.settings import PAGE_SIZE

T = TypeVar('T')


class PageParams:
    """Page parameters for pagination"""

    def __init__(
            self,
            page: int = Query(1, ge=1, description="Page number"),
            size: int = Query(PAGE_SIZE, ge=1, description="Items per page")
    ):
        self.page = page
        self.size = size


class PageResponse(BaseModel, Generic[T]):
    """Standard response for paginated results"""
    items: List[T]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool


def paginate(
        items: Sequence[Any],
        page_params: PageParams
) -> Dict[str, Any]:
    """
    Paginate a sequence of items

    Args:
        items: Sequence of items to paginate
        page_params: Pagination parameters

    Returns:
        Dictionary with paginated items and metadata
    """
    # Calculate total pages
    total_items = len(items)
    total_pages = (total_items + page_params.size - 1) // page_params.size

    # Ensure page number is within bounds
    page = min(page_params.page, total_pages) if total_pages > 0 else 1

    # Calculate start and end indices
    start_idx = (page - 1) * page_params.size
    end_idx = min(start_idx + page_params.size, total_items)

    # Get items for the current page
    page_items = items[start_idx:end_idx] if items else []

    # Prepare response
    return {
        "items": page_items,
        "total": total_items,
        "page": page,
        "size": page_params.size,
        "pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1
    }