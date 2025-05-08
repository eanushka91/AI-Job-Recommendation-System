from fastapi import Query
from typing import Generic, TypeVar, Sequence, List, Dict, Any # Optional not used
from pydantic import BaseModel
# Ensure PAGE_SIZE is correctly imported or defined
try:
    from app.config.settings import PAGE_SIZE
except ImportError:
    PAGE_SIZE = 10 # Default fallback if not in settings

T = TypeVar('T')

class PageParams:
    def __init__(
            self,
            page: int = Query(1, ge=1, description="Page number"),
            # Ensure size is always at least 1 from Query itself if possible,
            # or handle it robustly in paginate. ge=1 is good.
            size: int = Query(PAGE_SIZE, ge=1, le=100, description="Items per page")
    ):
        self.page = page
        self.size = size if size >=1 else PAGE_SIZE # Ensure size is positive

class PageResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool

def paginate(
        items: Sequence[Any],
        page_params: PageParams # Expects an object with 'page' and 'size'
) -> Dict[str, Any]:
    total_items = len(items)

    # Ensure size is strictly positive to prevent ZeroDivisionError
    # PageParams class now tries to enforce this, but an extra check here is safer.
    size = max(1, getattr(page_params, 'size', PAGE_SIZE)) # Safely get size, default if not present or invalid

    if total_items == 0:
        total_pages = 0
    else:
        total_pages = (total_items + size - 1) // size

    # Ensure requested page is at least 1
    current_page_requested = max(1, getattr(page_params, 'page', 1)) # Safely get page

    # Clamp page to valid range
    if total_pages == 0:
        page = 1 # If no items/pages, current page is effectively 1 (showing nothing)
    else:
        page = min(current_page_requested, total_pages)

    start_idx = (page - 1) * size
    # end_idx should not exceed total_items
    end_idx = min(start_idx + size, total_items)

    page_items = items[start_idx:end_idx] if total_items > 0 and start_idx < total_items else []

    return {
        "items": page_items,
        "total": total_items,
        "page": page, # The effective page number used
        "size": size, # The effective size used
        "pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1 and total_pages > 0
    }