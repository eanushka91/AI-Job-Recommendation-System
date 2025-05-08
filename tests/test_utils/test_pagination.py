import pytest
from app.api.pagination import paginate # Assuming PageParams is used by routes, not directly here for unit test

# Using a simple mock for page_params for direct testing of paginate function
class MockPageParamsForPagination:
    def __init__(self, page, size):
        self.page = page
        self.size = size

class TestPaginationUtil:

    def test_paginate_page_out_of_bounds_low(self):
        items = list(range(20)) # 4 pages if size is 5
        # Request page 0. pagination.py fix: current_page_requested = max(1, page_params.page)
        page_params = MockPageParamsForPagination(page=0, size=5)
        result = paginate(items, page_params)

        assert result["page"] == 1, f"Expected page 1 when requested page was 0, but got {result['page']}"
        assert len(result["items"]) == 5 # Items for page 1
        assert result["pages"] == 4
        assert result["has_next"] is True
        assert result["has_prev"] is False

    def test_paginate_size_less_than_one_handled(self):
        items = list(range(10)) # 10 items

        # Test with size = 0
        # pagination.py fix: size = max(1, getattr(page_params, 'size', PAGE_SIZE))
        page_params_zero_size = MockPageParamsForPagination(page=1, size=0)
        result_zero = paginate(items, page_params_zero_size)

        assert result_zero["size"] == 1, f"Expected size to be corrected to 1 from 0, got {result_zero['size']}"
        assert result_zero["pages"] == 10 # 10 items / 1 per page = 10 pages
        assert len(result_zero["items"]) == 1 # Should get the first item for page 1
        assert result_zero["items"][0] == items[0]

        # Test with negative size
        page_params_neg_size = MockPageParamsForPagination(page=1, size=-2)
        result_neg = paginate(items, page_params_neg_size)

        assert result_neg["size"] == 1, f"Expected size to be corrected to 1 from -2, got {result_neg['size']}"
        assert result_neg["pages"] == 10
        assert len(result_neg["items"]) == 1
        assert result_neg["items"][0] == items[0]

    # Other pagination tests (basic, middle page, last page, empty items etc.)
    # These should remain largely the same if their logic was sound.
    def test_paginate_basic_scenario(self):
        items = list(range(30)) # 30 items
        page_params = MockPageParamsForPagination(page=2, size=7)
        result = paginate(items, page_params)
        # total_pages = (30 + 7 - 1) // 7 = 36 // 7 = 5 (approx, actually (30+6)//7 = 5 pages)
        # page 1: 0-6
        # page 2: 7-13
        # page 3: 14-20
        # page 4: 21-27
        # page 5: 28-29

        assert result["page"] == 2
        assert result["size"] == 7
        assert result["total"] == 30
        assert result["pages"] == 5 # ceil(30/7) = 5
        assert result["items"] == list(range(7, 14))
        assert result["has_next"] is True
        assert result["has_prev"] is True

    def test_paginate_empty_item_list(self):
        items = []
        page_params = MockPageParamsForPagination(page=1, size=10)
        result = paginate(items, page_params)
        assert result["items"] == []
        assert result["total"] == 0
        assert result["pages"] == 0
        assert result["page"] == 1 # Stays at 1 even if no pages
        assert result["has_next"] is False
        assert result["has_prev"] is False