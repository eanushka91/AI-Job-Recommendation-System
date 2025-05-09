import sys
import os
import pytest
from fastapi.testclient import TestClient
import psycopg2
from psycopg2.extras import RealDictCursor

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
print(f"Project root added to sys.path in conftest: {PROJECT_ROOT}")

try:
    from app.main import app

    print("Successfully imported 'app' from app.main for conftest")
except ImportError as e_app_main:
    try:
        from main import app

        print("Successfully imported 'app' from main (project root) for conftest")
    except ImportError as e_main:
        app = None
        print(
            f"CRITICAL WARNING (conftest.py): FastAPI 'app' instance could not be imported. Error for 'app.main': {e_app_main}. Error for 'main': {e_main}. Client-dependent tests will be skipped."
        )

try:
    from app.config.settings import (
        DB_HOST as TEST_DB_HOST,
        DB_PORT as TEST_DB_PORT,
        DB_NAME as TEST_DB_NAME,
        DB_USER as TEST_DB_USER,
        DB_PASSWORD as TEST_DB_PASSWORD,
    )

    print(
        f"Test database settings loaded from app.config.settings for: {TEST_DB_NAME} on {TEST_DB_HOST}"
    )
except ImportError:
    print(
        "WARNING (conftest.py): Database settings could not be imported. Using placeholder/env values."
    )
    TEST_DB_HOST = os.getenv("TEST_DB_HOST", "localhost")
    TEST_DB_PORT = os.getenv("TEST_DB_PORT", "5432")
    TEST_DB_NAME = os.getenv(
        "TEST_DB_NAME", "test_db_placeholder"
    )
    TEST_DB_USER = os.getenv("TEST_DB_USER", "test_user_placeholder")
    TEST_DB_PASSWORD = os.getenv("TEST_DB_PASSWORD", "test_password_placeholder")


@pytest.fixture(scope="session")
def test_db_connection():
    conn = None
    try:
        conn = psycopg2.connect(
            host=TEST_DB_HOST,
            port=TEST_DB_PORT,
            dbname=TEST_DB_NAME,
            user=TEST_DB_USER,
            password=TEST_DB_PASSWORD,
        )
    except psycopg2.OperationalError as e:
        pytest.skip(f"TEST DB CONNECTION FAILED for '{TEST_DB_NAME}': {e}.")
        return None
    try:
        from app.db.database import create_tables

        create_tables(conn)
    except Exception as e:
        if conn:
            conn.close()
        pytest.skip(f"Table creation in test DB ('{TEST_DB_NAME}') failed: {e}.")
        return None
    yield conn
    if conn:
        conn.close()


@pytest.fixture(scope="function")
def db_session_for_integration(test_db_connection):
    # (Implementation remains the same as previous version - handles skipping)
    if not test_db_connection:
        pytest.skip("Skipping test due to unavailable 'test_db_connection'.")
        return None
    cursor = test_db_connection.cursor(cursor_factory=RealDictCursor)
    yield cursor
    test_db_connection.rollback()
    cursor.close()


@pytest.fixture(scope="module")
def client():
    """Provides a FastAPI TestClient instance for route testing."""
    if not app:
        pytest.skip(
            "FastAPI 'app' instance not loaded. Skipping client-dependent tests."
        )

    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
def mock_s3_upload(mocker):
    return mocker.patch(
        "app.services.s3_service.S3Service.upload_file",
        return_value="http://fake-s3-url.com/test.pdf",
    )


@pytest.fixture
def mock_s3_delete(mocker):
    return mocker.patch(
        "app.services.s3_service.S3Service.delete_file", return_value=True
    )


@pytest.fixture
def mock_user_model_create(mocker):
    return mocker.patch("app.db.models.UserModel.create", return_value=1)


@pytest.fixture
def mock_user_model_get_by_id(mocker):
    mock = mocker.patch("app.db.models.UserModel.get_by_id")
    mock.return_value = {"id": 1, "created_at": "2024-01-01T10:00:00Z"}
    return mock


@pytest.fixture
def mock_resume_model_create(mocker):
    return mocker.patch("app.db.models.ResumeModel.create", return_value=101)


@pytest.fixture
def mock_resume_model_get_by_id(mocker):
    mock = mocker.patch("app.db.models.ResumeModel.get_by_id")
    mock.return_value = {
        "id": 101,
        "user_id": 1,
        "cv_url": "http://fake-s3-url.com/test.pdf",
        "skills": ["python", "fastapi"],
        "experience": ["dev"],
        "education": ["bsc"],
        "location": "Testville",
    }
    return mock


@pytest.fixture
def mock_resume_model_delete(mocker):
    return mocker.patch("app.db.models.ResumeModel.delete", return_value=True)


@pytest.fixture
def mock_recommendation_engine_get_recommendations(mocker):
    mock = mocker.patch(
        "app.services.ml.recommendation_engine.RecommendationEngine.get_job_recommendations"
    )
    mock.return_value = [
        {"id": "rec_j1", "title": "R Job 1"},
        {"id": "rec_j2", "title": "R Job 2"},
    ]
    return mock


@pytest.fixture
def mock_recommendation_engine_search_jobs(mocker):
    mock = mocker.patch(
        "app.services.ml.recommendation_engine.RecommendationEngine.search_jobs"
    )
    mock.return_value = [{"id": "search_j1", "title": "S Job 1"}]
    return mock


@pytest.fixture
def mock_recommendation_engine_get_job_stats(mocker):
    mock = mocker.patch(
        "app.services.ml.recommendation_engine.RecommendationEngine.get_job_stats"
    )
    mock.return_value = {"total_matching_jobs": 5, "top_skills": ["pytest"]}
    return mock


@pytest.fixture
def mock_job_api_service_fetch_jobs(mocker):
    mock = mocker.patch("app.services.job_api_service.JobAPIService.fetch_jobs")
    mock.return_value = [{"id": "api_job_s1", "title": "Job From Service"}]
    return mock