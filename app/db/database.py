# app/db/database.py

import psycopg2

# from psycopg2.extras import RealDictCursor # Removed as unused in this file
# Import settings safely
try:
    from app.config.settings import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
except ImportError:
    # Provide fallbacks or raise a configuration error if settings are crucial
    print("CRITICAL: Failed to import database settings from app.config.settings!")
    # Define fallbacks if needed for the code to run, though connection will likely fail
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD = None, None, None, None, None

import logging

logger = logging.getLogger(__name__)


def get_db_connection():
    """Create and return a new connection to the PostgreSQL database."""
    connection = None
    # Check if settings were loaded
    if not all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD]):
        logger.error(
            "Database connection cannot be established: Configuration is missing."
        )
        raise ConnectionError("Database configuration is incomplete.")
    try:
        logger.debug(
            f"Connecting to database: dbname='{DB_NAME}' user='{DB_USER}' host='{DB_HOST}' port='{DB_PORT}'"
        )
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        logger.info("Database connection established successfully.")
        return connection
    except psycopg2.OperationalError as e:
        logger.error(f"Database connection failed: {e}", exc_info=True)
        raise  # Re-raise to signal connection failure clearly
    except Exception as e:
        logger.error(f"Unexpected error during database connection: {e}", exc_info=True)
        raise


def init_db():
    """Initialize database by creating necessary tables if they don't exist."""
    conn = None
    try:
        conn = get_db_connection()  # Attempt to connect
        if conn:
            create_tables(conn)  # Pass the connection to create_tables
            logger.info("Database tables structure verified/initialized.")
        # else case handled by get_db_connection raising an error
    except Exception as e:
        # Catch errors from get_db_connection or create_tables
        logger.error(f"Database initialization failed: {e}", exc_info=True)
    finally:
        if (
            conn and not conn.closed
        ):  # Check if connection exists and is not already closed
            conn.close()
            logger.debug("Database connection closed after init_db.")


def create_tables(conn):
    """Create required tables if they don't exist using the provided connection."""
    if not conn or conn.closed:
        logger.error("create_tables error: Invalid or closed database connection.")
        raise ValueError("Invalid database connection provided to create_tables.")

    try:
        with conn.cursor() as cur:
            logger.info("Ensuring 'users' table exists...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            logger.info("Ensuring 'resumes' table exists...")
            cur.execute("""
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
            """)

            logger.info("Ensuring 'job_recommendations' table exists...")
            cur.execute("""
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
            """)

            logger.info("Ensuring indexes exist...")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_resumes_user_id ON resumes(user_id);"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_job_recommendations_resume_id ON job_recommendations(resume_id);"
            )

        conn.commit()
        logger.info("Database tables and indexes are ready.")
    except Exception as e:
        logger.error(f"Error during table/index creation: {e}", exc_info=True)
        if conn and not conn.closed:  # Check before rollback
            try:
                conn.rollback()
                logger.info("Rolled back transaction due to table creation error.")
            except Exception as rb_e:
                logger.error(f"Error during rollback: {rb_e}")
        raise  # Re-raise error after attempting rollback
