import pytest
import psycopg2 # For raising psycopg2 specific errors in mocks if needed
from psycopg2.extras import RealDictCursor
from app.db.models import UserModel, ResumeModel
# Assuming get_db_connection is in app.db.database
# from app.db.database import get_db_connection (We will mock this)
from app.config import settings # Database settings (if needed for asserts, though mostly mocked)

# --- Mock Fixtures for Database Connection and Cursor ---
# මේ fixtures `conftest.py` එකට දාන්නත් පුළුවන්.
# හැබැයි models test වලට විතරක් specific නිසා මෙතන තියන්නත් පුළුවන්.

@pytest.fixture
def mock_db_connection(mocker):
    """Mocks the database connection and cursor."""
    mock_conn = mocker.MagicMock(name="mock_connection")
    mock_cursor = mocker.MagicMock(name="mock_cursor")

    # Setup mock_conn.cursor() to return a context manager that yields mock_cursor
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value.__exit__.return_value = None # Handle __exit__

    # Mock the get_db_connection function to return this mock_conn
    mocker.patch("app.db.models.get_db_connection", return_value=mock_conn)
    # Also patch in database.py if models import it directly from there for some reason
    # mocker.patch("app.db.database.get_db_connection", return_value=mock_conn)
    return mock_conn, mock_cursor

# --- UserModel Tests ---

class TestUserModel:
    def test_create_user_success(self, mock_db_connection):
        mock_conn, mock_cursor = mock_db_connection
        expected_user_id = 123
        mock_cursor.fetchone.return_value = (expected_user_id,) # RETURNING id gives a tuple

        user_id = UserModel.create()

        assert user_id == expected_user_id
        mock_cursor.execute.assert_called_once_with(
            """
                    INSERT INTO users DEFAULT VALUES
                    RETURNING id
                    """
        )
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_create_user_db_error(self, mock_db_connection):
        mock_conn, mock_cursor = mock_db_connection
        # Simulate a database error during execute
        mock_cursor.execute.side_effect = psycopg2.Error("Simulated DB error")

        with pytest.raises(psycopg2.Error, match="Simulated DB error"):
            UserModel.create()

        mock_conn.rollback.assert_called_once() # Ensure rollback on error
        mock_conn.close.assert_called_once()

    def test_get_user_by_id_found(self, mock_db_connection):
        mock_conn, mock_cursor = mock_db_connection
        user_id_to_find = 1
        expected_user_data = {"id": user_id_to_find, "created_at": "some_timestamp"}
        mock_cursor.fetchone.return_value = expected_user_data

        user = UserModel.get_by_id(user_id_to_find)

        assert user == expected_user_data
        mock_cursor.execute.assert_called_once_with(
            """
                    SELECT * FROM users WHERE id = %s
                    """,
            (user_id_to_find,)
        )
        # Ensure cursor_factory was used
        mock_conn.cursor.assert_called_with(cursor_factory=RealDictCursor)
        mock_conn.close.assert_called_once()
        mock_conn.commit.assert_not_called() # get_by_id shouldn't commit

    def test_get_user_by_id_not_found(self, mock_db_connection):
        mock_conn, mock_cursor = mock_db_connection
        user_id_to_find = 999
        mock_cursor.fetchone.return_value = None # Simulate user not found

        user = UserModel.get_by_id(user_id_to_find)

        assert user is None
        mock_cursor.execute.assert_called_once_with(
            """
                    SELECT * FROM users WHERE id = %s
                    """,
            (user_id_to_find,)
        )
        mock_conn.close.assert_called_once()

# --- ResumeModel Tests ---

