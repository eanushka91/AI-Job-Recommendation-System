from fastapi import APIRouter, File, UploadFile, Form, Query, HTTPException
from typing import Optional, TypeVar
import logging

from app.services.s3_service import S3Service
from app.services.ml.recommendation_engine import RecommendationEngine
from app.db.models import ResumeModel, UserModel
from app.config.settings import (
    DEFAULT_RECOMMENDATIONS_COUNT,
    DEFAULT_JOB_LOCATION,
    S3_BUCKET_NAME,
)
from app.api.pagination import (
    PageParams,
    paginate,
    PageResponse,
    RecommendationsWrappedResponse,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["CV Upload & Recommendations"])

JobItemType = TypeVar("JobItemType")


@router.post("/upload-cv", status_code=201)
async def upload_cv(
    file: UploadFile = File(..., description="CV file (PDF, DOC, DOCX)."),
    skills: str = Form(""),
    experience: str = Form(""),
    education: str = Form(""),
    location: Optional[str] = Form(DEFAULT_JOB_LOCATION),
    user_id: Optional[int] = Form(None),
):
    logger.info(f"CV upload request for filename: {file.filename}")
    allowed_extensions = {".pdf", ".doc", ".docx"}

    file_ext = ""
    if "." in file.filename:
        file_ext = "." + file.filename.rsplit(".", 1)[1].lower()

    if file_ext not in allowed_extensions:
        logger.warning(f"Invalid file type: {file.filename} (ext: {file_ext})")
        raise HTTPException(
            status_code=400,
            detail=f"Only PDF, DOC, DOCX files are allowed. Got: {file_ext}",
        )

    try:
        s3_url = S3Service.upload_file(file, object_name=file.filename)
        logger.info(f"File uploaded to S3: {s3_url}")

        user_created = False
        db_user_id = user_id
        if db_user_id is None:
            created_id = UserModel.create()
            if created_id is None:
                raise HTTPException(
                    status_code=500, detail="Failed to create new user record."
                )
            db_user_id = created_id
            user_created = True
            logger.info(f"New user created: ID {db_user_id}")
        else:
            user = UserModel.get_by_id(db_user_id)
            if not user:
                logger.warning(f"User ID {db_user_id} not found.")
                raise HTTPException(
                    status_code=404, detail=f"User with ID {db_user_id} not found"
                )
            logger.debug(f"Found existing user: ID {db_user_id}")

        skills_list = (
            [s.strip() for s in skills.split(",") if s.strip()] if skills else []
        )
        experience_list = (
            [e.strip() for e in experience.split(";") if e.strip()]
            if experience
            else []
        )
        education_list = (
            [e.strip() for e in education.split(";") if e.strip()] if education else []
        )

        logger.debug(f"Processed Skills: {skills_list}")
        logger.debug(f"Processed Experience: {experience_list}")
        logger.debug(f"Processed Education: {education_list}")
        logger.debug(f"Processed Location: {location}")

        resume_id = ResumeModel.create(
            user_id=db_user_id,
            cv_url=s3_url,
            skills=skills_list,
            experience=experience_list,
            education=education_list,
            location=location,
        )
        if resume_id is None:
            raise HTTPException(
                status_code=500, detail="Failed to create resume record."
            )
        logger.info(f"Resume record created: ID {resume_id} with location: {location}")

        effective_location = location or DEFAULT_JOB_LOCATION
        rec_cache_key = f"resume_{resume_id}_{effective_location}"

        recommendations_data_list = RecommendationEngine.get_job_recommendations(
            skills=skills_list,
            experience=experience_list,
            education=education_list,
            location=effective_location,
            num_recommendations=DEFAULT_RECOMMENDATIONS_COUNT * 2,
            cache_key=rec_cache_key,
            force_refresh=True,
            page=1,
        )
        logger.info(
            f"Fetched {len(recommendations_data_list)} potential recommendations for initial display."
        )

        page_params = PageParams(page=1, size=DEFAULT_RECOMMENDATIONS_COUNT)
        paginated_recommendations_dict = paginate(
            recommendations_data_list, page_params
        )

        return {
            "message": "CV uploaded successfully!",
            "s3_url": s3_url,
            "user_id": db_user_id,
            "user_created": user_created,
            "resume_id": resume_id,
            "recommendations": paginated_recommendations_dict,
        }
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception(f"Error during CV upload: {e}")
        raise HTTPException(
            status_code=500,
            detail="An internal server error occurred during CV upload.",
        )


@router.get(
    "/recommendations/{resume_id}",
    response_model=RecommendationsWrappedResponse[JobItemType],
)
async def get_recommendations(
    resume_id: int,
    location: Optional[str] = Query(None),
    refresh: bool = Query(False),
    page: int = Query(1, ge=1),
    size: int = Query(DEFAULT_RECOMMENDATIONS_COUNT, ge=1, le=50),
):
    logger.info(
        f"Get recommendations request for resume_id: {resume_id}, page: {page}, size: {size}, location: {location}, refresh: {refresh}"
    )
    try:
        resume_data = ResumeModel.get_by_id(resume_id)
        if not resume_data:
            logger.warning(f"Resume ID {resume_id} not found in DB.")
            raise HTTPException(status_code=404, detail=f"Resume {resume_id} not found")

        job_location_to_use = (
            location or resume_data.get("location") or DEFAULT_JOB_LOCATION
        )
        logger.info(
            f"Using job location: {job_location_to_use} for recommendations (resume_id: {resume_id})."
        )

        rec_cache_key = f"resume_{resume_id}_{job_location_to_use}"

        all_recommendations_for_criteria = RecommendationEngine.get_job_recommendations(
            skills=resume_data.get("skills", []),
            experience=resume_data.get("experience", []),
            education=resume_data.get("education", []),
            location=job_location_to_use,
            cache_key=rec_cache_key,
            force_refresh=refresh,
            page=page,
        )
        logger.info(
            f"RecommendationEngine returned {len(all_recommendations_for_criteria)} items for resume_id {resume_id}, page {page} request."
        )

        page_params_obj = PageParams(page=page, size=size)
        paginated_result_dict = paginate(
            all_recommendations_for_criteria, page_params_obj
        )

        final_response_content = {"recommendations": paginated_result_dict}

        logger.debug(
            f"Returning paginated recommendations for resume_id {resume_id}, page {page}: {str(final_response_content)[:200]}..."
        )
        return final_response_content

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception(
            f"Unexpected error getting recommendations for resume {resume_id}, page {page}: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error getting recommendations for resume {resume_id}.",
        )


