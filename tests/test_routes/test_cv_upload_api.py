from fastapi.testclient import TestClient
import io
from unittest.mock import ANY, patch

from app.config import settings

VALID_RESUME_ID = 101
MOCK_RESUME_DATA = {
    "id": VALID_RESUME_ID,
    "user_id": 1,
    "cv_url": "http://s3/cv.pdf",
    "skills": ["python", "fastapi"],
    "experience": ["dev"],
    "education": ["bsc"],
    "location": "Colombo",
}
MOCK_RECOMMENDATIONS_PAYLOAD = [{"id": "job1", "title": "Awesome Job"}]
MOCK_SEARCH_RESULTS = [{"id": "search1", "title": "Found Job"}]
MOCK_JOB_STATS = {"total_matching_jobs": 50, "top_skills": ["python", "java"]}


def test_upload_cv_user_creation_fails(
    client: TestClient,
    mock_s3_upload,
    mock_user_model_create,
):
    mock_s3_upload.return_value = "http://fake-s3-url.com/user_create_fail.pdf"
    mock_user_model_create.return_value = None

    pdf_content = b"%PDF-1.4\n%user_create_fail"
    files = {
        "file": ("user_create_fail.pdf", io.BytesIO(pdf_content), "application/pdf")
    }
    form_data = {"skills": "s", "experience": "e", "education": "d"}

    response = client.post("/api/upload-cv", files=files, data=form_data)

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to create new user record."
    mock_user_model_create.assert_called_once()


def test_upload_cv_resume_creation_fails(
    client: TestClient,
    mock_s3_upload,
    mock_user_model_get_by_id,
    mock_resume_model_create,
):
    user_id_existing = 789
    mock_s3_upload.return_value = "http://fake-s3-url.com/resume_create_fail.pdf"
    mock_user_model_get_by_id.return_value = {
        "id": user_id_existing,
        "created_at": "sometime",
    }
    mock_resume_model_create.return_value = None

    pdf_content = b"%PDF-1.4\n%resume_create_fail"
    files = {
        "file": ("resume_create_fail.pdf", io.BytesIO(pdf_content), "application/pdf")
    }
    form_data = {
        "skills": "s",
        "experience": "e",
        "education": "d",
        "user_id": str(user_id_existing),
    }

    response = client.post("/api/upload-cv", files=files, data=form_data)

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to create resume record."
    mock_resume_model_create.assert_called_once()


def test_upload_cv_unexpected_generic_exception(
    client: TestClient,
    mock_s3_upload,
    mock_user_model_create,  # Add this fixture to the test parameters
    # mock_resume_model_create will be patched locally in this test
):
    mock_s3_upload.return_value = "http://fake-s3-url.com/generic_error.pdf"
    # SIMULATE SUCCESSFUL USER CREATION first, so we reach ResumeModel.create
    mock_user_model_create.return_value = 123  # Assume user creation is successful

    from app.db import models as db_models

    # Now mock ResumeModel.create to cause the generic error you want to test
    with patch.object(
        db_models.ResumeModel, "create", side_effect=ValueError("Unexpected DB trouble")
    ):
        pdf_content = b"%PDF-1.4\n%generic"
        files = {"file": ("generic.pdf", io.BytesIO(pdf_content), "application/pdf")}
        form_data = {
            "skills": "s",
            "experience": "e",
            "education": "d",
        }  # This will take the new user path

        response = client.post("/api/upload-cv", files=files, data=form_data)

        assert response.status_code == 500
        # Now the detail should match, because UserModel.create didn't fail due to DB connection
        assert (
            response.json()["detail"]
            == "An internal server error occurred during CV upload."
        )
    mock_user_model_create.assert_called_once()  # Verify user creation mock was called


def test_get_recommendations_success(
    client: TestClient,
    mock_resume_model_get_by_id,
    mock_recommendation_engine_get_recommendations,
):
    mock_resume_model_get_by_id.return_value = MOCK_RESUME_DATA
    mock_recommendation_engine_get_recommendations.return_value = (
        MOCK_RECOMMENDATIONS_PAYLOAD * 5
    )

    response = client.get(f"/api/recommendations/{VALID_RESUME_ID}?page=1&size=5")

    assert response.status_code == 200
    data = response.json()
    assert "recommendations" in data
    assert len(data["recommendations"]["items"]) == 5
    assert data["recommendations"]["items"][0] == MOCK_RECOMMENDATIONS_PAYLOAD[0]
    assert data["recommendations"]["page"] == 1
    assert data["recommendations"]["size"] == 5
    mock_resume_model_get_by_id.assert_called_once_with(VALID_RESUME_ID)
    mock_recommendation_engine_get_recommendations.assert_called_once_with(
        skills=MOCK_RESUME_DATA["skills"],
        experience=MOCK_RESUME_DATA["experience"],
        education=MOCK_RESUME_DATA["education"],
        location=MOCK_RESUME_DATA["location"],
        cache_key=f"resume_{VALID_RESUME_ID}_{MOCK_RESUME_DATA['location']}",
        force_refresh=False,
        page=1,
    )


