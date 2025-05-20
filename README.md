# 🧠 AI Job Recommendation System

This is an AI-powered job recommendation platform built with FastAPI (Python) that uses a Large Language Model (LLM) to generate personalized job suggestions. The system supports CV uploads to AWS S3, uses PostgreSQL for data storage, and offers paginated job listings. CI is managed through GitHub Actions, and the backend runs as a Docker container.

## 🚀 Features

- 🔍 AI-generated job recommendations using LLM
- 📄 CV upload and storage via AWS S3
- 🔁 Job list pagination (10 jobs per page)
- 📦 Backend API with FastAPI (Python)
- 🗃️ PostgreSQL for database management
- 🐳 Dockerized for easy deployment
- 🔄 CI pipeline via GitHub Actions

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI
- **Database**: PostgreSQL
- **CI/CD**: GitHub Actions
- **AI**: LLM (e.g., OpenAI, Hugging Face)
- **Storage**: AWS S3 (for CVs)
- **Containerization**: Docker

## 📁 Project Structure

ai-job-recommendation/
│
├── app/
│ ├── main.py # FastAPI app entry point
│ ├── models/ # Pydantic models and DB models
│ ├── routes/ # API routes
│ ├── services/ # LLM logic and S3 upload services
│ └── utils/ # Helper functions
│
├── tests/ # Unit and integration tests
├── Dockerfile # Docker image config
├── requirements.txt # Python dependencies
├── .github/workflows/ # GitHub Actions workflows
└── README.md # This file

## 📦 Getting Started

### Prerequisites

- Python 3.10+
- Docker
- AWS CLI (configured)
- PostgreSQL database

### Environment Variables

Create a `.env` file in the root:

DATABASE_URL=postgresql://user:password@localhost:5432/dbname
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
S3_BUCKET_NAME=your_bucket_name
OPENAI_API_KEY=your_openai_key # or relevant LLM API key



### Installation

```bash
git clone https://github.com/your-username/ai-job-recommendation.git
cd ai-job-recommendation
pip install -r requirements.txt
uvicorn app.main:app --reload

🐳 Docker
To build and run the Docker container:

bash
Copy
Edit
docker build -t ai-job-recommendation .
docker run -d -p 8000:8000 --env-file .env ai-job-recommendation

🧪 Running Tests
bash
Copy
Edit
pytest

🔄 CI/CD with GitHub Actions
CI is configured in .github/workflows/ci.yml to:

Lint code

Run tests

Build Docker image

📤 Uploading CVs
PDFs uploaded via the API are stored in AWS S3. Ensure correct permissions and bucket policies are in place.

📚 API Endpoints
POST /recommend - Get job recommendations from LLM

GET /jobs?page=1 - Paginated job list

POST /upload-cv - Upload CV to AWS S3

GET /profile/{user_id} - Retrieve user profile data

📬 Contact
For feedback or contributions, open an issue or create a pull request.

© 2025 Anushka Eshan | All rights reserved.