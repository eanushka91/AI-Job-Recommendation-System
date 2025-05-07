from sklearn.feature_extraction.text import TfidfVectorizer

from app.db.database import get_db_connection
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel


class RecommendationResult(BaseModel):
    """Pydantic model for recommendation results"""
    job_id: str
    title: str
    company: str
    location: str
    match_score: float
    description: str
    url: str
    date_posted: datetime


class JobRecommendationModel:
    """Database model for storing and retrieving job recommendations"""

    @staticmethod
    def save_recommendations(resume_id: int, recommendations: List[Dict[str, Any]]) -> bool:
        """
        Save job recommendations to the database
        """
        conn = None
        try:
            conn = get_db_connection()

            with conn.cursor() as cur:
                # Delete existing recommendations
                cur.execute(
                    "DELETE FROM job_recommendations WHERE resume_id = %s",
                    (resume_id,)
                )

                # Insert new recommendations
                for job in recommendations:
                    cur.execute(
                        """INSERT INTO job_recommendations 
                        (resume_id, job_id, job_title, company, location, 
                         description, url, match_score)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            resume_id,
                            job.get('id'),
                            job.get('title'),
                            job.get('company'),
                            job.get('location'),
                            job.get('description'),
                            job.get('url'),
                            job.get('match_score')
                        )
                    )
            conn.commit()
            return True
        except Exception as e:
            if conn: conn.rollback()
            print(f"Error saving recommendations: {str(e)}")
            return False
        finally:
            if conn: conn.close()

    @staticmethod
    def get_recommendations(resume_id: int, limit: int = 10) -> List[RecommendationResult]:
        """
        Retrieve stored recommendations from database
        """
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """SELECT * FROM job_recommendations 
                    WHERE resume_id = %s 
                    ORDER BY match_score DESC 
                    LIMIT %s""",
                    (resume_id, limit)
                )
                results = cur.fetchall()
                return [RecommendationResult(**row) for row in results]
        except Exception as e:
            print(f"Error retrieving recommendations: {str(e)}")
            return []
        finally:
            if conn: conn.close()


class MLModelConfig(BaseModel):
    """Configuration model for ML components"""
    tfidf_max_features: int = 10000
    tfidf_ngram_range: tuple = (1, 2)
    skill_weight: int = 3
    min_similarity_threshold: float = 0.2


class TrainedModel:
    """Wrapper for trained ML model components"""

    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=MLModelConfig.tfidf_max_features,
            ngram_range=MLModelConfig.tfidf_ngram_range
        )

    def fit(self, texts: List[str]):
        """Train the vectorizer"""
        self.vectorizer.fit(texts)

    def transform(self, text: str):
        """Transform text to TF-IDF vector"""
        return self.vectorizer.transform([text])