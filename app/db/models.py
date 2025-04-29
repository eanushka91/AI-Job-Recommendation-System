from app.db.database import get_db_connection
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional


class UserModel:
    """Model to handle database operations for users"""

    @staticmethod
    def create():
        """Create a new user and return the ID"""
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users DEFAULT VALUES
                    RETURNING id
                    """
                )
                user_id = cur.fetchone()[0]
                conn.commit()
                return user_id
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()

    @staticmethod
    def get_by_id(user_id):
        """Get a user by ID"""
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT * FROM users WHERE id = %s
                    """,
                    (user_id,)
                )
                return cur.fetchone()
        finally:
            if conn:
                conn.close()


class ResumeModel:
    """Model to handle database operations for resumes"""

    @staticmethod
    def create(user_id, cv_url, skills, experience, education):
        """Create a new resume entry in the database"""
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO resumes (user_id, cv_url, skills, experience, education)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        user_id,
                        cv_url,
                        skills,
                        experience,
                        education
                    )
                )
                resume_id = cur.fetchone()[0]
                conn.commit()
                return resume_id
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()

    @staticmethod
    def get_by_id(resume_id):
        """Get a resume by its ID"""
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT * FROM resumes WHERE id = %s
                    """,
                    (resume_id,)
                )
                return cur.fetchone()
        finally:
            if conn:
                conn.close()

    @staticmethod
    def get_by_user_id(user_id):
        """Get all resumes for a specific user"""
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT * FROM resumes WHERE user_id = %s ORDER BY created_at DESC
                    """,
                    (user_id,)
                )
                return cur.fetchall()
        finally:
            if conn:
                conn.close()

    @staticmethod
    def save_recommendations(resume_id: int, recommendations: List[Dict[str, Any]]) -> bool:
        """
        Save job recommendations for a resume

        This is optional - you could store recommendations to avoid re-calculating
        them every time, or to track user interactions with recommendations
        """
        conn = None
        try:
            conn = get_db_connection()

            # First, check if we need to create the recommendations table
            with conn.cursor() as cur:
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS job_recommendations (
                        id SERIAL PRIMARY KEY,
                        resume_id INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
                        job_id TEXT NOT NULL,
                        job_title TEXT NOT NULL,
                        company TEXT NOT NULL,
                        location TEXT,
                        description TEXT,
                        url TEXT,
                        match_score FLOAT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()

            # Delete any existing recommendations for this resume
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM job_recommendations WHERE resume_id = %s",
                    (resume_id,)
                )

            # Insert new recommendations
            for job in recommendations:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO job_recommendations 
                        (resume_id, job_id, job_title, company, location, description, url, match_score)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            resume_id,
                            job.get('id', ''),
                            job.get('title', ''),
                            job.get('company', ''),
                            job.get('location', ''),
                            job.get('description', ''),
                            job.get('url', ''),
                            job.get('match_score', 0.0)
                        )
                    )

            conn.commit()
            return True

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error saving recommendations: {str(e)}")
            return False
        finally:
            if conn:
                conn.close()

    @staticmethod
    def get_recommendations(resume_id: int) -> List[Dict[str, Any]]:
        """Get stored job recommendations for a resume"""
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT * FROM job_recommendations 
                    WHERE resume_id = %s 
                    ORDER BY match_score DESC
                    """,
                    (resume_id,)
                )
                return cur.fetchall()
        except Exception as e:
            print(f"Error getting recommendations: {str(e)}")
            return []
        finally:
            if conn:
                conn.close()