import pytest
from unittest.mock import MagicMock, PropertyMock
import psycopg2
from datetime import datetime, timezone
import logging

from app.services.ml.ai_models import JobRecommendationModel, TrainedModel, RecommendationResult, MLModelConfig

test_logger = logging.getLogger("test_ai_models_logger")
test_logger.setLevel(logging.DEBUG)


@pytest.fixture
def mock_db_conn_for_ai_models(mocker):
    test_logger.debug("FIXTURE: mock_db_conn_for_ai_models setup started.")
    mock_conn = MagicMock(name="mock_connection_ai_models_instance")
    mock_cursor = MagicMock(name="mock_cursor_ai_models_instance")

    closed_property_mock = PropertyMock(return_value=False)
    type(mock_conn).closed = closed_property_mock

    def close_conn_side_effect(*args, **kwargs):
        closed_property_mock.return_value = True
        test_logger.debug("FIXTURE: mock_conn.close() called, mock_conn.closed is now True.")
    mock_conn.close.side_effect = close_conn_side_effect

    mock_conn.commit = MagicMock(name="mock_db_commit_method")
    mock_conn.rollback = MagicMock(name="mock_db_rollback_method")

    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.__enter__.return_value = mock_cursor
    mock_cursor.__exit__.return_value = None

    patch_target = 'app.services.ml.ai_models.get_db_connection'

    try:
        patcher = mocker.patch(patch_target, return_value=mock_conn)
        patcher.start()
        test_logger.debug(f"FIXTURE: Successfully patched '{patch_target}' with mock object ID: {id(mock_conn)}")
        try:
             import app.services.ml.ai_models
             test_logger.debug(f"FIXTURE: ID of get_db_connection inside ai_models after patch: {id(app.services.ml.ai_models.get_db_connection)}")
             test_logger.debug(f"FIXTURE: Is patched function the mock? {app.services.ml.ai_models.get_db_connection is mock_conn}")
             conn_from_patched = app.services.ml.ai_models.get_db_connection()
             test_logger.debug(f"FIXTURE: Call to patched function returned: {type(conn_from_patched)} (ID: {id(conn_from_patched)})")
        except Exception as patch_check_e:
             test_logger.error(f"FIXTURE: Error verifying patch for '{patch_target}': {patch_check_e}")

        yield mock_conn, mock_cursor

    finally:
        patcher.stop()
        test_logger.debug(f"FIXTURE: Stopped patch for '{patch_target}'.")
        test_logger.debug("FIXTURE: mock_db_conn_for_ai_models teardown finished.")


