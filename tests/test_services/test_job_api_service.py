from app.services.job_api_service import JobAPIService
import requests
from unittest.mock import MagicMock

SETTINGS_API_KEY_PATH = "app.config.settings.JOOBLE_API_KEY"


class TestJobAPIService:
    def test_fetch_jobs_success(self, mocker):
        MOCKED_KEY = "key_success_001"
        mocker.patch(SETTINGS_API_KEY_PATH, MOCKED_KEY, create=True)
        mock_api_data = {"jobs": [{"id": "succ001", "title": "Success Job"}]}
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = mock_api_data
        mock_post = mocker.patch("requests.post", return_value=mock_response)

        jobs = JobAPIService.fetch_jobs(keywords=["kw_succ"], limit=1)
        assert len(jobs) == 1
        mock_post.assert_called_once()

    def test_fetch_jobs_api_error_response(self, mocker):
        MOCKED_KEY = "key_api_error_002"
        mocker.patch(SETTINGS_API_KEY_PATH, MOCKED_KEY, create=True)
        mock_response = MagicMock(status_code=403, text="Forbidden")
        mock_post = mocker.patch("requests.post", return_value=mock_response)
        jobs = JobAPIService.fetch_jobs(keywords=["kw_api_err"])
        assert jobs == []
        mock_post.assert_called_once()

    def test_fetch_jobs_requests_exception(self, mocker):
        MOCKED_KEY = "key_req_exception_003"
        mocker.patch(SETTINGS_API_KEY_PATH, MOCKED_KEY, create=True)
        mock_post = mocker.patch(
            "requests.post", side_effect=requests.exceptions.ConnectTimeout("Timeout")
        )
        jobs = JobAPIService.fetch_jobs(keywords=["kw_req_exc"])
        assert jobs == []
        mock_post.assert_called_once()

    def test_fetch_jobs_no_api_key_configured(self, mocker):
        mocker.patch(SETTINGS_API_KEY_PATH, None, create=True)
        mock_post = mocker.patch("requests.post")
        jobs = JobAPIService.fetch_jobs(keywords=["kw_no_key"])
        assert jobs == []
        mock_post.assert_not_called()

    def test_process_jooble_response_jobs_not_a_list(self):
        api_response = {"jobs": "not a list"}
        processed = JobAPIService._process_jooble_response(api_response)
        assert processed == []

    def test_process_jooble_response_job_item_not_a_dict(self):
        api_response = {"jobs": ["string_item", {"id": "v1"}]}
        processed = JobAPIService._process_jooble_response(api_response)
        assert len(processed) == 1
        assert processed[0]["id"] == "v1"