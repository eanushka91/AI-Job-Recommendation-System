from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from typing import List, Optional
import json
import uuid
from app.services.s3_service import S3Service
from app.services.ml.recommendation_engine import RecommendationEngine
from app.db.models import ResumeModel, UserModel
from app.config.settings import DEFAULT_RECOMMENDATIONS_COUNT, DEFAULT_JOB_LOCATION
from app.api.pagination import PageParams, paginate

router = APIRouter(prefix="/api", tags=["CV Upload"])


@router.post("/upload-cv")
async def upload_cv(
        file: UploadFile = File(...),
        skills: str = Form(...),
        experience: str = Form(...),
        education: str = Form(...),
        location: Optional[str] = Form(DEFAULT_JOB_LOCATION),
        user_id: Optional[int] = Form(None)  # Optional, can be provided if you want to use existing user
):
    """
    Upload a CV file to S3, store user details in the database, and get job recommendations

    Args:
        file: CV file (PDF recommended)
        skills: Comma-separated list of skills
        experience: Comma-separated list of experience items
        education: Comma-separated list of education items
        location: Optional job location preference
        user_id: Optional user ID (if not provided, a new user will be created)

    Returns:
        URL of uploaded file, database entry IDs, and job recommendations (first page)
    """
    try:
        # Check if file is PDF
        if not file.filename.endswith('.pdf'):
            return JSONResponse(
                status_code=400,
                content={"message": "Only PDF files are allowed"}
            )

        # Upload file to S3
        s3_url = S3Service.upload_file(file)
        if not s3_url:
            return JSONResponse(
                status_code=500,
                content={"message": "Failed to upload file - S3 error"}
            )

        # Create a new user if user_id not provided
        if user_id is None:
            user_id = UserModel.create()
            user_created = True
        else:
            user_created = False

        # Verify the user exists
        if not UserModel.get_by_id(user_id):
            return JSONResponse(
                status_code=404,
                content={"message": f"User with ID {user_id} not found"}
            )

        # Process the comma-separated values into lists
        skills_list = [skill.strip() for skill in skills.split(",") if skill.strip()]
        experience_list = [exp.strip() for exp in experience.split(",") if exp.strip()]
        education_list = [edu.strip() for edu in education.split(",") if edu.strip()]

        # Log the processed data for debugging
        print(f"Processing CV upload with skills: {skills_list}")
        print(f"Experience: {experience_list}")
        print(f"Education: {education_list}")
        print(f"Location: {location}")

        # Store information in database
        resume_id = ResumeModel.create(
            user_id=user_id,
            cv_url=s3_url,
            skills=skills_list,
            experience=experience_list,
            education=education_list
        )
        print(f"Created resume with ID: {resume_id}")

        # Generate a cache key for this resume
        cache_key = f"resume_{resume_id}_{location}"

        # Get job recommendations based on CV data (get enough for multiple pages)
        try:
            print("Fetching job recommendations...")
            all_recommendations = RecommendationEngine.get_job_recommendations(
                skills=skills_list,
                experience=experience_list,
                education=education_list,
                location=location,
                num_recommendations=50,  # Get more to support pagination
                cache_key=cache_key
            )
            print(f"Fetched {len(all_recommendations)} recommendations")
        except Exception as rec_error:
            print(f"Error fetching recommendations: {str(rec_error)}")
            # If recommendation engine fails, use empty list
            all_recommendations = []

        # Paginate the results - first page
        page_params = PageParams(page=1, size=DEFAULT_RECOMMENDATIONS_COUNT)
        paginated_recommendations = paginate(all_recommendations, page_params)

        return {
            "message": "CV uploaded and data stored successfully!",
            "url": s3_url,
            "user_id": user_id,
            "user_created": user_created,
            "resume_id": resume_id,
            "recommendations": paginated_recommendations
        }

    except Exception as e:
        print(f"Error in upload-cv endpoint: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"message": f"An error occurred: {str(e)}"}
        )


@router.get("/recommendations/{resume_id}")
async def get_recommendations(
        resume_id: int,
        location: Optional[str] = Query(None),
        refresh: bool = Query(False),
        page: int = Query(1, ge=1),
        size: int = Query(DEFAULT_RECOMMENDATIONS_COUNT, ge=1, le=50)
):
    """
    Get job recommendations for a previously uploaded CV

    Args:
        resume_id: ID of the resume
        location: Optional job location to filter by (if None, uses default)
        refresh: If True, force refresh cache
        page: Page number
        size: Page size

    Returns:
        Page of job recommendations
    """
    try:
        # Get resume from database
        resume_data = ResumeModel.get_by_id(resume_id)
        if not resume_data:
            return JSONResponse(
                status_code=404,
                content={"message": f"Resume with ID {resume_id} not found"}
            )

        # Use provided location or default from resume
        job_location = location or resume_data.get("location", DEFAULT_JOB_LOCATION)

        # Generate cache key
        cache_key = f"resume_{resume_id}_{job_location}"

        # Get recommendations
        all_recommendations = RecommendationEngine.get_job_recommendations(
            skills=resume_data.get("skills", []),
            experience=resume_data.get("experience", []),
            education=resume_data.get("education", []),
            location=job_location,
            num_recommendations=50,  # Get more to support pagination
            cache_key=cache_key,
            force_refresh=refresh
        )

        # Paginate the results
        page_params = PageParams(page=page, size=size)
        paginated_recommendations = paginate(all_recommendations, page_params)

        return {
            "resume_id": resume_id,
            "location": job_location,
            "recommendations": paginated_recommendations
        }

    except Exception as e:
        print(f"Error in get-recommendations endpoint: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"message": f"An error occurred: {str(e)}"}
        )