class TestJobRecommendationModel:

    def test_save_recommendations_success(self, mock_db_conn_for_ai_models, caplog):
        mock_conn, mock_cursor = mock_db_conn_for_ai_models
        caplog.set_level(logging.DEBUG)
        test_logger.debug(f"TEST_SAVE_SUCCESS: Initial mock_conn.closed: {mock_conn.closed}")
        resume_id = 1
        recommendations = [
            {"id": "job1", "title": "Dev", "match_score": 0.9, "company": "CompA", "location": "LocA",
             "description": "DescA", "url": "urlA"},
        ]
        mock_cursor.rowcount = 1

        success = JobRecommendationModel.save_recommendations(resume_id, recommendations)

        test_logger.debug(f"TEST_SAVE_SUCCESS: save_recommendations returned: {success}")
        test_logger.info(f"TEST_SAVE_SUCCESS: Application Logs:\n{caplog.text}")

        assert success is True, f"save_recommendations should return True on success. App Logs: {caplog.text}"
        assert mock_cursor.execute.call_count == 1, "DELETE should be called once"
        mock_cursor.executemany.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()
        assert mock_conn.closed is True

    def test_save_recommendations_db_error_on_delete(self, mock_db_conn_for_ai_models, caplog):
        mock_conn, mock_cursor = mock_db_conn_for_ai_models
        caplog.set_level(logging.DEBUG)
        test_logger.debug(f"TEST_SAVE_ERR_DELETE: Initial mock_conn.closed: {mock_conn.closed}")

        mock_cursor.execute.side_effect = psycopg2.Error("DB error during delete (simulated)")

        recommendations = [{"id": "job1", "title": "Dev"}]
        success = JobRecommendationModel.save_recommendations(1, recommendations)

        test_logger.debug(f"TEST_SAVE_ERR_DELETE: save_recommendations returned: {success}")
        test_logger.info(f"TEST_SAVE_ERR_DELETE: Application Logs:\n{caplog.text}")

        assert success is False, f"Should return False on DB error. App Logs: {caplog.text}"
        mock_cursor.execute.assert_called_once()
        mock_conn.rollback.assert_called_once()
        mock_conn.close.assert_called_once()
        mock_cursor.executemany.assert_not_called()
        assert mock_conn.closed is True

    def test_save_recommendations_db_error_on_insert(self, mock_db_conn_for_ai_models, caplog):
        mock_conn, mock_cursor = mock_db_conn_for_ai_models
        caplog.set_level(logging.DEBUG)
        test_logger.debug(f"TEST_SAVE_ERR_INSERT: Initial mock_conn.closed: {mock_conn.closed}")

        mock_cursor.executemany.side_effect = psycopg2.Error("DB error during insert (simulated)")
        mock_cursor.rowcount = 0

        recommendations = [{"id": "job1", "title": "Test Job"}]
        success = JobRecommendationModel.save_recommendations(1, recommendations)

        test_logger.debug(f"TEST_SAVE_ERR_INSERT: save_recommendations returned: {success}")
        test_logger.info(f"TEST_SAVE_ERR_INSERT: Application Logs:\n{caplog.text}")

        assert success is False, f"Should return False on insert error. App Logs: {caplog.text}"
        assert mock_cursor.execute.call_count == 1, "DELETE should be called once."
        mock_cursor.executemany.assert_called_once()
        mock_conn.rollback.assert_called_once()
        mock_conn.close.assert_called_once()
        assert mock_conn.closed is True

    def test_save_recommendations_empty_list(self, mock_db_conn_for_ai_models, caplog):
        mock_conn, mock_cursor = mock_db_conn_for_ai_models
        caplog.set_level(logging.DEBUG)
        test_logger.debug(f"TEST_SAVE_EMPTY: Initial mock_conn.closed: {mock_conn.closed}")
        mock_cursor.rowcount = 0

        success = JobRecommendationModel.save_recommendations(1, [])

        test_logger.debug(f"TEST_SAVE_EMPTY: save_recommendations returned: {success}")
        test_logger.info(f"TEST_SAVE_EMPTY: Application Logs:\n{caplog.text}")

        assert success is True, f"Should return True for empty list. App Logs: {caplog.text}"
        assert mock_cursor.execute.call_count == 1, "DELETE should be called once for empty list."
        mock_cursor.executemany.assert_not_called()
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()
        assert mock_conn.closed is True

    def test_get_recommendations_success(self, mock_db_conn_for_ai_models, caplog):
        mock_conn, mock_cursor = mock_db_conn_for_ai_models
        caplog.set_level(logging.DEBUG)
        test_logger.debug(f"TEST_GET_SUCCESS: Initial mock_conn.closed: {mock_conn.closed}")
        resume_id = 1
        current_time = datetime.now(timezone.utc)
        db_output = [
            {"job_id": "job1", "job_title": "Dev", "match_score": 0.9, "company": "CompA",
             "location": "LocA", "description": "DescA", "url": "urlA", "created_at": current_time}
        ]
        mock_cursor.fetchall.return_value = db_output

        recommendations = JobRecommendationModel.get_recommendations(resume_id, limit=5)

        test_logger.debug(f"TEST_GET_SUCCESS: Recommendations: {recommendations}")
        test_logger.info(f"TEST_GET_SUCCESS: Application Logs:\n{caplog.text}")

        assert len(recommendations) == 1, f"Expected 1 recommendation, got {len(recommendations)}. App Logs: {caplog.text}"
        if recommendations:
            assert isinstance(recommendations[0], RecommendationResult)
            assert recommendations[0].job_id == "job1"
            assert recommendations[0].created_at == current_time
        mock_cursor.execute.assert_called_once()
        mock_conn.close.assert_called_once()
        assert mock_conn.closed is True

    def test_get_recommendations_db_error(self, mock_db_conn_for_ai_models, caplog):
        mock_conn, mock_cursor = mock_db_conn_for_ai_models
        caplog.set_level(logging.DEBUG)
        test_logger.debug(f"TEST_GET_ERR: Initial mock_conn.closed: {mock_conn.closed}")
        mock_cursor.execute.side_effect = psycopg2.Error("DB error getting recs (simulated)")

        recommendations = JobRecommendationModel.get_recommendations(1)

        test_logger.debug(f"TEST_GET_ERR: Recommendations: {recommendations}")
        test_logger.info(f"TEST_GET_ERR: Application Logs:\n{caplog.text}")

        assert recommendations == [], f"Expected empty list on DB error. App Logs: {caplog.text}"
        mock_conn.close.assert_called_once()
        assert mock_conn.closed is True

    def test_get_recommendations_pydantic_validation_error(self, mock_db_conn_for_ai_models, caplog):
        mock_conn, mock_cursor = mock_db_conn_for_ai_models
        caplog.set_level(logging.WARNING)
        test_logger.debug(f"TEST_GET_PYD_ERR: Initial mock_conn.closed: {mock_conn.closed}")
        resume_id = 1
        current_time = datetime.now(timezone.utc)
        db_output_invalid = [
            {"job_id": "pyd_invalid1", "job_title": "Invalid Job",
             "match_score": "NOT_A_FLOAT_VALUE", # Invalid type
             "company": "Test Corp", "location": "Testville", "description": "Test desc", "url": "test.com",
             "created_at": current_time }
        ]
        mock_cursor.fetchall.return_value = db_output_invalid

        recommendations = JobRecommendationModel.get_recommendations(resume_id)

        test_logger.debug(f"TEST_GET_PYD_ERR: Recommendations: {recommendations}")
        test_logger.info(f"TEST_GET_PYD_ERR: Captured App Logs (WARNING+):\n{caplog.text}")

        assert len(recommendations) == 0, f"Expected 0 valid recommendations. App Logs: {caplog.text}"
        assert "Could not validate recommendation row" in caplog.text, "Validation error message missing."
        assert "pyd_invalid1" in caplog.text, "Problematic job_id missing in log."
        assert "NOT_A_FLOAT_VALUE" in caplog.text, "Invalid data missing in log."
        mock_conn.close.assert_called_once()
        assert mock_conn.closed is True

