import psycopg2
from psycopg2.extras import RealDictCursor
from app.config.settings import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


def get_db_connection():
    """Create a connection to the PostgreSQL database"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {str(e)}")
        raise


def init_db():
    """Initialize database by creating necessary tables"""
    conn = None
    try:
        conn = get_db_connection()
        create_tables(conn)
        print("Database tables initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {str(e)}")
    finally:
        if conn:
            conn.close()


def create_tables(conn):
    """Create required tables if they don't exist"""
    with conn.cursor() as cur:
        # Create users table first
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create resumes table with foreign key to users
        cur.execute('''
            CREATE TABLE IF NOT EXISTS resumes (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                cv_url TEXT NOT NULL,
                skills TEXT[],
                experience TEXT[],
                education TEXT[],
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create job recommendations table
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