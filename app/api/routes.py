# app/api/routes.py

# Keep necessary FastAPI imports
from fastapi import APIRouter, File, UploadFile, Form, Query, HTTPException # Keep HTTPException if used
# Removed Depends as it wasn't used in the provided endpoint signatures
from fastapi.responses import JSONResponse
# Keep Optional if used, removed List as it wasn't used in provided signatures
from typing import Optional
# import json # Removed as unused
# import uuid # Removed as unused
import logging

# --- Application specific imports ---
from app.services.s3_service import S3Service
from app.services.ml.recommendation_engine import RecommendationEngine
# Assuming models are correctly defined in app.db.models
from app.db.models import ResumeModel, UserModel
# Assuming settings are correctly defined
from app.config.settings import DEFAULT_RECOMMENDATIONS_COUNT, DEFAULT_JOB_LOCATION
# Assuming pagination utilities are correct
from app.api.pagination import PageParams, paginate, PageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["CV Upload & Recommendations"])

# --- Endpoint Definitions ---

# Example: /upload-cv endpoint (Review and apply similar logic to others)
@router.post("/upload-cv", status_code=201)
async def upload_cv(
        file: UploadFile = File(..., description="CV file (PDF recommended)."),
        skills: str = Form(..., description="Comma-separated skills."),
        experience: str = Form(..., description="Comma-separated experience."),
        education: str = Form(..., description="Comma-separated education."),
        location: Optional[str] = Form(DEFAULT_JOB_LOCATION, description="Optional job location."),
        user_id: Optional[int] = Form(None, description="Optional existing user ID.")
):
    logger.info(f"CV upload request for filename: {file.filename}")
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        logger.warning(f"Invalid file type: {file.filename}")
        # Use HTTPException for standard errors
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
        # Or return JSONResponse if preferred:
        # return JSONResponse(status_code=400, content={"message": "Only PDF files are allowed"})

    try:
        s3_url = S3Service.upload_file(file, object_name=file.filename)
        logger.info(f"File uploaded to S3: {s3_url}")

        user_created = False
        db_user_id = user_id # Use a different variable name to avoid confusion
        if db_user_id is None:
            created_id = UserModel.create()
            if created_id is None: # Check if user creation failed
                 raise HTTPException(status_code=500, detail="Failed to create new user record.")
            db_user_id = created_id
            user_created = True
            logger.info(f"New user created: ID {db_user_id}")
        else:
            user = UserModel.get_by_id(db_user_id)
            if not user:
                logger.warning(f"User ID {db_user_id} not found.")
                raise HTTPException(status_code=404, detail=f"User with ID {db_user_id} not found")
            logger.debug(f"Found existing user: ID {db_user_id}")

        skills_list = [s.strip() for s in skills.split(",") if s.strip()]
        experience_list = [e.strip() for e in experience.split(",") if e.strip()]
        education_list = [e.strip() for e in education.split(",") if e.strip()]

        resume_id = ResumeModel.create(
            user_id=db_user_id, cv_url=s3_url, skills=skills_list,
            experience=experience_list, education=education_list
        )
        if resume_id is None: # Check if resume creation failed
             raise HTTPException(status_code=500, detail="Failed to create resume record.")
        logger.info(f"Resume record created: ID {resume_id}")

        rec_cache_key = f"resume_{resume_id}_{location or 'default'}"
        recommendations_list = RecommendationEngine.get_job_recommendations(
            skills=skills_list, experience=experience_list, education=education_list,
            location=location, num_recommendations=DEFAULT_RECOMMENDATIONS_COUNT * 2, # Fetch more for cache
            cache_key=rec_cache_key, force_refresh=True
        )
        logger.info(f"Fetched {len(recommendations_list)} potential recommendations.")

        page_params = PageParams(page=1, size=DEFAULT_RECOMMENDATIONS_COUNT)
        paginated_recommendations = paginate(recommendations_list, page_params)

        return {
            "message": "CV uploaded successfully!",
            "s3_url": s3_url,
            "user_id": db_user_id,
            "user_created": user_created,
            "resume_id": resume_id,
            "recommendations": paginated_recommendations
        }
    except HTTPException as http_exc:
         # Re-raise HTTPExceptions directly
         raise http_exc
    except Exception as e:
        logger.exception(f"Error during CV upload: {e}") # Log full traceback
        raise HTTPException(status_code=500, detail="An internal server error occurred during CV upload.")

# --- Review and apply similar fixes (unused imports, logging, HTTPException) to other endpoints ---

@router.get("/recommendations/{resume_id}", response_model=PageResponse) # Example using PageResponse model
async def get_recommendations(
        resume_id: int,
        # Use PageParams with Depends if you prefer FastAPI's dependency injection for pagination params
        # page_params: PageParams = Depends(),
        # Or define them directly with Query as before:
        location: Optional[str] = Query(None),
        refresh: bool = Query(False),
        page: int = Query(1, ge=1),
        size: int = Query(DEFAULT_RECOMMENDATIONS_COUNT, ge=1, le=50)
):
    logger.info(f"Get recommendations request for resume_id: {resume_id}, page: {page}, size: {size}")
    try:
        resume_data = ResumeModel.get_by_id(resume_id)
        if not resume_data:
            raise HTTPException(status_code=404, detail=f"Resume {resume_id} not found")

        job_location = location or resume_data.get("location") or DEFAULT_JOB_LOCATION
        rec_cache_key = f"resume_{resume_id}_{job_location or 'default'}"

        # Fetch a potentially larger batch for pagination/caching
        recommendations_list = RecommendationEngine.get_job_recommendations(
            skills=resume_data.get("skills", []),
            experience=resume_data.get("experience", []),
            education=resume_data.get("education", []),
            location=job_location,
            num_recommendations=size * page + size, # Fetch enough for current/next page?
            cache_key=rec_cache_key,
            force_refresh=refresh,
            page=page # Pass page if RE uses it
        )

        # Use the PageParams class for pagination logic input
        page_params_obj = PageParams(page=page, size=size)
        paginated_result = paginate(recommendations_list, page_params_obj)

        # Return the dictionary which matches PageResponse structure implicitly
        # Or explicitly create PageResponse(items=paginated_result['items'], ...)
        return paginated_result
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception(f"Error getting recommendations for resume {resume_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error getting recommendations.")