class TestTrainedModel:
    def test_init_default_config(self):
        model = TrainedModel()
        assert isinstance(model.config, MLModelConfig)
        assert model.vectorizer.max_features == 10000
        assert model.vectorizer.ngram_range == (1, 2)
        assert model.vectorizer.min_df == 1
        assert model._is_fitted is False

    def test_init_custom_config(self):
        custom_config = MLModelConfig(tfidf_max_features=500, tfidf_ngram_range=(1, 1))
        model = TrainedModel(config=custom_config)
        assert model.vectorizer.max_features == 500
        assert model.vectorizer.ngram_range == (1, 1)
        assert model.vectorizer.min_df == 1

    def test_fit_success(self):
        model = TrainedModel()
        texts = ["this is a document", "another document here", "document three"]
        model.fit(texts)
        assert model._is_fitted is True

    def test_fit_empty_texts(self, caplog):
        model = TrainedModel()
        caplog.set_level(logging.WARNING)
        model.fit([])
        assert model._is_fitted is False
        assert "TrainedModel fit: Cannot fit on empty text list." in caplog.text

    def test_fit_vectorizer_value_error(self, mocker, caplog):
        model = TrainedModel()
        caplog.set_level(logging.ERROR)
        mocker.patch.object(model.vectorizer, 'fit', side_effect=ValueError("Mocked TFIDF ValueError: empty vocabulary"))
        model.fit(["text that causes error"])
        assert model._is_fitted is False
        assert "Error fitting vectorizer: Mocked TFIDF ValueError: empty vocabulary" in caplog.text

    def test_transform_not_fitted(self):
        model = TrainedModel()
        with pytest.raises(RuntimeError, match="Vectorizer is not fitted."):
            model.transform("some text")

    def test_transform_success(self):
        model = TrainedModel()
        texts = ["this is a document", "another document here"]
        model.fit(texts)
        vector = model.transform("this is a document")
        assert vector is not None
        assert vector.shape[0] == 1
        assert vector.shape[1] > 0

    def test_transform_empty_text_after_fit(self, caplog):
        model = TrainedModel()
        caplog.set_level(logging.WARNING)
        model.fit(["sample document to ensure vectorizer is fitted"])
        vector = model.transform("")
        assert "Input text is empty or invalid type" in caplog.text
        assert vector is not None
        assert vector.nnz == 0

    def test_transform_vectorizer_error_after_fit(self, mocker, caplog):
        model = TrainedModel()
        caplog.set_level(logging.ERROR)
        model.fit(["sample document"])
        mocker.patch.object(model.vectorizer, 'transform', side_effect=Exception("Mocked Transform Process Error"))
        with pytest.raises(Exception, match="Mocked Transform Process Error"):
            model.transform("test text")
        assert "Error transforming text: Mocked Transform Process Error" in caplog.text