import pytest
import psycopg2
from psycopg2.extras import RealDictCursor
from app.db.models import UserModel, ResumeModel  # Assuming models.py is in app.db

@pytest.fixture
def mock_db_connection_for_models(mocker):
    mock_conn = mocker.MagicMock(name="mock_connection", closed=False)
    mock_cursor = mocker.MagicMock(name="mock_cursor")
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value.__exit__.return_value = None
    mocker.patch("app.db.models.get_db_connection", return_value=mock_conn)
    return mock_conn, mock_cursor


@pytest.fixture
def mock_get_db_connection_fails(mocker):
    mocker.patch("app.db.models.get_db_connection", return_value=None)


@pytest.fixture
def mock_get_db_connection_raises_error(mocker):
    mocker.patch("app.db.models.get_db_connection", side_effect=psycopg2.Error("Connection failed"))


class TestUserModel:

    def test_create_user_fetchone_returns_none(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        mock_cursor.fetchone.return_value = None

        user_id = UserModel.create()
        assert user_id is None
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_create_user_get_connection_fails(self, mock_get_db_connection_fails):
        user_id = UserModel.create()
        assert user_id is None

    def test_create_user_get_connection_raises_error(self, mock_get_db_connection_raises_error):
        user_id = UserModel.create()
        assert user_id is None

    def test_get_user_by_id_get_connection_fails(self, mock_get_db_connection_fails):
        user = UserModel.get_by_id(1)
        assert user is None

    def test_get_user_by_id_get_connection_raises_error(self, mock_get_db_connection_raises_error):
        user = UserModel.get_by_id(1)
        assert user is None

    def test_get_user_by_id_db_error(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        mock_cursor.execute.side_effect = psycopg2.Error("Simulated DB error on get")
        user = UserModel.get_by_id(1)
        assert user is None
        mock_conn.close.assert_called_once()


class TestResumeModel:
    resume_data_sample = {
        "user_id": 1, "cv_url": "s3://url/cv.pdf",
        "skills": ["Python"], "experience": ["Dev"], "education": ["BSc"], "location": "Office"
    }
    recommendations_sample = [
        {"id": "job1", "title": "Dev", "company": "A", "location": "B", "description": "C", "url": "D",
         "match_score": 0.9}
    ]

    def test_create_resume_fetchone_returns_none(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        mock_cursor.fetchone.return_value = None
        resume_id = ResumeModel.create(**self.resume_data_sample)
        assert resume_id is None
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_create_resume_db_error(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        mock_cursor.execute.side_effect = psycopg2.Error("DB create error")
        resume_id = ResumeModel.create(**self.resume_data_sample)
        assert resume_id is None
        mock_conn.rollback.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_create_resume_get_connection_fails(self, mock_get_db_connection_fails):
        resume_id = ResumeModel.create(**self.resume_data_sample)
        assert resume_id is None

    def test_get_resume_by_id_found(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        expected_data = {"id": 1, **self.resume_data_sample}
        mock_cursor.fetchone.return_value = expected_data
        resume = ResumeModel.get_by_id(1)
        assert resume == expected_data
        mock_conn.cursor.assert_called_with(cursor_factory=RealDictCursor)
        mock_conn.close.assert_called_once()

    def test_get_resume_by_id_not_found(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        mock_cursor.fetchone.return_value = None
        resume = ResumeModel.get_by_id(1)
        assert resume is None
        mock_conn.close.assert_called_once()

    def test_get_resume_by_id_db_error(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        mock_cursor.execute.side_effect = psycopg2.Error("DB get error")
        resume = ResumeModel.get_by_id(1)
        assert resume is None
        mock_conn.close.assert_called_once()

    def test_get_resume_by_id_get_connection_fails(self, mock_get_db_connection_fails):
        resume = ResumeModel.get_by_id(1)
        assert resume is None

    def test_get_resumes_by_user_id_success(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        expected_data = [{"id": 1, **self.resume_data_sample}]
        mock_cursor.fetchall.return_value = expected_data
        resumes = ResumeModel.get_by_user_id(1)
        assert resumes == expected_data
        mock_cursor.execute.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_get_resumes_by_user_id_empty(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        mock_cursor.fetchall.return_value = []
        resumes = ResumeModel.get_by_user_id(1)
        assert resumes == []
        mock_conn.close.assert_called_once()

    def test_get_resumes_by_user_id_db_error(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        mock_cursor.execute.side_effect = psycopg2.Error("DB get error")
        resumes = ResumeModel.get_by_user_id(1)
        assert resumes == []
        mock_conn.close.assert_called_once()

    def test_get_resumes_by_user_id_get_connection_fails(self, mock_get_db_connection_fails):
        resumes = ResumeModel.get_by_user_id(1)
        assert resumes == []

    def test_delete_resume_db_error(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        mock_cursor.execute.side_effect = psycopg2.Error("DB delete error")
        deleted = ResumeModel.delete(1)
        assert deleted is False
        mock_conn.rollback.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_delete_resume_get_connection_fails(self, mock_get_db_connection_fails):
        deleted = ResumeModel.delete(1)
        assert deleted is False

    def test_save_recommendations_success(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        mock_cursor.rowcount = len(self.recommendations_sample)  # For executemany

        success = ResumeModel.save_recommendations(1, self.recommendations_sample)

        assert success is True
        assert mock_cursor.execute.call_count == 1
        mock_cursor.executemany.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_save_recommendations_empty_list(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        success = ResumeModel.save_recommendations(1, [])
        assert success is True
        mock_cursor.execute.assert_called_once()
        mock_cursor.executemany.assert_not_called()
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_save_recommendations_invalid_job_in_list(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        invalid_recs = ["not a dict"] + self.recommendations_sample
        mock_cursor.rowcount = len(self.recommendations_sample)

        success = ResumeModel.save_recommendations(1, invalid_recs)

        assert success is True
        assert mock_cursor.execute.call_count == 1
        args, _ = mock_cursor.executemany.call_args
        assert len(args[1]) == len(self.recommendations_sample)
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_save_recommendations_db_error_on_delete(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        mock_cursor.execute.side_effect = psycopg2.Error("DB delete error")
        success = ResumeModel.save_recommendations(1, self.recommendations_sample)
        assert success is False
        mock_conn.rollback.assert_called_once()
        mock_conn.close.assert_called_once()
        mock_cursor.executemany.assert_not_called()

    def test_save_recommendations_db_error_on_insert(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        mock_cursor.executemany.side_effect = psycopg2.Error("DB insert error")
        success = ResumeModel.save_recommendations(1, self.recommendations_sample)
        assert success is False
        mock_conn.rollback.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_save_recommendations_get_connection_fails(self, mock_get_db_connection_fails):
        success = ResumeModel.save_recommendations(1, self.recommendations_sample)
        assert success is False

    def test_get_recommendations_success(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        mock_cursor.fetchall.return_value = self.recommendations_sample
        results = ResumeModel.get_recommendations(1)
        assert results == self.recommendations_sample
        mock_cursor.execute.assert_called_once()
        mock_conn.cursor.assert_called_with(cursor_factory=RealDictCursor)
        mock_conn.close.assert_called_once()

    def test_get_recommendations_empty(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        mock_cursor.fetchall.return_value = []
        results = ResumeModel.get_recommendations(1)
        assert results == []
        mock_conn.close.assert_called_once()

    def test_get_recommendations_db_error(self, mock_db_connection_for_models):
        mock_conn, mock_cursor = mock_db_connection_for_models
        mock_cursor.execute.side_effect = psycopg2.Error("DB get error")
        results = ResumeModel.get_recommendations(1)
        assert results == []
        mock_conn.close.assert_called_once()

    def test_get_recommendations_get_connection_fails(self, mock_get_db_connection_fails):
        results = ResumeModel.get_recommendations(1)
        assert results == []