import sys
import os
import pytest
from fastapi.testclient import TestClient
import psycopg2
from psycopg2.extras import RealDictCursor

# Add the project root directory to the Python path
# This allows pytest to find the 'app' module
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

# --- Attempt to import the FastAPI app instance ---
# Adjust the import path based on where your 'app' instance is defined.
# Common locations: app/main.py or main.py in the project root.
try:
    from app.main import app  # If your FastAPI app instance is in app/main.py
    print("Successfully imported 'app' from app.main")
except ImportError:
    try:
        from main import app  # If your FastAPI app instance is in main.py (project root)
        print("Successfully imported 'app' from main (project root)")
    except ImportError:
        app = None  # App could not be imported
        print("CRITICAL WARNING: FastAPI 'app' instance could not be imported. Tests needing 'client' will fail or be skipped.")


# --- Optional: Database settings for Test Database (if using real test DB for some tests) ---
# It's highly recommended to use a separate configuration for your test database.
# These would ideally come from app.config.settings or a dedicated test settings file.
try:
    from app.config.settings import (
        DB_HOST as TEST_DB_HOST,
        DB_PORT as TEST_DB_PORT,
        DB_NAME as TEST_DB_NAME, # IMPORTANT: This should be a DEDICATED TEST DATABASE NAME
        DB_USER as TEST_DB_USER,
        DB_PASSWORD as TEST_DB_PASSWORD
    )
    print(f"Test database settings loaded for: {TEST_DB_NAME} on {TEST_DB_HOST}")
except ImportError:
    print("WARNING: Main database settings could not be imported from app.config.settings for test DB.")
    # Provide placeholder/default values if settings are not found,
    # but tests requiring a real DB connection will likely fail or be skipped.
    TEST_DB_HOST = "localhost"
    TEST_DB_PORT = "5432"
    TEST_DB_NAME = "your_test_db_name_placeholder" # CHANGE THIS
    TEST_DB_USER = "your_test_db_user_placeholder" # CHANGE THIS
    TEST_DB_PASSWORD = "your_test_db_password_placeholder" # CHANGE THIS


# --- Optional: Fixture for a real test database connection (for integration tests) ---
@pytest.fixture(scope="session")
def test_db_connection():
    """
    Manages a connection to the test database for the entire test session.
    Creates tables before tests and can clean up afterwards.
    """
    try:
        conn = psycopg2.connect(
            host=TEST_DB_HOST,
            port=TEST_DB_PORT,
            dbname=TEST_DB_NAME,
            user=TEST_DB_USER,
            password=TEST_DB_PASSWORD
        )
        print(f"Connected to test database: {TEST_DB_NAME}")
    except psycopg2.OperationalError as e:
        pytest.skip(f"TEST DATABASE CONNECTION FAILED: {e}. Skipping tests that require 'test_db_connection'. Ensure test database '{TEST_DB_NAME}' exists and credentials are correct.")
        return None

    try:
        from app.db.database import create_tables # Your function to create tables
        # Create tables in the test database
        # For a truly clean state, you might want to drop tables first.
        # Be extremely careful if TEST_DB_NAME is not a dedicated test database.
        # with conn.cursor() as cur:
        # cur.execute("DROP TABLE IF EXISTS job_recommendations CASCADE;")
        # cur.execute("DROP TABLE IF EXISTS resumes CASCADE;")
        # cur.execute("DROP TABLE IF EXISTS users CASCADE;")
        # conn.commit()
        create_tables(conn) # Assumes create_tables uses the passed connection
        print(f"Tables created in test database '{TEST_DB_NAME}'.")
    except ImportError:
        print("WARNING: 'app.db.database.create_tables' not found. Tables might not be set up for integration tests.")
    except Exception as e:
        print(f"ERROR creating tables in test_db_connection fixture: {e}")
        conn.close()
        pytest.skip(f"Table creation in test database failed: {e}.")
        return None

    yield conn  # Provide the connection to fixtures/tests that need it

    print(f"Closing test database connection to '{TEST_DB_NAME}'.")
    # Optional: Clean up by dropping tables after all tests in the session.
    # with conn.cursor() as cur:
    #     cur.execute("DROP TABLE IF EXISTS job_recommendations CASCADE;")
    #     cur.execute("DROP TABLE IF EXISTS resumes CASCADE;")
    #     cur.execute("DROP TABLE IF EXISTS users CASCADE;")
    # conn.commit()
    conn.close()

@pytest.fixture(scope="function")
def db_session_for_integration(test_db_connection):
    """
    Provides a transactional session for a single test function using the real test_db_connection.
    Rolls back changes after each test to ensure isolation.
    This is for integration tests that interact with the database.
    """
    if test_db_connection is None:
        pytest.skip("No active test database connection for 'db_session_for_integration'.")
        return None

    # Start a new transaction for each test
    # test_db_connection.autocommit = False # Ensure we are in a transaction block
    cursor = test_db_connection.cursor(cursor_factory=RealDictCursor)
    yield cursor # Test function uses this cursor

    # Rollback any changes made during the test to keep DB state clean
    test_db_connection.rollback()
    cursor.close()
    # print("Rolled back transaction for test function.")


