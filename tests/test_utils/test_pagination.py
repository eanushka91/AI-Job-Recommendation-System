from app.api.pagination import paginate


class MockPageParamsForPagination:
    def __init__(self, page, size):
        self.page = page
        self.size = size


class TestPaginationUtil:
    def test_paginate_page_out_of_bounds_low(self):
        items = list(range(20))
        page_params = MockPageParamsForPagination(page=0, size=5)
        result = paginate(items, page_params)
        assert result["page"] == 1

    def test_paginate_size_less_than_one_handled(self):
        items = list(range(10))
        page_params_zero = MockPageParamsForPagination(page=1, size=0)
        result_zero = paginate(items, page_params_zero)
        assert result_zero["size"] == 1
        assert result_zero["pages"] == 10

        page_params_neg = MockPageParamsForPagination(page=1, size=-2)
        result_neg = paginate(items, page_params_neg)
        assert result_neg["size"] == 1
        assert result_neg["pages"] == 10
