# app/db/models.py

from app.db.database import get_db_connection
from psycopg2.extras import RealDictCursor
# Removed Optional from import as it was reported unused (F401)
# Keep List, Dict, Any if they are used.
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class UserModel:
    """Model to handle database operations for users"""

    @staticmethod
    def create() -> int | None: # Return type hint
        """Create a new user and return the ID, or None on failure."""
        conn = None
        user_id = None
        try:
            conn = get_db_connection()
            if not conn: raise Exception("Failed to get DB connection")
            with conn.cursor() as cur:
                cur.execute("INSERT INTO users DEFAULT VALUES RETURNING id")
                result = cur.fetchone()
                if result: user_id = result[0]
                conn.commit()
                if user_id is None:
                     logger.error("Failed to retrieve user ID after insert.")
                     return None
                logger.info(f"Created user with ID: {user_id}")
                return user_id
        except Exception as e:
            logger.exception(f"Error creating user: {e}") # Log traceback
            if conn: conn.rollback()
            return None # Return None on error instead of raising for some scenarios
        finally:
            if conn: conn.close()

    @staticmethod
    def get_by_id(user_id: int) -> Dict[str, Any] | None: # Type hints
        """Get a user by ID"""
        conn = None
        try:
            conn = get_db_connection()
            if not conn: raise Exception("Failed to get DB connection")
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id, created_at FROM users WHERE id = %s", (user_id,))
                user = cur.fetchone()
                logger.debug(f"Fetched user by ID {user_id}: {'Found' if user else 'Not Found'}")
                return user
        except Exception as e:
             logger.exception(f"Error getting user by ID {user_id}: {e}")
             return None
        finally:
            if conn: conn.close()

class ResumeModel:
    """Model to handle database operations for resumes"""

    @staticmethod
    def create(user_id: int, cv_url: str, skills: List[str], experience: List[str], education: List[str]) -> int | None: # Type hints
        """Create a new resume entry in the database, return ID or None."""
        conn = None
        resume_id = None
        try:
            conn = get_db_connection()
            if not conn: raise Exception("Failed to get DB connection")
            with conn.cursor() as cur:
                # Ensure lists are passed correctly to PostgreSQL array type
                cur.execute(
                    """
                    INSERT INTO resumes (user_id, cv_url, skills, experience, education)
                    VALUES (%s, %s, %s::TEXT[], %s::TEXT[], %s::TEXT[])
                    RETURNING id
                    """,
                    (user_id, cv_url, skills, experience, education)
                )
                result = cur.fetchone()
                if result: resume_id = result[0]
                conn.commit()
                if resume_id is None:
                     logger.error(f"Failed to retrieve resume ID after insert for user {user_id}.")
                     return None
                logger.info(f"Created resume with ID: {resume_id} for user ID: {user_id}")
                return resume_id
        except Exception as e:
            logger.exception(f"Error creating resume for user {user_id}: {e}")
            if conn: conn.rollback()
            return None
        finally:
            if conn: conn.close()

    @staticmethod
    def get_by_id(resume_id: int) -> Dict[str, Any] | None: # Type hints
        """Get a resume by its ID"""
        conn = None
        try:
            conn = get_db_connection()
            if not conn: raise Exception("Failed to get DB connection")
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, user_id, cv_url, skills, experience, education, location, created_at
                    FROM resumes WHERE id = %s
                    """,
                    (resume_id,)
                )
                resume = cur.fetchone()
                logger.debug(f"Fetched resume by ID {resume_id}: {'Found' if resume else 'Not Found'}")
                return resume
        except Exception as e:
             logger.exception(f"Error getting resume by ID {resume_id}: {e}")
             return None
        finally:
            if conn: conn.close()

    @staticmethod
    def get_by_user_id(user_id: int) -> List[Dict[str, Any]]: # Type hints
        """Get all resumes for a specific user"""
        conn = None
        try:
            conn = get_db_connection()
            if not conn: raise Exception("Failed to get DB connection")
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, user_id, cv_url, skills, experience, education, location, created_at
                    FROM resumes WHERE user_id = %s ORDER BY created_at DESC
                    """,
                    (user_id,)
                )
                resumes = cur.fetchall()
                logger.debug(f"Fetched {len(resumes)} resumes for user ID {user_id}")
                return resumes
        except Exception as e:
             logger.exception(f"Error getting resumes for user ID {user_id}: {e}")
             return []
        finally:
            if conn: conn.close()

    @staticmethod
    def delete(resume_id: int) -> bool:
        """Deletes a resume record by its ID."""
        conn = None
        try:
            conn = get_db_connection()
            if not conn: raise Exception("Failed to get DB connection")
            with conn.cursor() as cur:
                cur.execute("DELETE FROM resumes WHERE id = %s", (resume_id,))
                deleted_count = cur.rowcount
                conn.commit()
                if deleted_count > 0:
                    logger.info(f"Successfully deleted resume record with ID: {resume_id}")
                    return True
                else:
                    logger.warning(f"Attempted to delete resume ID {resume_id}, but record not found.")
                    return False # Or True depending on desired idempotency behavior
        except Exception as e:
            logger.exception(f"Error deleting resume ID {resume_id}: {e}")
            if conn: conn.rollback()
            return False
        finally:
            if conn: conn.close()

    # --- Recommendation methods ---
    # These likely belong in their own model or service, or consolidated here.
    # Keeping them as provided in the ai_models.py context for now.
    @staticmethod
    def save_recommendations(resume_id: int, recommendations: List[Dict[str, Any]]) -> bool:
        """Save job recommendations for a resume"""
        # (Implementation from ai_models.py context, using logging)
        conn = None
        try:
            conn = get_db_connection()
            # ... (rest of implementation with logging as in ai_models.py) ...
            with conn.cursor() as cur:
                cur.execute("DELETE FROM job_recommendations WHERE resume_id = %s", (resume_id,))
                insert_query = """
                    INSERT INTO job_recommendations
                    (resume_id, job_id, job_title, company, location, description, url, match_score)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                values_list = [
                    (resume_id, job.get('id'), job.get('title'), job.get('company'), job.get('location'),
                     job.get('description'), job.get('url'), job.get('match_score'))
                    for job in recommendations if isinstance(job, dict)
                ]
                if values_list:
                    cur.executemany(insert_query, values_list)
            conn.commit()
            return True
        except Exception as e:
            logger.exception(f"Error saving recommendations for resume {resume_id}: {e}")
            if conn: conn.rollback()
            return False
        finally:
            if conn: conn.close()

    @staticmethod
    def get_recommendations(resume_id: int) -> List[Dict[str, Any]]:
        """Get stored job recommendations for a resume"""
        # (Implementation from ai_models.py context, using logging)
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT job_id, job_title, company, location, description, url, match_score, created_at
                    FROM job_recommendations
                    WHERE resume_id = %s
                    ORDER BY match_score DESC, created_at DESC
                    """, (resume_id,))
                results = cur.fetchall()
            return results
        except Exception as e:
            logger.exception(f"Error getting recommendations for resume {resume_id}: {e}")
            return []
        finally:
            if conn: conn.close()