# --- FastAPI Test Client Fixture ---
@pytest.fixture(scope="module") # Module scope is often sufficient for TestClient
def client():
    if app is None:
        pytest.skip("FastAPI 'app' instance not loaded. Cannot create TestClient.")
    with TestClient(app) as c:
        yield c

# --- Mocking Fixtures for Services and Models (used in Route/Unit tests) ---

@pytest.fixture
def mock_s3_upload(mocker):
    # Path to the method used in your application code (e.g., routes.py)
    return mocker.patch("app.services.s3_service.S3Service.upload_file", return_value="http://fake-s3-url.com/test.pdf")

@pytest.fixture
def mock_s3_delete(mocker):
    # Ensure S3Service.delete_file exists as defined in s3_service.py
    return mocker.patch("app.services.s3_service.S3Service.delete_file", return_value=True)

# --- Database Model Mocks (for isolating route logic from DB interactions) ---
@pytest.fixture
def mock_user_model_create(mocker):
    # Path to the method in app.db.models, as imported in routes.py
    return mocker.patch("app.db.models.UserModel.create", return_value=1) # Example: returns new user_id

@pytest.fixture
def mock_user_model_get_by_id(mocker):
    mock = mocker.patch("app.db.models.UserModel.get_by_id")
    mock.return_value = {"id": 1, "created_at": "2024-01-01T10:00:00Z"} # Example user data
    return mock

@pytest.fixture
def mock_resume_model_create(mocker):
    return mocker.patch("app.db.models.ResumeModel.create", return_value=101) # Example: returns new resume_id

@pytest.fixture
def mock_resume_model_get_by_id(mocker):
    mock = mocker.patch("app.db.models.ResumeModel.get_by_id")
    mock.return_value = { # Example resume data
        "id": 101,
        "user_id": 1,
        "cv_url": "http://fake-s3-url.com/test.pdf",
        "skills": ["python", "fastapi", "pytest"],
        "experience": ["Worked on testing"],
        "education": ["BSc Testology"],
        "location": "Testville" # Ensure this matches what your ResumeModel.get_by_id might return
    }
    return mock

@pytest.fixture
def mock_resume_model_delete(mocker):
    return mocker.patch("app.db.models.ResumeModel.delete", return_value=True)

# --- Recommendation Engine Mocks (for isolating route logic) ---
@pytest.fixture
def mock_recommendation_engine_get_recommendations(mocker):
    # Path to method as imported in routes.py
    mock = mocker.patch("app.services.ml.recommendation_engine.RecommendationEngine.get_job_recommendations")
    # This is the list of ALL recommendations before pagination by the `paginate` utility
    mock.return_value = [
        {"id": "rec_job1", "title": "Mocked Rec Job 1", "company": "MockRec", "match_score": 92.5},
        {"id": "rec_job2", "title": "Mocked Rec Job 2", "company": "MockRec", "match_score": 88.0},
        # Add more if your default page size is larger or you test pagination with more items
    ]
    return mock

@pytest.fixture
def mock_recommendation_engine_search_jobs(mocker):
    mock = mocker.patch("app.services.ml.recommendation_engine.RecommendationEngine.search_jobs")
    # This is the list of ALL search results before pagination
    mock.return_value = [
        {"id": "search_j1", "title": "Mocked Search Job 1", "company": "MockSearch", "match_score": 75.0}
    ]
    return mock

@pytest.fixture
def mock_recommendation_engine_get_job_stats(mocker):
    mock = mocker.patch("app.services.ml.recommendation_engine.RecommendationEngine.get_job_stats")
    mock.return_value = {
        "total_matching_jobs": 15,
        "top_skills": ["mocking", "pytest", "fastapi"],
        "locations": {"TestCity": 10, "Mockville": 5},
        "salary_range": {"min": 60000, "max": 120000, "avg": 90000},
        "job_types": {"Full-time": 12, "Contract": 3}
    }
    return mock

# --- JobAPIService Mock (if RecommendationEngine calls it and you want to isolate RE) ---
@pytest.fixture
def mock_job_api_service_fetch_jobs(mocker):
    # This would be used if you were testing RecommendationEngine itself
    # and wanted to mock its call to JobAPIService.
    # Path: app.services.job_api_service.JobAPIService.fetch_jobs
    mock = mocker.patch("app.services.job_api_service.JobAPIService.fetch_jobs")
    mock.return_value = [
        {"id": "api_job1", "title": "Job from Mocked API", "company": "API Corp", "content": "Job from Mocked API API Corp"}
    ]
    return mock