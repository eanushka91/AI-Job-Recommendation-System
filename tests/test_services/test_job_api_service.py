import pytest
from app.services.job_api_service import JobAPIService
import requests


class TestJobAPIService:

    def test_fetch_jobs_success(self, mocker):
        # Mock the JOOBLE_API_KEY within app.config.settings module
        mocker.patch('app.config.settings.JOOBLE_API_KEY', "test_key_success_001")

        mock_api_data = {"jobs": [{"id": "ts001", "title": "Test Job Success"}]}
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_api_data
        mock_post = mocker.patch("requests.post", return_value=mock_response)

        jobs = JobAPIService.fetch_jobs(keywords=["test_kw_succ"], limit=1)

        assert len(jobs) == 1, f"Expected 1 job, got {len(jobs)}. Response: {jobs}"
        assert jobs[0]["id"] == "ts001"
        mock_post.assert_called_once()
        # (Further assertions on call arguments can be added if needed)

    def test_fetch_jobs_api_error_response(self, mocker):
        mocker.patch('app.config.settings.JOOBLE_API_KEY', "test_key_api_error_002")

        mock_response = mocker.Mock()
        mock_response.status_code = 403  # Simulate an API error like Forbidden
        mock_response.text = "Forbidden - Invalid API Key"
        mock_post = mocker.patch("requests.post", return_value=mock_response)

        jobs = JobAPIService.fetch_jobs(keywords=["test_kw_apierr"])

        assert jobs == [], f"Expected empty list on API error, got {jobs}"
        mock_post.assert_called_once()  # Should still attempt the call

    def test_fetch_jobs_requests_exception(self, mocker):
        mocker.patch('app.config.settings.JOOBLE_API_KEY', "test_key_req_exception_003")
        mock_post = mocker.patch("requests.post",
                                 side_effect=requests.exceptions.ConnectTimeout("Connection timed out"))

        jobs = JobAPIService.fetch_jobs(keywords=["test_kw_reqexc"])

        assert jobs == [], f"Expected empty list on requests exception, got {jobs}"
        mock_post.assert_called_once()

    def test_process_jooble_response_jobs_not_a_list(self):
        # Test case where 'jobs' key contains a string instead of a list
        api_response_invalid_jobs_type = {"jobs": "this is a string, not a list"}
        # The fix in JobAPIService._process_jooble_response should now handle this:
        # `if not isinstance(jobs_list, list): return []`
        processed = JobAPIService._process_jooble_response(api_response_invalid_jobs_type)
        assert processed == [], "Expected empty list when 'jobs' is not a list."

    def test_process_jooble_response_job_item_not_a_dict(self):
        # Test case where an item within the 'jobs' list is not a dictionary
        api_response_invalid_job_item = {
            "jobs": [
                "not_a_dictionary_item",  # This item should be skipped
                {"id": "valid_id_001", "title": "Valid Job Item"}
            ]
        }
        # The fix in JobAPIService._process_jooble_response:
        # `if not isinstance(job_data, dict): continue`
        processed = JobAPIService._process_jooble_response(api_response_invalid_job_item)
        assert len(processed) == 1, "Expected only the valid dictionary item to be processed."
        if processed:  # Ensure list is not empty before indexing
            assert processed[0]["id"] == "valid_id_001"

    # Other _process_jooble_response tests (valid, empty, no_jobs_key, all_defaults)
    # should still pass if their inputs were already correct.
    def test_process_jooble_response_valid_input(self):
        api_response = {"jobs": [{"id": "v01", "title": "Valid"}]}
        processed = JobAPIService._process_jooble_response(api_response)
        assert len(processed) == 1
        assert processed[0]['id'] == 'v01'

    def test_process_jooble_response_empty_actual_jobs_list(self):
        api_response = {"jobs": []}
        processed = JobAPIService._process_jooble_response(api_response)
        assert processed == []

    def test_process_jooble_response_missing_jobs_key(self):
        api_response = {"some_other_key": "value"}
        processed = JobAPIService._process_jooble_response(api_response)
        assert processed == []