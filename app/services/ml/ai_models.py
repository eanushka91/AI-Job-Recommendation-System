# app/services/ml/ai_models.py

from sklearn.feature_extraction.text import TfidfVectorizer
from app.db.database import get_db_connection
from psycopg2.extras import RealDictCursor
# Removed Optional from import as it was reported unused (F401)
# Keep List, Dict, Any if they are used elsewhere in the file.
from typing import List, Dict, Any
from datetime import datetime
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

class RecommendationResult(BaseModel):
    """Pydantic model for structuring recommendation results when retrieved."""
    job_id: str | None = None
    job_title: str | None = None
    company: str | None = None
    location: str | None = None
    match_score: float | None = None
    description: str | None = None
    url: str | None = None
    created_at: datetime | None = None # Matches DB schema column

class JobRecommendationModel:
    """
    Handles database operations specifically for job recommendations.
    NOTE: Consider consolidating with app/db/models.py -> ResumeModel.
    """

    @staticmethod
    def save_recommendations(resume_id: int, recommendations: List[Dict[str, Any]]) -> bool:
        """
        Save job recommendations to the database. Overwrites existing ones.
        """
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                logger.debug(f"Deleting existing recommendations for resume_id: {resume_id}")
                cur.execute("DELETE FROM job_recommendations WHERE resume_id = %s", (resume_id,))
                logger.info(f"Deleted {cur.rowcount} old recommendations for resume_id: {resume_id}")

                insert_query = """
                    INSERT INTO job_recommendations
                    (resume_id, job_id, job_title, company, location,
                     description, url, match_score)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                values_list = [
                    (
                        resume_id, job.get('id'), job.get('title'), job.get('company'),
                        job.get('location'), job.get('description'), job.get('url'),
                        job.get('match_score')
                    ) for job in recommendations if isinstance(job, dict)
                ]

                if not values_list:
                    logger.warning(f"No valid recommendations to save for resume_id: {resume_id}")
                    conn.commit() # Commit delete even if no inserts
                    return True

                logger.debug(f"Inserting {len(values_list)} new recommendations for resume_id: {resume_id}")
                cur.executemany(insert_query, values_list)
                logger.info(f"Successfully inserted {cur.rowcount} recommendations for resume_id: {resume_id}")

            conn.commit()
            return True
        except Exception as e:
            logger.exception(f"Error saving recommendations for resume_id {resume_id}: {e}")
            if conn: conn.rollback()
            return False
        finally:
            if conn: conn.close()

    @staticmethod
    def get_recommendations(resume_id: int, limit: int = 10) -> List[RecommendationResult]:
        """
        Retrieve stored recommendations from database, ordered by score.
        """
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """SELECT job_id, job_title, company, location, match_score,
                              description, url, created_at
                       FROM job_recommendations
                       WHERE resume_id = %s
                       ORDER BY match_score DESC, created_at DESC
                       LIMIT %s""",
                    (resume_id, limit)
                )
                results = cur.fetchall()
                logger.info(f"Retrieved {len(results)} recommendations from DB for resume_id: {resume_id}")
                valid_recommendations = []
                for row in results:
                    try:
                        valid_recommendations.append(RecommendationResult(**row))
                    except Exception as pydantic_error:
                        logger.warning(f"Could not validate recommendation row: {row}. Error: {pydantic_error}")
                return valid_recommendations
        except Exception as e:
            logger.exception(f"Error retrieving recommendations for resume_id {resume_id}: {e}")
            return []
        finally:
            if conn: conn.close()


class MLModelConfig(BaseModel):
    """Configuration model for ML components (e.g., TF-IDF parameters)."""
    tfidf_max_features: int = 10000
    tfidf_ngram_range: tuple[int, int] = (1, 2)

class TrainedModel:
    """Basic wrapper for a trained TF-IDF vectorizer."""
    def __init__(self, config: MLModelConfig = MLModelConfig()):
        self.config = config
        self.vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=self.config.tfidf_max_features,
            ngram_range=self.config.tfidf_ngram_range,
            min_df=1
        )
        self._is_fitted = False
        logger.info("TrainedModel initialized with TF-IDF vectorizer.")

    def fit(self, texts: List[str]):
        """Fit the TF-IDF vectorizer on the provided texts."""
        if not texts:
            logger.warning("TrainedModel fit: Cannot fit on empty text list.")
            return
        try:
            logger.info(f"TrainedModel: Fitting TF-IDF vectorizer on {len(texts)} texts...")
            self.vectorizer.fit(texts)
            self._is_fitted = True
            logger.info("TrainedModel: TF-IDF vectorizer fitted successfully.")
        except ValueError as ve:
            logger.error(f"TrainedModel fit: Error fitting vectorizer: {ve}")
            self._is_fitted = False
        except Exception as e:
            logger.exception(f"TrainedModel fit: Unexpected error fitting vectorizer: {e}")
            self._is_fitted = False

    def transform(self, text: str):
        """Transform a single text string into a TF-IDF vector."""
        if not self._is_fitted:
            logger.error("TrainedModel transform: Vectorizer has not been fitted yet.")
            raise RuntimeError("Vectorizer is not fitted.")
        if not text or not isinstance(text, str):
             logger.warning(f"TrainedModel transform: Input text is empty or invalid type ({type(text)}).")
             # Depending on desired behavior, might return zero vector or raise error
             # For now, let vectorizer handle it, which might raise error.
        try:
            logger.debug(f"TrainedModel: Transforming text (length: {len(text)})...")
            vector = self.vectorizer.transform([text])
            logger.debug(f"TrainedModel: Transformation successful (vector shape: {vector.shape}).")
            return vector
        except Exception as e:
             logger.exception(f"TrainedModel transform: Error transforming text: {e}")
             raise

# Ensure E701 is fixed: Check line 62 in your original file.
# If it looked like `if condition: statement`, change it to:
# if condition:
#     statement