@router.get("/search-jobs", response_model=PageResponse[JobItemType])
async def search_jobs(
    query: str = Query(..., min_length=1),
    location: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(DEFAULT_RECOMMENDATIONS_COUNT, ge=1, le=50),
    load_more: bool = Query(False),
):
    logger.info(
        f"Search jobs request: query='{query}', location='{location}', page={page}, size={size}, load_more={load_more}"
    )
    try:
        search_base_cache_key = f"search_{query}_{location or 'default'}"

        all_matching_jobs = RecommendationEngine.search_jobs(
            query=query,
            location=location,
            cache_key=search_base_cache_key,
            page=page,
            size=size,
            fetch_more=load_more,
        )
        logger.info(
            f"RecommendationEngine returned {len(all_matching_jobs)} items for search query '{query}'."
        )

        page_params_obj = PageParams(page=page, size=size)
        paginated_jobs_dict = paginate(all_matching_jobs, page_params_obj)

        return paginated_jobs_dict
    except Exception as e:
        logger.exception(f"Error during job search for query '{query}': {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error during job search."
        )


@router.get("/job-stats/{resume_id}")
async def get_job_stats(resume_id: int):
    logger.info(f"Get job stats request for resume_id: {resume_id}")
    try:
        resume_data = ResumeModel.get_by_id(resume_id)
        if not resume_data:
            raise HTTPException(status_code=404, detail=f"Resume {resume_id} not found")

        stats = RecommendationEngine.get_job_stats(
            skills=resume_data.get("skills", []),
            experience=resume_data.get("experience", []),
            education=resume_data.get("education", []),
        )
        return {"resume_id": resume_id, "stats": stats}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception(f"Error generating job stats for resume {resume_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error generating job stats."
        )


@router.delete("/delete-cv/{resume_id}", status_code=200)
async def delete_cv(resume_id: int):
    logger.info(f"Delete request for resume_id: {resume_id}")
    try:
        resume_data = ResumeModel.get_by_id(resume_id)
        if not resume_data:
            raise HTTPException(status_code=404, detail=f"Resume {resume_id} not found")

        cv_url = resume_data.get("cv_url")
        s3_deleted = False
        if cv_url:
            s3_object_name = cv_url.split(S3_BUCKET_NAME + ".s3.amazonaws.com/")[-1]
            logger.debug(f"Attempting S3 delete for object: {s3_object_name}")
            s3_deleted = S3Service.delete_file(s3_object_name)
            if not s3_deleted:
                logger.error(
                    f"Failed to delete S3 file {s3_object_name} for resume {resume_id}."
                )

        logger.debug(f"Attempting DB delete for resume_id: {resume_id}")
        db_deleted = ResumeModel.delete(resume_id)
        if not db_deleted:
            logger.error(f"Failed to delete resume record {resume_id} from database.")
            raise HTTPException(
                status_code=500, detail="Failed to delete resume record from database."
            )

        logger.info(
            f"Successfully processed delete for resume {resume_id} (S3 delete status: {s3_deleted}, DB delete status: {db_deleted})"
        )

        loc_for_cache = resume_data.get("location") or DEFAULT_JOB_LOCATION
        rec_cache_key = f"resume_{resume_id}_{loc_for_cache}"
        RecommendationEngine.clear_cache(rec_cache_key)

        return {
            "message": f"Resume with ID {resume_id} processed for deletion. S3 status: {s3_deleted}"
        }
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception(f"Error deleting resume {resume_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error during resume deletion."
        )


@router.get("/load-more-jobs")
async def load_more_jobs(
    query: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(DEFAULT_RECOMMENDATIONS_COUNT, ge=1, le=50),
    resume_id: Optional[int] = Query(None),
):
    logger.info(
        f"Load more jobs request: page={page}, size={size}, query='{query}', resume_id={resume_id}, location='{location}'"
    )
    if resume_id:
        try:
            return await get_recommendations(
                resume_id=resume_id,
                location=location,
                page=page,
                size=size,
                refresh=False,
            )
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            logger.exception(
                f"Error in load_more forwarding to get_recommendations for resume_id {resume_id}: {e}"
            )
            raise HTTPException(
                status_code=500,
                detail="Internal server error during load more (recommendations).",
            )
    elif query:
        try:
            return await search_jobs(
                query=query, location=location, page=page, size=size, load_more=True
            )
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            logger.exception(
                f"Error in load_more forwarding to search_jobs for query '{query}': {e}"
            )
            raise HTTPException(
                status_code=500,
                detail="Internal server error during load more (search).",
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="Requires 'resume_id' or 'query' for loading more jobs.",
        )
