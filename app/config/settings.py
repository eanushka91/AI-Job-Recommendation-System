import os
from dotenv import load_dotenv

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "CV Upload System")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "mycvstore")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "resumes")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

JOOBLE_API_KEY = os.getenv("JOOBLE_API_KEY")

DEFAULT_RECOMMENDATIONS_COUNT = int(os.getenv("DEFAULT_RECOMMENDATIONS_COUNT", "10"))
DEFAULT_JOB_LOCATION = os.getenv("DEFAULT_JOB_LOCATION", "Remote")

PAGE_SIZE = 10
MAX_PAGE_SIZE = 50
