from typing import List, Dict, Any, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import requests
import re
import random
import logging

from app.services.job_api_service import JobAPIService

logger = logging.getLogger(__name__)


class RecommendationEngine:
    _job_cache: Dict[str, List[Dict[str, Any]]] = {}
    _pagination_state: Dict[str, Dict[str, Any]] = {}

    JOOBLE_API_KEY_RE = (
        "70587e41-5ac1-49f7-a9e8-a388a12308dc"
    )
    JOOBLE_API_URL = "https://jooble.org/api/"

    @staticmethod
    def get_job_recommendations(
        skills: List[str],
        education: List[str],
        experience: Optional[List[str]] = None,
        location: Optional[str] = None,
        num_recommendations: int = 10,
        cache_key: Optional[str] = None,
        force_refresh: bool = False,
        page: int = 1,
    ) -> List[Dict[str, Any]]:
        _experience = experience if experience is not None else []
        logger.info("RE: Getting recommendations...")

        logger.info(
            f"RE Details: num={num_recommendations}, page={page}, refresh={force_refresh}, key={cache_key}"
        )

        if cache_key and not force_refresh:
            cached_data = RecommendationEngine._job_cache.get(cache_key)
            if cached_data:
                logger.info(f"RE: Returning cached data for key: {cache_key}")
                return cached_data[:num_recommendations]

        search_keywords_for_api: List[str]
        if not skills and not _experience:
            fallback_keywords = [
                edu.strip().split()[0]
                for edu in education
                if edu and edu.strip() and edu.strip().split()
            ]
            if not fallback_keywords:
                fallback_keywords = ["entry", "level", "job"]
            search_keywords_for_api = fallback_keywords
            logger.info(f"RE: Using fallback keywords: {search_keywords_for_api}")
        else:
            search_keywords_for_api = RecommendationEngine._extract_search_keywords(
                skills, _experience
            )
            logger.info(f"RE: Using search keywords: {search_keywords_for_api}")

        fetch_api_limit = max(num_recommendations + 10, 30)
        logger.info(f"RE: Fetching up to {fetch_api_limit} jobs for page {page}.")

        available_jobs = JobAPIService.fetch_jobs(
            keywords=search_keywords_for_api,
            location=location,
            limit=fetch_api_limit,
            page=page,
        )
        logger.info(f"RE: Fetched {len(available_jobs)} jobs from JobAPIService.")

        if not available_jobs:
            logger.info(
                "RE: No jobs from JobAPIService, trying Jooble API (RE internal)."
            )  # Fixed E701
            available_jobs = RecommendationEngine._fetch_jobs_from_jooble(
                keywords=search_keywords_for_api,
                location=location,
                limit=fetch_api_limit,
                page=page,
            )
            logger.info(
                f"RE: Fetched {len(available_jobs)} jobs from Jooble API (RE internal)."
            )

        if not available_jobs:
            logger.warning("RE: No available jobs found from any source.")
            return []

        user_profile = RecommendationEngine._create_user_profile(
            skills, _experience, education
        )
        logger.info(f"RE: Created user profile (length: {len(user_profile)}).")

        matched_and_scored_jobs = RecommendationEngine._match_jobs_to_profile(
            user_profile, available_jobs, num_recommendations
        )
        logger.info(f"RE: Matched and scored {len(matched_and_scored_jobs)} jobs.")

        if cache_key:
            RecommendationEngine._job_cache[cache_key] = matched_and_scored_jobs
            RecommendationEngine._pagination_state[cache_key] = {
                "current_page_served": page,
                "has_more": len(available_jobs) >= fetch_api_limit,
            }
            logger.info(f"RE: Updated cache for key: {cache_key}")

        return matched_and_scored_jobs

    @staticmethod
    def _extract_search_keywords(skills: List[str], experience: List[str]) -> List[str]:
        clean_skills = [
            str(skill).strip() for skill in skills if skill and str(skill).strip()
        ]
        job_titles = []
        if experience:
            for exp_item in experience:
                exp_str = str(exp_item).strip()
                if exp_str:
                    title_words = exp_str.split(" ")[:3]
                    if title_words:
                        job_titles.append(" ".join(title_words))
        keywords = []
        if job_titles:
            keywords.extend(job_titles[:1])
        if clean_skills:
            keywords.extend(clean_skills[:3])
        unique_keywords = list(dict.fromkeys(keywords))
        logger.debug(f"RE Extracted Keywords: {unique_keywords[:5]}")
        return unique_keywords[:5]

    @staticmethod
    def _create_user_profile(
        skills: List[str], experience: List[str], education: List[str]
    ) -> str:
        profile_parts = []
        for skill in (str(s).strip() for s in skills if s and str(s).strip()):
            profile_parts.extend([skill] * 3)
        for exp_item in (str(e).strip() for e in experience if e and str(e).strip()):
            profile_parts.append(exp_item)
        for edu_item in (str(e).strip() for e in education if e and str(e).strip()):
            profile_parts.append(edu_item)
        profile = " ".join(profile_parts)
        logger.debug(f"RE Created Profile Length: {len(profile)}")
        return profile

    @staticmethod
    def _match_jobs_to_profile(
        user_profile: str, jobs: List[Dict[str, Any]], num_recommendations: int
    ) -> List[Dict[str, Any]]:
        logger.info(
            f"RE Match: Starting profile matching for {len(jobs)} jobs, requesting top {num_recommendations}."
        )
        if not user_profile or not jobs:
            logger.warning(
                "RE Match: User profile or jobs list is empty."
            )  # Fixed E701
            return []
        job_contents, valid_jobs = [], []
        for job in jobs:
            content = (
                job.get("content", "")
                or f"{job.get('title', '')} {job.get('description', '')}".strip()
            )
            if content and isinstance(content, str):
                job_contents.append(content)
                valid_jobs.append(job)
            else:
                logger.warning(
                    f"RE Match: Skipping job with invalid content: {job.get('id', 'N/A')}"
                )

        if not valid_jobs:
            logger.warning("RE Match: No valid jobs with content.")  # Fixed E701
            return []
        if not user_profile.strip():
            logger.warning(
                "RE Match: User profile empty. Using fallback."
            )  # Fixed E701
            return RecommendationEngine._fallback_job_ranking(
                valid_jobs, num_recommendations
            )
        try:
            vectorizer = TfidfVectorizer(stop_words="english", min_df=1)
            valid_job_contents = [
                jc for jc in job_contents if jc and isinstance(jc, str)
            ]
            if len(valid_job_contents) != len(valid_jobs):
                logger.error(
                    "RE Match: Mismatch between valid jobs and contents. Refiltering."
                )  # Fixed E701
                valid_jobs = [
                    job
                    for job, content in zip(valid_jobs, job_contents)
                    if content and isinstance(content, str)
                ]
                job_contents = valid_job_contents
            if not valid_job_contents:
                logger.warning(
                    "RE Match: No valid job contents after filtering. Using fallback."
                )  # Fixed E701
                return RecommendationEngine._fallback_job_ranking(
                    valid_jobs, num_recommendations
                )

            all_texts_for_vectorization = valid_job_contents + [user_profile]
            tfidf_matrix = vectorizer.fit_transform(all_texts_for_vectorization)
            user_vector = tfidf_matrix[-1]
            job_vectors = tfidf_matrix[:-1]
            if job_vectors.shape[0] == 0:
                logger.warning("RE Match: No job vectors generated.")  # Fixed E701
                return []
            similarities = cosine_similarity(user_vector, job_vectors).flatten()
            scored_jobs = []
            for job, score in zip(valid_jobs, similarities):
                job_copy = job.copy()
                match_score = float(score) if not (score != score) else 0.0
                job_copy["match_score"] = min(round(match_score * 100, 1), 100.0)
                scored_jobs.append(job_copy)
            sorted_jobs = sorted(
                scored_jobs, key=lambda x: x.get("match_score", 0.0), reverse=True
            )
            return sorted_jobs[:num_recommendations]
        except ValueError as ve:
            logger.error(f"RE Match: TF-IDF ValueError: {str(ve)}. Using fallback.")
            return RecommendationEngine._fallback_job_ranking(
                valid_jobs, num_recommendations
            )
        except Exception as e:
            logger.exception(
                f"RE Match: Unexpected error: {type(e).__name__}. Using fallback."
            )
            return RecommendationEngine._fallback_job_ranking(
                valid_jobs, num_recommendations
            )

    @staticmethod
    def _fallback_job_ranking(
        jobs: List[Dict[str, Any]], num_recommendations: int
    ) -> List[Dict[str, Any]]:
        logger.warning(f"RE Fallback: Using random ranking for {len(jobs)} jobs.")
        if not jobs:
            return []  # Fixed E701
        scored_jobs = []
        for job in jobs:
            job_copy = job.copy()
            job_copy["match_score"] = round(random.uniform(50.0, 70.0), 1)
            scored_jobs.append(job_copy)
        return sorted(
            scored_jobs, key=lambda x: x.get("match_score", 0.0), reverse=True
        )[:num_recommendations]

    @staticmethod
    def _fetch_jobs_from_jooble(
        keywords: List[str],
        location: Optional[str] = None,
        limit: int = 10,
        page: int = 1,
    ) -> List[Dict[str, Any]]:
        if not RecommendationEngine.JOOBLE_API_KEY_RE:
            logger.error("RE Jooble Fetch: API key not set.")
            return []
        try:
            search_query_str = " ".join(filter(None, keywords))
            payload = {
                "keywords": search_query_str,
                "pageSize": max(1, limit),
                "page": max(1, page),
            }
            if location:
                payload["location"] = location
            headers = {"Content-Type": "application/json"}
            response = requests.post(
                f"{RecommendationEngine.JOOBLE_API_URL}{RecommendationEngine.JOOBLE_API_KEY_RE}",
                json=payload,
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            response_data = response.json()
            formatted_jobs = []
            api_jobs = response_data.get("jobs", [])
            if not isinstance(api_jobs, list):
                logger.warning("RE Jooble Fetch: 'jobs' key not list.")  # Fixed E701
                return []
            for job_data in api_jobs:
                if not isinstance(job_data, dict):
                    logger.warning(
                        f"RE Jooble Fetch: Skipping non-dict: {job_data}"
                    )  # Fixed E701
                    continue
                title = job_data.get("title", "")
                snippet = job_data.get("snippet", "")
                company = job_data.get("company", "")
                formatted_jobs.append(
                    {
                        "id": job_data.get("id", ""),
                        "title": title,
                        "company": company,
                        "location": job_data.get("location", ""),
                        "description": snippet,
                        "url": job_data.get("link", ""),
                        "date_posted": job_data.get("updated", ""),
                        "content": f"{title} {snippet} {company}".strip(),
                    }
                )
            return formatted_jobs
        except requests.exceptions.RequestException as e:
            logger.error(f"RE Jooble Fetch Error: {str(e)}")
            return []
        except Exception as e:
            logger.exception(f"RE Jooble Fetch Unexpected Error: {type(e).__name__}")
            return []

    @staticmethod
    def clear_cache(cache_key: Optional[str] = None):
        if cache_key:
            popped_jobs = RecommendationEngine._job_cache.pop(cache_key, None)
            popped_state = RecommendationEngine._pagination_state.pop(cache_key, None)
            if popped_jobs or popped_state:
                logger.info(f"RE Cache: Cleared cache for key: {cache_key}")
            else:
                logger.info(f"RE Cache: No cache found for key to clear: {cache_key}")
        else:
            RecommendationEngine._job_cache.clear()
            RecommendationEngine._pagination_state.clear()
            logger.info("RE Cache: Cleared entire recommendation cache")

    @staticmethod
    def get_job_stats(
        skills: List[str], experience: Optional[List[str]], education: List[str]
    ) -> Dict[str, Any]:
        search_keywords = RecommendationEngine._extract_search_keywords(
            skills, experience or []
        )
        jobs = RecommendationEngine._fetch_jobs_from_jooble(
            keywords=search_keywords, limit=100
        )
        stats = {
            "total_matching_jobs": len(jobs),
            "top_skills": [],
            "locations": {},
            "salary_range": {"min": 0, "max": 0, "avg": 0},
            "job_types": {},
        }
        if not jobs:
            return stats

        loc_counts = {}
        for job in jobs:
            loc = job.get("location", "Unknown")
            if loc:
                loc_counts[loc] = loc_counts.get(loc, 0) + 1
        stats["locations"] = loc_counts

        salaries = []
        for job in jobs:
            salary_str = str(job.get("salary", ""))
            if salary_str:
                salary_match = re.search(r"(\d[\d,.]*)", salary_str)
                if salary_match:
                    try:
                        salary_value = float(salary_match.group(1).replace(",", ""))
                        salaries.append(salary_value)
                    except ValueError:
                        pass  # Ignore conversion errors silently
        if salaries:
            stats["salary_range"]["min"] = min(salaries)
            stats["salary_range"]["max"] = max(salaries)
            stats["salary_range"]["avg"] = int(sum(salaries) / len(salaries))

        common_tech_skills = [
            "python",
            "java",
            "javascript",
            "react",
            "angular",
            "vue",
            "node",
            "sql",
            "nosql",
            "aws",
            "azure",
            "gcp",
            "docker",
            "kubernetes",
            "ci/cd",
            "devops",
            "agile",
            "scrum",
        ]
        skill_counts = {skill: 0 for skill in common_tech_skills}
        for job in jobs:
            content = (job.get("title", "") + " " + job.get("description", "")).lower()
            for skill in common_tech_skills:
                if skill.lower() in content:
                    skill_counts[skill] += 1
        sorted_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)
        stats["top_skills"] = [skill for skill, count in sorted_skills[:5] if count > 0]

        job_type_keywords = {
            "Full-time": ["full time", "full-time"],
            "Contract": ["contract"],
        }
        type_counts = {}
        for job in jobs:
            content = (job.get("title", "") + " " + job.get("description", "")).lower()
            for job_type, keywords in job_type_keywords.items():
                if any(keyword in content for keyword in keywords):
                    type_counts[job_type] = type_counts.get(job_type, 0) + 1
                    break
        stats["job_types"] = type_counts

        return stats

    @staticmethod
    def search_jobs(*args, **kwargs) -> List[Dict[str, Any]]:
        logger.warning("RE: search_jobs placeholder called")
        return []

    @staticmethod
    def has_more_jobs(cache_key: str) -> bool:
        logger.warning("RE: has_more_jobs placeholder called")
        return RecommendationEngine._pagination_state.get(cache_key, {}).get(
            "has_more", False
        )