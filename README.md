# CV Upload & Job Recommendation System

A FastAPI-based application that allows users to upload their CV, extracts skills, education, and experience, and provides AI-powered job recommendations matching their profile.

## Features

- CV file upload to Amazon S3
- Storage of CV metadata in PostgreSQL database
- AI-powered job recommendation engine that matches user skills with job listings
- Integration with external job API for real-time job data
- REST API for CV management and job recommendations

## Project Structure

```
my-cv-upload-project/
│
├── .env                     # Environment variables
│
├── app/
│   ├── __init__.py          # Makes app directory a Python package
│   │
│   ├── main.py              # Main FastAPI application entry point
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py      # App configuration and environment settings
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py      # Database connection handling
│   │   └── models.py        # Database models/schema
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── s3_service.py    # S3 upload functionality
│   │   ├── job_api_service.py # Service for fetching job listings
│   │   └── recommendation_engine.py # AI recommendation engine
│   │
│   └── api/
│       ├── __init__.py
│       ├── routes.py        # API route definitions
│       └── schemas.py       # Pydantic models for request/response validation
│
├── requirements.txt         # Project dependencies
│
└── README.md                # Project documentation
```

## Setup Instructions

### Prerequisites

- Python 3.9+
- PostgreSQL database
- AWS account with S3 access
- API Ninjas API key (for job data)

### Installation

1. Clone the repository

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root with your configuration (see the sample .env file)

5. Create the PostgreSQL database:
   ```
   createdb cv_upload_db  # Or use your preferred method
   ```

6. Run the application:
   ```
   uvicorn app.main:app --reload
   ```

7. Access the API documentation at http://localhost:8000/docs

## API Endpoints

- `POST /api/upload-cv` - Upload CV and get job recommendations
- `GET /api/users/{user_id}` - Get user data
- `GET /api/resumes/user/{user_id}` - Get all resumes for a user
- `GET /api/resumes/{resume_id}` - Get a specific resume
- `GET /api/job-recommendations/{resume_id}` - Get job recommendations for an existing resume

## AI Recommendation Engine

The system uses a content-based recommendation approach:

1. User CV data (skills, experience, education) is processed and vectorized
2. Real-time job listings are fetched from an external API
3. TF-IDF and cosine similarity are used to match the user profile with job listings
4. Jobs are ranked by match score and returned to the user

## Development

To contribute to this project:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License.