@router.get("/search-jobs", response_model=PageResponse) # Example using PageResponse
async def search_jobs(
        query: str = Query(..., min_length=1),
        location: Optional[str] = Query(None),
        page: int = Query(1, ge=1),
        size: int = Query(DEFAULT_RECOMMENDATIONS_COUNT, ge=1, le=50),
        load_more: bool = Query(False) # Flag for internal logic if needed
):
    logger.info(f"Search jobs request: query='{query}', page={page}, size={size}")
    try:
        search_cache_key = f"search_{query}_{location or 'default'}"
        all_matching_jobs = RecommendationEngine.search_jobs(
            query=query, location=location, cache_key=search_cache_key,
            page=page, size=size, fetch_more=load_more
        )
        page_params_obj = PageParams(page=page, size=size)
        paginated_jobs = paginate(all_matching_jobs, page_params_obj)
        # Add query/location info to response if needed, PageResponse model doesn't have them
        # return {"query": query, "location_used": location, "jobs": paginated_jobs}
        return paginated_jobs # Return structure matching PageResponse
    except Exception as e:
        logger.exception(f"Error during job search for query '{query}': {e}")
        raise HTTPException(status_code=500, detail="Internal server error during job search.")


@router.get("/job-stats/{resume_id}") # Define a response model for stats if desired
async def get_job_stats(resume_id: int):
    logger.info(f"Get job stats request for resume_id: {resume_id}")
    try:
        resume_data = ResumeModel.get_by_id(resume_id)
        if not resume_data:
            raise HTTPException(status_code=404, detail=f"Resume {resume_id} not found")

        stats = RecommendationEngine.get_job_stats(
            skills=resume_data.get("skills", []),
            experience=resume_data.get("experience", []),
            education=resume_data.get("education", [])
        )
        return {"resume_id": resume_id, "stats": stats}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception(f"Error generating job stats for resume {resume_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error generating job stats.")


@router.delete("/delete-cv/{resume_id}", status_code=200)
async def delete_cv(resume_id: int):
    logger.info(f"Delete request for resume_id: {resume_id}")
    try:
        resume_data = ResumeModel.get_by_id(resume_id)
        if not resume_data:
            raise HTTPException(status_code=404, detail=f"Resume {resume_id} not found")

        cv_url = resume_data.get("cv_url")
        if cv_url:
            logger.debug(f"Attempting S3 delete: {cv_url}")
            s3_deleted = S3Service.delete_file(cv_url)
            if not s3_deleted:
                # Log error but continue with DB deletion for now
                logger.error(f"Failed to delete S3 file {cv_url} for resume {resume_id}.")

        logger.debug(f"Attempting DB delete for resume_id: {resume_id}")
        # Ensure ResumeModel.delete method exists and handles errors/return values
        db_deleted = ResumeModel.delete(resume_id)
        if not db_deleted:
            # If DB delete fails, this is more critical
            logger.error(f"Failed to delete resume record {resume_id} from database.")
            raise HTTPException(status_code=500, detail="Failed to delete resume record from database.")

        logger.info(f"Successfully deleted resume {resume_id} (S3 delete status: {s3_deleted}, DB delete status: {db_deleted})")

        # Clear cache
        location = resume_data.get("location") or DEFAULT_JOB_LOCATION
        rec_cache_key = f"resume_{resume_id}_{location or 'default'}"
        RecommendationEngine.clear_cache(rec_cache_key)

        return {"message": f"Resume with ID {resume_id} deleted successfully."}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception(f"Error deleting resume {resume_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during resume deletion.")


# Consider if this endpoint is truly needed or if frontend can just call
# /recommendations or /search-jobs with the next page number.
@router.get("/load-more-jobs")
async def load_more_jobs(
        query: Optional[str] = Query(None),
        location: Optional[str] = Query(None),
        page: int = Query(1, ge=1),
        size: int = Query(DEFAULT_RECOMMENDATIONS_COUNT, ge=1, le=50),
        resume_id: Optional[int] = Query(None)
):
    logger.info(f"Load more request: page={page}, size={size}, query='{query}', resume_id={resume_id}")
    if resume_id:
        # Forward to get_recommendations logic
        # Avoid raising exceptions directly from other endpoints if possible
        try:
             # Note: awaiting another endpoint function directly might bypass middleware/dependencies
             # It might be better to refactor the core logic into a shared function.
             # For now, let's assume direct call is acceptable for this structure.
             return await get_recommendations(resume_id=resume_id, location=location, page=page, size=size, refresh=False)
        except HTTPException as http_exc:
             # If get_recommendations raises HTTPException, re-raise it
             raise http_exc
        except Exception as e:
             logger.exception(f"Error in load_more calling get_recommendations: {e}")
             raise HTTPException(status_code=500, detail="Internal server error.")
    elif query:
        # Forward to search_jobs logic
        try:
             return await search_jobs(query=query, location=location, page=page, size=size, load_more=True)
        except HTTPException as http_exc:
             raise http_exc
        except Exception as e:
             logger.exception(f"Error in load_more calling search_jobs: {e}")
             raise HTTPException(status_code=500, detail="Internal server error.")
    else:
        raise HTTPException(status_code=400, detail="Requires 'resume_id' or 'query'.")