@router.get("/search-jobs")
async def search_jobs(
        query: str = Query(..., min_length=1),
        location: Optional[str] = Query(None),
        page: int = Query(1, ge=1),
        size: int = Query(DEFAULT_RECOMMENDATIONS_COUNT, ge=1, le=50),
        load_more: bool = Query(False)
):
    """
    Search for jobs by keyword and location

    Args:
        query: Search term
        location: Optional job location
        page: Page number
        size: Page size
        load_more: If True, will fetch more jobs if needed

    Returns:
        Matching jobs
    """
    try:
        # Generate cache key for search
        cache_key = f"search_{query}_{location}"

        # Check if we need to fetch more jobs if load_more is True and we're beyond page 1
        fetch_new = load_more and page > 1

        # Search for jobs with pagination awareness
        all_jobs = RecommendationEngine.search_jobs(
            query=query,
            location=location,
            cache_key=cache_key,
            page=page,
            size=size,
            fetch_more=fetch_new
        )

        # Paginate the results
        page_params = PageParams(page=page, size=size)
        paginated_jobs = paginate(all_jobs, page_params)

        return {
            "query": query,
            "location": location,
            "jobs": paginated_jobs
        }

    except Exception as e:
        print(f"Error in search-jobs endpoint: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"message": f"An error occurred: {str(e)}"}
        )


@router.get("/job-stats/{resume_id}")
async def get_job_stats(resume_id: int):
    """
    Get statistics about job availability based on a resume

    Args:
        resume_id: ID of the resume

    Returns:
        Job market statistics
    """
    try:
        # Get resume from database
        resume_data = ResumeModel.get_by_id(resume_id)
        if not resume_data:
            return JSONResponse(
                status_code=404,
                content={"message": f"Resume with ID {resume_id} not found"}
            )

        # Get job stats
        stats = RecommendationEngine.get_job_stats(
            skills=resume_data.get("skills", []),
            experience=resume_data.get("experience", []),
            education=resume_data.get("education", [])
        )

        return {
            "resume_id": resume_id,
            "stats": stats
        }

    except Exception as e:
        print(f"Error in job-stats endpoint: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"message": f"An error occurred: {str(e)}"}
        )


@router.delete("/delete-cv/{resume_id}")
async def delete_cv(resume_id: int):
    """
    Delete a CV file and its data

    Args:
        resume_id: ID of the resume to delete

    Returns:
        Success message
    """
    try:
        # Get resume from database
        resume_data = ResumeModel.get_by_id(resume_id)
        if not resume_data:
            return JSONResponse(
                status_code=404,
                content={"message": f"Resume with ID {resume_id} not found"}
            )

        # Delete file from S3
        cv_url = resume_data.get("cv_url")
        if cv_url:
            S3Service.delete_file(cv_url)

        # Delete from database
        ResumeModel.delete(resume_id)

        # Clear cache for this resume
        cache_key = f"resume_{resume_id}_"
        RecommendationEngine.clear_cache(cache_key)

        return {
            "message": f"CV with ID {resume_id} deleted successfully"
        }

    except Exception as e:
        print(f"Error in delete-cv endpoint: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"message": f"An error occurred: {str(e)}"}
        )


@router.get("/load-more-jobs")
async def load_more_jobs(
        query: str = Query(..., min_length=1),
        location: Optional[str] = Query(None),
        page: int = Query(1, ge=1),
        size: int = Query(DEFAULT_RECOMMENDATIONS_COUNT, ge=1, le=50),
        resume_id: Optional[int] = Query(None)
):
    """
    Explicit endpoint for loading more jobs (useful for frontend "Load More" button)

    Args:
        query: Search term
        location: Optional job location
        page: Page number to load
        size: Page size
        resume_id: Optional resume ID if loading based on resume

    Returns:
        Next batch of jobs
    """
    try:
        if resume_id:
            # Get resume-based recommendations
            return await get_recommendations(
                resume_id=resume_id,
                location=location,
                page=page,
                size=size
            )
        else:
            # Get search-based results with load_more flag
            return await search_jobs(
                query=query,
                location=location,
                page=page,
                size=size,
                load_more=True
            )

    except Exception as e:
        print(f"Error in load-more-jobs endpoint: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"message": f"An error occurred: {str(e)}"}
        )