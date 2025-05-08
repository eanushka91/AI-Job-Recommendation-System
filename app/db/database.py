# app/db/database.py

import psycopg2
# from psycopg2.extras import RealDictCursor # Removed as it's used in models.py, not here
from app.config.settings import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
import logging

logger = logging.getLogger(__name__)

def get_db_connection():
    """Create and return a new connection to the PostgreSQL database."""
    connection = None
    try:
        logger.debug(f"Connecting to database: dbname='{DB_NAME}' user='{DB_USER}' host='{DB_HOST}' port='{DB_PORT}'")
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        logger.info("Database connection established successfully.")
        return connection
    except psycopg2.OperationalError as e:
        logger.error(f"Database connection failed: {e}", exc_info=True)
        # Depending on use case, might return None or raise
        raise # Re-raise to signal connection failure clearly
    except Exception as e:
        logger.error(f"Unexpected error during database connection: {e}", exc_info=True)
        raise

def init_db():
    """Initialize database by creating necessary tables if they don't exist."""
    conn = None
    try:
        conn = get_db_connection() # Attempt to connect
        if conn:
            create_tables(conn) # Pass the connection to create_tables
            logger.info("Database tables structure verified/initialized.")
        else:
            # This case should ideally not be reached if get_db_connection raises on failure
            logger.error("Database initialization skipped: Failed to establish connection.")
    except Exception as e:
        # Catch errors from get_db_connection or create_tables
        logger.error(f"Database initialization failed: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()
            logger.debug("Database connection closed after init_db.")

def create_tables(conn):
    """Create required tables if they don't exist using the provided connection."""
    if not conn or conn.closed:
         logger.error("create_tables error: Invalid or closed database connection.")
         raise ValueError("Invalid database connection provided to create_tables.")

    try:
        # Use a single transaction for all table creations
        with conn.cursor() as cur:
            logger.info("Ensuring 'users' table exists...")
            cur.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            ''')

            logger.info("Ensuring 'resumes' table exists...")
            cur.execute('''
                CREATE TABLE IF NOT EXISTS resumes (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    cv_url TEXT NOT NULL,
                    skills TEXT[],
                    experience TEXT[],
                    education TEXT[],
                    location TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            ''')

            logger.info("Ensuring 'job_recommendations' table exists...")
            cur.execute('''
                CREATE TABLE IF NOT EXISTS job_recommendations (
                    id SERIAL PRIMARY KEY,
                    resume_id INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
                    job_id TEXT,
                    job_title TEXT,
                    company TEXT,
                    location TEXT,
                    description TEXT,
                    url TEXT,
                    match_score FLOAT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            ''')

            # Add indexes
            logger.info("Ensuring indexes exist...")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_resumes_user_id ON resumes(user_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_job_recommendations_resume_id ON job_recommendations(resume_id);")

        conn.commit() # Commit transaction
        logger.info("Database tables and indexes are ready.")
    except Exception as e:
        logger.error(f"Error during table/index creation: {e}", exc_info=True)
        if conn:
             conn.rollback() # Rollback on error
        raise # Re-raise error