class TestResumeModel:
    def test_create_resume_success(self, mock_db_connection):
        mock_conn, mock_cursor = mock_db_connection
        expected_resume_id = 101
        mock_cursor.fetchone.return_value = (expected_resume_id,)

        resume_data = {
            "user_id": 1,
            "cv_url": "http://s3.com/cv.pdf",
            "skills": ["python", "fastapi"],
            "experience": ["dev role"],
            "education": ["bsc"]
        }
        resume_id = ResumeModel.create(**resume_data)

        assert resume_id == expected_resume_id
        mock_cursor.execute.assert_called_once_with(
            """
                    INSERT INTO resumes (user_id, cv_url, skills, experience, education)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
            (
                resume_data["user_id"],
                resume_data["cv_url"],
                resume_data["skills"],
                resume_data["experience"],
                resume_data["education"]
            )
        )
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_create_resume_db_error(self, mock_db_connection):
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.execute.side_effect = psycopg2.Error("Create resume failed")
        resume_data = {
            "user_id": 1, "cv_url": "url", "skills": [], "experience": [], "education": []
        }

        with pytest.raises(psycopg2.Error, match="Create resume failed"):
            ResumeModel.create(**resume_data)

        mock_conn.rollback.assert_called_once()
        mock_conn.close.assert_called_once()


    def test_get_resume_by_id_found(self, mock_db_connection):
        mock_conn, mock_cursor = mock_db_connection
        resume_id_to_find = 101
        expected_resume_data = {"id": resume_id_to_find, "user_id": 1, "cv_url": "url"}
        mock_cursor.fetchone.return_value = expected_resume_data

        resume = ResumeModel.get_by_id(resume_id_to_find)

        assert resume == expected_resume_data
        mock_cursor.execute.assert_called_once_with(
            """
                    SELECT * FROM resumes WHERE id = %s
                    """,
            (resume_id_to_find,)
        )
        mock_conn.cursor.assert_called_with(cursor_factory=RealDictCursor)
        mock_conn.close.assert_called_once()

    def test_get_resume_by_id_not_found(self, mock_db_connection):
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = None

        resume = ResumeModel.get_by_id(999)
        assert resume is None
        mock_conn.close.assert_called_once()

    def test_get_resumes_by_user_id_found(self, mock_db_connection):
        mock_conn, mock_cursor = mock_db_connection
        user_id_to_find = 1
        expected_resumes = [
            {"id": 101, "user_id": user_id_to_find, "cv_url": "url1"},
            {"id": 102, "user_id": user_id_to_find, "cv_url": "url2"}
        ]
        mock_cursor.fetchall.return_value = expected_resumes

        resumes = ResumeModel.get_by_user_id(user_id_to_find)

        assert resumes == expected_resumes
        mock_cursor.execute.assert_called_once_with(
            """
                    SELECT * FROM resumes WHERE user_id = %s ORDER BY created_at DESC
                    """,
            (user_id_to_find,)
        )
        mock_conn.cursor.assert_called_with(cursor_factory=RealDictCursor)
        mock_conn.close.assert_called_once()

    def test_get_resumes_by_user_id_none_found(self, mock_db_connection):
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = []

        resumes = ResumeModel.get_by_user_id(1)
        assert resumes == []
        mock_conn.close.assert_called_once()

    def test_save_recommendations_success(self, mock_db_connection):
        mock_conn, mock_cursor = mock_db_connection
        resume_id = 1
        recommendations_data = [
            {'id': 'job1', 'title': 'Dev', 'company': 'CompA', 'location': 'LocA', 'description': 'DescA', 'url': 'urlA', 'match_score': 90.0},
            {'id': 'job2', 'title': 'Eng', 'company': 'CompB', 'location': 'LocB', 'description': 'DescB', 'url': 'urlB', 'match_score': 85.0}
        ]

        # Mock the sequence of calls to cursor.execute
        # 1. CREATE TABLE IF NOT EXISTS
        # 2. DELETE FROM job_recommendations
        # 3. INSERT for job1
        # 4. INSERT for job2
        # We can check the number of calls or be more specific if needed.
        # For simplicity, we'll check the number of execute calls and commit.

        result = ResumeModel.save_recommendations(resume_id, recommendations_data)

        assert result is True
        # Check calls (1 for CREATE TABLE, 1 for DELETE, N for INSERTs)
        assert mock_cursor.execute.call_count == 2 + len(recommendations_data)

        # Check CREATE TABLE call
        create_table_call = mock_cursor.execute.call_args_list[0]
        assert "CREATE TABLE IF NOT EXISTS job_recommendations" in create_table_call[0][0]

        # Check DELETE call
        delete_call = mock_cursor.execute.call_args_list[1]
        assert delete_call[0][0] == "DELETE FROM job_recommendations WHERE resume_id = %s"
        assert delete_call[0][1] == (resume_id,)

        # Check one of the INSERT calls (e.g., the first one)
        insert_call_1 = mock_cursor.execute.call_args_list[2]
        assert "INSERT INTO job_recommendations" in insert_call_1[0][0]
        expected_insert_args_1 = (
            resume_id,
            recommendations_data[0]['id'],
            recommendations_data[0]['title'],
            recommendations_data[0]['company'],
            recommendations_data[0]['location'],
            recommendations_data[0]['description'],
            recommendations_data[0]['url'],
            recommendations_data[0]['match_score']
        )
        assert insert_call_1[0][1] == expected_insert_args_1

        assert mock_conn.commit.call_count == 2 # One after CREATE TABLE, one after all INSERTs
        mock_conn.close.assert_called_once()

    def test_save_recommendations_db_error_on_insert(self, mock_db_connection):
        mock_conn, mock_cursor = mock_db_connection
        resume_id = 1
        recommendations_data = [{'id': 'job1', 'title': 'Dev'}] # Simplified

        # Simulate error on the INSERT statement (after CREATE and DELETE)
        # First call (CREATE TABLE) is fine.
        # Second call (DELETE) is fine.
        # Third call (INSERT) will raise an error.
        mock_cursor.execute.side_effect = [
            None, # For CREATE TABLE
            None, # For DELETE
            psycopg2.Error("Insert failed") # For INSERT
        ]

        result = ResumeModel.save_recommendations(resume_id, recommendations_data)

        assert result is False
        mock_conn.rollback.assert_called_once() # Rollback should be called due to error
        mock_conn.close.assert_called_once()

    def test_get_recommendations_found(self, mock_db_connection):
        mock_conn, mock_cursor = mock_db_connection
        resume_id = 1
        expected_recs = [
            {"job_id": "job1", "title": "Dev", "match_score": 90.0},
            {"job_id": "job2", "title": "Eng", "match_score": 85.0}
        ]
        mock_cursor.fetchall.return_value = expected_recs

        recs = ResumeModel.get_recommendations(resume_id)

        assert recs == expected_recs
        mock_cursor.execute.assert_called_once_with(
            """
                    SELECT * FROM job_recommendations 
                    WHERE resume_id = %s 
                    ORDER BY match_score DESC
                    """,
            (resume_id,)
        )
        mock_conn.cursor.assert_called_with(cursor_factory=RealDictCursor)
        mock_conn.close.assert_called_once()

    def test_get_recommendations_not_found(self, mock_db_connection):
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = []

        recs = ResumeModel.get_recommendations(1)
        assert recs == []
        mock_conn.close.assert_called_once()

    def test_get_recommendations_db_error(self, mock_db_connection):
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.execute.side_effect = psycopg2.Error("Get recs failed")

        recs = ResumeModel.get_recommendations(1)
        assert recs == [] # Should return empty list on error as per implementation
        mock_conn.close.assert_called_once()