def test_get_recommendations_resume_not_found(
    client: TestClient, mock_resume_model_get_by_id
):
    mock_resume_model_get_by_id.return_value = None
    non_existent_resume_id = 9999
    response = client.get(f"/api/recommendations/{non_existent_resume_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == f"Resume {non_existent_resume_id} not found"


def test_get_recommendations_with_location_override_and_refresh(
    client: TestClient,
    mock_resume_model_get_by_id,
    mock_recommendation_engine_get_recommendations,
):
    override_location = "Remote"
    mock_resume_model_get_by_id.return_value = MOCK_RESUME_DATA
    # FIX: Return enough items for page=2, size=3 (e.g., 4 items)
    mock_recommendations = [
        {"id": f"remotejob{i}", "title": f"Remote Role {i}"} for i in range(4)
    ]
    mock_recommendation_engine_get_recommendations.return_value = mock_recommendations

    response = client.get(
        f"/api/recommendations/{VALID_RESUME_ID}?location={override_location}&refresh=true&page=2&size=3"
    )
    assert response.status_code == 200
    data = response.json()["recommendations"]
    assert len(data["items"]) == 1  # 4 items total, size 3. Page 1 has 3, Page 2 has 1.
    assert data["items"][0]["title"] == "Remote Role 3"  # The 4th item
    assert data["page"] == 2  # This should now pass
    assert data["size"] == 3

    mock_recommendation_engine_get_recommendations.assert_called_once_with(
        skills=MOCK_RESUME_DATA["skills"],
        experience=MOCK_RESUME_DATA["experience"],
        education=MOCK_RESUME_DATA["education"],
        location=override_location,
        cache_key=f"resume_{VALID_RESUME_ID}_{override_location}",
        force_refresh=True,
        page=2,
    )


def test_get_recommendations_engine_exception(
    client: TestClient,
    mock_resume_model_get_by_id,
    mock_recommendation_engine_get_recommendations,
):
    mock_resume_model_get_by_id.return_value = MOCK_RESUME_DATA
    mock_recommendation_engine_get_recommendations.side_effect = Exception(
        "AI Engine exploded"
    )

    response = client.get(f"/api/recommendations/{VALID_RESUME_ID}")

    assert response.status_code == 500
    assert (
        response.json()["detail"]
        == f"Internal server error getting recommendations for resume {VALID_RESUME_ID}."
    )


def test_search_jobs_success(
    client: TestClient, mock_recommendation_engine_search_jobs
):
    search_query = "developer"
    search_location = "Kandy"
    mock_recommendation_engine_search_jobs.return_value = MOCK_SEARCH_RESULTS * 10

    response = client.get(
        f"/api/search-jobs?query={search_query}&location={search_location}&page=1&size=10"
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 10
    assert data["items"][0] == MOCK_SEARCH_RESULTS[0]
    assert data["page"] == 1
    assert data["size"] == 10
    mock_recommendation_engine_search_jobs.assert_called_once_with(
        query=search_query,
        location=search_location,
        cache_key=f"search_{search_query}_{search_location}",
        page=1,
        size=10,
        fetch_more=False,
    )


def test_search_jobs_missing_query(client: TestClient):
    response = client.get("/api/search-jobs?location=Colombo")
    assert response.status_code == 422


def test_search_jobs_engine_exception(
    client: TestClient, mock_recommendation_engine_search_jobs
):
    search_query = "tester"
    mock_recommendation_engine_search_jobs.side_effect = Exception(
        "Search system offline"
    )

    response = client.get(f"/api/search-jobs?query={search_query}")
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error during job search."


def test_get_job_stats_success(
    client: TestClient,
    mock_resume_model_get_by_id,
    mock_recommendation_engine_get_job_stats,
):
    mock_resume_model_get_by_id.return_value = MOCK_RESUME_DATA
    mock_recommendation_engine_get_job_stats.return_value = MOCK_JOB_STATS

    response = client.get(f"/api/job-stats/{VALID_RESUME_ID}")

    assert response.status_code == 200
    data = response.json()
    assert data["resume_id"] == VALID_RESUME_ID
    assert data["stats"] == MOCK_JOB_STATS
    mock_recommendation_engine_get_job_stats.assert_called_once_with(
        skills=MOCK_RESUME_DATA["skills"],
        experience=MOCK_RESUME_DATA["experience"],
        education=MOCK_RESUME_DATA["education"],
    )


def test_get_job_stats_resume_not_found(
    client: TestClient, mock_resume_model_get_by_id
):
    mock_resume_model_get_by_id.return_value = None
    non_existent_resume_id = 777
    response = client.get(f"/api/job-stats/{non_existent_resume_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == f"Resume {non_existent_resume_id} not found"


def test_get_job_stats_engine_exception(
    client: TestClient,
    mock_resume_model_get_by_id,
    mock_recommendation_engine_get_job_stats,
):
    mock_resume_model_get_by_id.return_value = MOCK_RESUME_DATA
    mock_recommendation_engine_get_job_stats.side_effect = Exception(
        "Stats engine broke"
    )
    response = client.get(f"/api/job-stats/{VALID_RESUME_ID}")
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error generating job stats."


def test_delete_cv_success(
    client: TestClient,
    mock_resume_model_get_by_id,
    mock_s3_delete,
    mock_resume_model_delete,
    mocker,
):
    mock_resume_data_with_url = {
        **MOCK_RESUME_DATA,
        "cv_url": f"https://{settings.S3_BUCKET_NAME}.s3.amazonaws.com/uploads/cv_to_delete.pdf",
    }
    mock_resume_model_get_by_id.return_value = mock_resume_data_with_url
    mock_s3_delete.return_value = True
    mock_resume_model_delete.return_value = True
    mock_clear_cache = mocker.patch(
        "app.services.ml.recommendation_engine.RecommendationEngine.clear_cache"
    )

    response = client.delete(f"/api/delete-cv/{VALID_RESUME_ID}")

    assert response.status_code == 200
    assert (
        response.json()["message"]
        == f"Resume with ID {VALID_RESUME_ID} processed for deletion. S3 status: True"
    )
    expected_s3_object_name = "uploads/cv_to_delete.pdf"
    mock_s3_delete.assert_called_once_with(expected_s3_object_name)
    mock_resume_model_delete.assert_called_once_with(VALID_RESUME_ID)
    mock_clear_cache.assert_called_once_with(
        f"resume_{VALID_RESUME_ID}_{mock_resume_data_with_url['location']}"
    )


def test_delete_cv_resume_not_found(client: TestClient, mock_resume_model_get_by_id):
    mock_resume_model_get_by_id.return_value = None
    response = client.delete(f"/api/delete-cv/{VALID_RESUME_ID}")
    assert response.status_code == 404
    assert f"Resume {VALID_RESUME_ID} not found" in response.json()["detail"]


def test_delete_cv_s3_delete_fails(
    client: TestClient,
    mock_resume_model_get_by_id,
    mock_s3_delete,
    mock_resume_model_delete,
    mocker,
):
    mock_resume_data_with_url = {
        **MOCK_RESUME_DATA,
        "cv_url": f"https://{settings.S3_BUCKET_NAME}.s3.amazonaws.com/uploads/cv_s3_fail.pdf",
    }
    mock_resume_model_get_by_id.return_value = mock_resume_data_with_url
    mock_s3_delete.return_value = False
    mock_resume_model_delete.return_value = True
    mock_clear_cache = mocker.patch(
        "app.services.ml.recommendation_engine.RecommendationEngine.clear_cache"
    )

    response = client.delete(f"/api/delete-cv/{VALID_RESUME_ID}")

    assert response.status_code == 200
    assert (
        response.json()["message"]
        == f"Resume with ID {VALID_RESUME_ID} processed for deletion. S3 status: False"
    )
    mock_s3_delete.assert_called_once()
    mock_resume_model_delete.assert_called_once()
    mock_clear_cache.assert_called_once()


def test_delete_cv_db_delete_fails(
    client: TestClient,
    mock_resume_model_get_by_id,
    mock_s3_delete,
    mock_resume_model_delete,
):
    mock_resume_data_with_url = {
        **MOCK_RESUME_DATA,
        "cv_url": "s3_url",
    }  # Ensure a cv_url to attempt s3 delete
    mock_resume_model_get_by_id.return_value = mock_resume_data_with_url
    mock_s3_delete.return_value = True  # Assume S3 delete would succeed or is called
    mock_resume_model_delete.return_value = False

    response = client.delete(f"/api/delete-cv/{VALID_RESUME_ID}")

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to delete resume record from database."
    mock_resume_model_delete.assert_called_once_with(VALID_RESUME_ID)


def test_delete_cv_no_cv_url_in_resume_data(
    client: TestClient,
    mock_resume_model_get_by_id,
    mock_s3_delete,
    mock_resume_model_delete,
    mocker,
):
    mock_resume_data_no_url = {**MOCK_RESUME_DATA, "cv_url": None}
    mock_resume_model_get_by_id.return_value = mock_resume_data_no_url
    mock_resume_model_delete.return_value = True
    mock_clear_cache = mocker.patch(
        "app.services.ml.recommendation_engine.RecommendationEngine.clear_cache"
    )

    response = client.delete(f"/api/delete-cv/{VALID_RESUME_ID}")

    assert response.status_code == 200
    assert (
        response.json()["message"]
        == f"Resume with ID {VALID_RESUME_ID} processed for deletion. S3 status: False"
    )
    mock_s3_delete.assert_not_called()
    mock_resume_model_delete.assert_called_once_with(VALID_RESUME_ID)
    mock_clear_cache.assert_called_once()


def test_delete_cv_s3_service_raises_exception(
    client: TestClient, mock_resume_model_get_by_id, mock_s3_delete
):
    mock_resume_data_with_url = {
        **MOCK_RESUME_DATA,
        "cv_url": f"https://{settings.S3_BUCKET_NAME}.s3.amazonaws.com/uploads/s3_exception.pdf",
    }
    mock_resume_model_get_by_id.return_value = mock_resume_data_with_url
    mock_s3_delete.side_effect = Exception("S3 service broke completely")

    response = client.delete(f"/api/delete-cv/{VALID_RESUME_ID}")
    assert response.status_code == 500
    assert "Internal server error during resume deletion." in response.json()["detail"]


def test_load_more_jobs_for_resume_id_success(
    client: TestClient,
    mock_resume_model_get_by_id,
    mock_recommendation_engine_get_recommendations,
):
    mock_resume_model_get_by_id.return_value = MOCK_RESUME_DATA
    mock_recs = [{"title": f"More Rec Job {i}"} for i in range(8)]
    mock_recommendation_engine_get_recommendations.return_value = mock_recs

    response = client.get(
        f"/api/load-more-jobs?resume_id={VALID_RESUME_ID}&page=2&size=7&location=TestCity"
    )
    assert response.status_code == 200
    data = response.json()["recommendations"]
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "More Rec Job 7"
    assert data["page"] == 2
    assert data["size"] == 7
    mock_recommendation_engine_get_recommendations.assert_called_with(
        skills=ANY,
        experience=ANY,
        education=ANY,
        location="TestCity",
        cache_key=f"resume_{VALID_RESUME_ID}_TestCity",
        force_refresh=False,
        page=2,
    )


def test_load_more_jobs_for_query_success(
    client: TestClient, mock_recommendation_engine_search_jobs
):
    query_val = "senior dev"
    location_val = "WFH"
    mock_search = [{"title": f"More Search Job {i}"} for i in range(17)]
    mock_recommendation_engine_search_jobs.return_value = mock_search

    response = client.get(
        f"/api/load-more-jobs?query={query_val}&location={location_val}&page=3&size=8"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "More Search Job 16"
    assert data["page"] == 3
    assert data["size"] == 8

    mock_recommendation_engine_search_jobs.assert_called_with(
        query=query_val,
        location=location_val,
        cache_key=f"search_{query_val}_{location_val}",
        page=3,
        size=8,
        fetch_more=True,
    )


def test_load_more_jobs_resume_not_found_forwarded(
    client: TestClient, mock_resume_model_get_by_id
):
    mock_resume_model_get_by_id.return_value = None
    resume_id_invalid = 333

    response = client.get(f"/api/load-more-jobs?resume_id={resume_id_invalid}&page=1")
    assert response.status_code == 404
    assert f"Resume {resume_id_invalid} not found" in response.json()["detail"]


def test_load_more_jobs_forwarded_generic_exception_from_recommendations(
    client: TestClient,
    mock_resume_model_get_by_id,
    mock_recommendation_engine_get_recommendations,
):
    mock_resume_model_get_by_id.return_value = MOCK_RESUME_DATA
    mock_recommendation_engine_get_recommendations.side_effect = Exception(
        "Rec engine internal error"
    )

    response = client.get(f"/api/load-more-jobs?resume_id={VALID_RESUME_ID}&page=1")
    assert response.status_code == 500
    assert (
        f"Internal server error getting recommendations for resume {VALID_RESUME_ID}."
        in response.json()["detail"]
    )


def test_load_more_jobs_forwarded_generic_exception_from_search(
    client: TestClient, mock_recommendation_engine_search_jobs
):
    mock_recommendation_engine_search_jobs.side_effect = Exception(
        "Search engine internal error"
    )

    response = client.get("/api/load-more-jobs?query=anything&page=1")
    assert response.status_code == 500
    assert "Internal server error during job search." in response.json()["detail"]


def test_load_more_jobs_missing_resume_id_and_query(client: TestClient):
    response = client.get("/api/load-more-jobs?page=1")
    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Requires 'resume_id' or 'query' for loading more jobs."
    )
