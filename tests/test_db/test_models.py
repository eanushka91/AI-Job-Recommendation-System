# tests/test_db/test_models.py

import pytest
import psycopg2 # For raising psycopg2 specific errors in mocks if needed
from psycopg2.extras import RealDictCursor
from app.db.models import UserModel, ResumeModel
# from app.config import settings # Removed F401 - Settings likely not needed directly here if DB is mocked

# Fixture to mock DB connection and cursor for model tests
@pytest.fixture
def mock_db_connection_for_models(mocker):
    """Mocks get_db_connection used by models and provides mock conn/cursor."""
    mock_conn = mocker.MagicMock(name="mock_connection", closed=False)
    mock_cursor = mocker.MagicMock(name="mock_cursor")
    # Setup context manager for 'with conn.cursor() as cur:'
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value.__exit__.return_value = None
    # Patch the function called by the models
    mocker.patch("app.db.models.get_db_connection", return_value=mock_conn)
    return mock_conn, mock_cursor

# --- UserModel Tests ---
class TestUserModel:
    def test_create_user_success(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        expected_user_id = 55
        mock_cursor.fetchone.return_value = (expected_user_id,)

        user_id = UserModel.create()

        assert user_id == expected_user_id
        mock_cursor.execute.assert_called_once() # Basic check, can check SQL string too
        assert "INSERT INTO users" in mock_cursor.execute.call_args[0][0]
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_create_user_db_error(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        mock_cursor.execute.side_effect = psycopg2.Error("Simulated DB error on create")

        # Check if the method now returns None on error instead of raising
        user_id = UserModel.create()
        assert user_id is None
        # Or if it still raises:
        # with pytest.raises(psycopg2.Error, match="Simulated DB error on create"):
        #     UserModel.create()

        mock_conn.rollback.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_get_user_by_id_found(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        user_id_to_find = 10
        expected_user_data = {"id": user_id_to_find, "created_at": "some_datetime"}
        mock_cursor.fetchone.return_value = expected_user_data

        user = UserModel.get_by_id(user_id_to_find)

        assert user == expected_user_data
        mock_cursor.execute.assert_called_once_with(
            "SELECT id, created_at FROM users WHERE id = %s", (user_id_to_find,)
        )
        # Check if RealDictCursor was requested
        mock_conn.cursor.assert_called_with(cursor_factory=RealDictCursor)
        mock_conn.close.assert_called_once()

    def test_get_user_by_id_not_found(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        mock_cursor.fetchone.return_value = None # Simulate DB returning nothing

        user = UserModel.get_by_id(99)
        assert user is None
        mock_conn.close.assert_called_once()

# --- ResumeModel Tests ---
class TestResumeModel:
    # Add tests for ResumeModel methods (create, get_by_id, get_by_user_id, delete, etc.)
    # using the mock_db_connection_for_models fixture similar to UserModel tests.

    def test_create_resume_success(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        expected_resume_id = 201
        mock_cursor.fetchone.return_value = (expected_resume_id,)
        resume_data = {
            "user_id": 5, "cv_url": "s3://bucket/cv.pdf",
            "skills": ["a", "b"], "experience": ["exp1"], "education": ["edu1"]
        }

        resume_id = ResumeModel.create(**resume_data)

        assert resume_id == expected_resume_id
        mock_cursor.execute.assert_called_once()
        sql_args = mock_cursor.execute.call_args[0]
        assert "INSERT INTO resumes" in sql_args[0]
        # Check if lists are passed correctly in the arguments tuple
        assert sql_args[1][2] == resume_data["skills"] # Check skills list
        assert "::TEXT[]" in sql_args[0] # Check if casting is used
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_delete_resume_success(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        resume_id_to_delete = 50
        mock_cursor.rowcount = 1 # Simulate that 1 row was deleted

        deleted = ResumeModel.delete(resume_id_to_delete)

        assert deleted is True
        mock_cursor.execute.assert_called_once_with(
            "DELETE FROM resumes WHERE id = %s", (resume_id_to_delete,)
        )
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_delete_resume_not_found(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        resume_id_to_delete = 99
        mock_cursor.rowcount = 0 # Simulate that 0 rows were deleted

        deleted = ResumeModel.delete(resume_id_to_delete)

        assert deleted is False # Or True depending on desired behavior
        mock_cursor.execute.assert_called_once_with(
            "DELETE FROM resumes WHERE id = %s", (resume_id_to_delete,)
        )
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    # Add tests for get_by_id, get_by_user_id, save_recommendations, get_recommendations...
