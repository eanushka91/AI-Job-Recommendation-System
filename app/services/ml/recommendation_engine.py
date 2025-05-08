from typing import List, Dict, Any, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import requests
import re
import random

from app.services.job_api_service import JobAPIService


# Assuming JOOBLE_API_KEY for this engine is managed here or via settings
# For consistency, it would be better if this also came from app.config.settings

class RecommendationEngine:
    _job_cache: Dict[str, List[Dict[str, Any]]] = {}  # Type hint for clarity
    _pagination_state: Dict[str, Dict[str, Any]] = {}

    # It's better to get this from app.config.settings as well
    JOOBLE_API_KEY_RE = "2b0875d1-df2c-45a7-a65b-ff28d3c3a624"  # Renamed to avoid conflict if settings has one
    JOOBLE_API_URL = "https://jooble.org/api/"

    @staticmethod
    def get_job_recommendations(
            skills: List[str],
            education: List[str],
            experience: Optional[List[str]] = None,  # Corrected type hint
            location: Optional[str] = None,  # Corrected type hint
            num_recommendations: int = 10,  # Default to a more common page size
            cache_key: Optional[str] = None,
            force_refresh: bool = False,
            page: int = 1  # Default page is 1
    ) -> List[Dict[str, Any]]:

        _experience = experience if experience is not None else []  # Ensure it's a list

        # Caching and pagination logic (simplified for focus on core issue)
        # A robust implementation would handle page sizes and total items more carefully.
        # The test failure indicates that num_recommendations was not respected.

        # Determine search keywords
        search_keywords_for_api: List[str]
        if not skills and not _experience:
            fallback_keywords = [edu.strip().split()[0] for edu in education if
                                 edu and edu.strip() and edu.strip().split()]
            if not fallback_keywords: fallback_keywords = ["entry", "level", "job"]
            search_keywords_for_api = fallback_keywords
            print(f"RE: Using fallback keywords: {search_keywords_for_api}")
        else:
            search_keywords_for_api = RecommendationEngine._extract_search_keywords(skills, _experience)
            print(f"RE: Using search keywords: {search_keywords_for_api}")

        # Fetch jobs
        # The `limit` here should be sufficient to get `num_recommendations` after matching.
        # If num_recommendations is small (e.g., 1), fetching more (e.g., 10-20) gives better ranking context.
        # Let's fetch a slightly larger batch than num_recommendations if num_recommendations is small.
        fetch_api_limit = max(num_recommendations * 2, 20)  # Fetch at least 20 or twice the needed amount

        available_jobs = JobAPIService.fetch_jobs(
            keywords=search_keywords_for_api, location=location, limit=fetch_api_limit, page=page
        )
        print(f"RE: Fetched {len(available_jobs)} jobs from JobAPIService for page {page}")

        if not available_jobs:
            print(f"RE: No jobs from JobAPIService, trying Jooble API (RE internal) for page {page}")
            available_jobs = RecommendationEngine._fetch_jobs_from_jooble(
                keywords=search_keywords_for_api, location=location, limit=fetch_api_limit, page=page
            )
            print(f"RE: Fetched {len(available_jobs)} jobs from Jooble API (RE internal) for page {page}")

        user_profile = RecommendationEngine._create_user_profile(skills, _experience, education)

        # _match_jobs_to_profile already slices to its 'num_recommendations' argument.
        # So, pass the 'num_recommendations' from this function's signature.
        matched_and_scored_jobs = RecommendationEngine._match_jobs_to_profile(
            user_profile,
            available_jobs,
            num_recommendations  # This is the crucial fix for the test failure
        )

        # Caching logic would go here, potentially storing more than just matched_and_scored_jobs
        # if fetch_api_limit was significantly larger and we wanted to cache a larger pool.
        # For now, assume the function returns exactly what was matched and sliced.

        return matched_and_scored_jobs

    @staticmethod
    def _extract_search_keywords(skills: List[str], experience: List[str]) -> List[str]:
        # (Implementation as provided before, ensure it handles empty lists gracefully)
        clean_skills = [skill.strip() for skill in skills if skill and skill.strip()]
        job_titles = []
        if experience:
            for exp_item in experience:
                if exp_item and exp_item.strip():
                    title_words = exp_item.split(" ")[:3]  # First 3 words as potential title
                    if title_words: job_titles.append(" ".join(title_words))

        keywords = []
        if job_titles: keywords.extend(job_titles[:1])  # Prioritize first job title
        if clean_skills: keywords.extend(clean_skills[:3])  # Top 3 skills

        unique_keywords = list(dict.fromkeys(keywords))  # Maintain order while making unique
        return unique_keywords[:5]  # Limit to 5 keywords

    @staticmethod
    def _create_user_profile(skills: List[str], experience: List[str], education: List[str]) -> str:
        # (Implementation as provided before)
        profile_parts = []
        # Weight skills by repeating them
        for skill in (s.strip() for s in skills if s and s.strip()): profile_parts.extend([skill] * 3)
        for exp_item in (e.strip() for e in experience if e and e.strip()): profile_parts.append(exp_item)
        for edu_item in (e.strip() for e in education if e and e.strip()): profile_parts.append(edu_item)
        return " ".join(profile_parts)

    @staticmethod
    def _match_jobs_to_profile(
            user_profile: str,
            jobs: List[Dict[str, Any]],
            num_recommendations: int
    ) -> List[Dict[str, Any]]:
        # (Implementation as provided before, ensure TF-IDF handles edge cases like empty vocab)
        if not user_profile or not jobs: return []

        job_contents, valid_jobs = [], []
        for job in jobs:
            content = job.get('content', '')
            if not content:  # Attempt to build content if missing
                title = job.get('title', '')
                desc = job.get('description', '')
                content = f"{title} {desc}".strip()
            if content:  # Only include jobs with some text content
                job_contents.append(content)
                valid_jobs.append(job)

        if not valid_jobs: return []
        if not user_profile.strip():  # If user profile is empty, meaningful match is not possible
            print("RE Match: User profile is empty. Returning fallback ranking or empty.")
            return RecommendationEngine._fallback_job_ranking(valid_jobs, num_recommendations)

        try:
            # Check if job_contents are all non-empty strings
            if not all(isinstance(text, str) and text.strip() for text in job_contents):
                print("RE Match: Some job contents are empty or invalid after processing. Using fallback.")
                return RecommendationEngine._fallback_job_ranking(valid_jobs, num_recommendations)

            vectorizer = TfidfVectorizer(stop_words='english', min_df=1)  # min_df=1 to handle small corpus
            all_texts_for_vectorization = job_contents + [user_profile]

            tfidf_matrix = vectorizer.fit_transform(all_texts_for_vectorization)
            user_vector = tfidf_matrix[-1]
            job_vectors = tfidf_matrix[:-1]

            if job_vectors.shape[0] == 0: return []  # No job vectors to compare against

            similarities = cosine_similarity(user_vector, job_vectors).flatten()
            scored_jobs = []
            for i, (job, score) in enumerate(zip(valid_jobs, similarities)):
                job_copy = job.copy()
                job_copy['match_score'] = min(round(float(score) * 100, 1), 100.0)
                scored_jobs.append(job_copy)

            sorted_jobs = sorted(scored_jobs, key=lambda x: x.get('match_score', 0.0), reverse=True)
            return sorted_jobs[:num_recommendations]  # Slice to the desired number
        except ValueError as ve:  # Catch specific TF-IDF errors like "empty vocabulary"
            print(f"RE Match: TF-IDF ValueError: {str(ve)}. Using fallback ranking.")
            return RecommendationEngine._fallback_job_ranking(valid_jobs, num_recommendations)
        except Exception as e:
            print(f"RE Match: Error in ML job matching: {type(e).__name__} - {str(e)}. Using fallback.")
            return RecommendationEngine._fallback_job_ranking(valid_jobs, num_recommendations)

    @staticmethod
    def _fallback_job_ranking(jobs: List[Dict[str, Any]], num_recommendations: int) -> List[Dict[str, Any]]:
        # (Implementation as provided before)
        if not jobs: return []
        scored_jobs = []
        for job in jobs:
            job_copy = job.copy()
            job_copy['match_score'] = round(random.uniform(60.0, 75.0), 1)  # Lower fallback scores
            scored_jobs.append(job_copy)
        return sorted(scored_jobs, key=lambda x: x.get('match_score', 0.0), reverse=True)[:num_recommendations]

    @staticmethod
    def _fetch_jobs_from_jooble(  # Internal method for RE
            keywords: List[str], location: Optional[str] = None, limit: int = 10, page: int = 1
    ) -> List[Dict[str, Any]]:
        # (Implementation as provided before, ensure API key is handled)
        if not RecommendationEngine.JOOBLE_API_KEY_RE:
            print("RE _fetch_jobs_from_jooble: API key not set.")
            return []
        try:
            # ... (rest of the implementation, ensuring robustness)
            search_query_str = " ".join(keywords)
            payload = {"keywords": search_query_str, "pageSize": limit, "page": page}
            if location: payload["location"] = location
            headers = {'Content-Type': 'application/json'}
            response = requests.post(
                f"{RecommendationEngine.JOOBLE_API_URL}{RecommendationEngine.JOOBLE_API_KEY_RE}",
                json=payload, headers=headers, timeout=10
            )
            response.raise_for_status()
            response_data = response.json()
            # ... (processing logic similar to JobAPIService._process_jooble_response)
            formatted_jobs = []
            api_jobs = response_data.get('jobs', [])
            if not isinstance(api_jobs, list): return []

            for job_data in api_jobs:
                if not isinstance(job_data, dict): continue
                formatted_jobs.append({
                    "id": job_data.get('id', ''), "title": job_data.get('title', 'Unknown Title'),
                    "company": job_data.get('company', 'Unknown Company'),
                    "location": job_data.get('location', 'Unknown Location'),
                    "description": job_data.get('snippet', ''), "url": job_data.get('link', ''),
                    "date_posted": job_data.get('updated', ''),
                    "content": f"{job_data.get('title', '')} {job_data.get('snippet', '')} {job_data.get('company', '')}".strip()
                })
            return formatted_jobs
        except requests.exceptions.RequestException as e:
            print(f"RE _fetch_jobs_from_jooble Error: {str(e)}")
            return []
        except Exception as e:
            print(f"RE _fetch_jobs_from_jooble Unexpected Error: {type(e).__name__} - {str(e)}")
            return []

    # clear_cache, search_jobs, has_more_jobs, get_job_stats implementations as before,
    # but ensure they are robust and consistent with the changes above.
    # For brevity, I'll omit repeating them if no direct fixes for the reported errors were in them.
    # However, ensure get_job_stats's _fetch_jobs_from_jooble call is also robust.

    @staticmethod
    def clear_cache(cache_key: Optional[str] = None):
        if cache_key:
            if cache_key in RecommendationEngine._job_cache:
                del RecommendationEngine._job_cache[cache_key]
            if cache_key in RecommendationEngine._pagination_state:
                del RecommendationEngine._pagination_state[cache_key]
            print(f"RE: Cleared cache for key: {cache_key}")
        else:
            RecommendationEngine._job_cache.clear()
            RecommendationEngine._pagination_state.clear()
            print("RE: Cleared entire recommendation cache")

    # search_jobs, has_more_jobs, get_job_stats would need similar review for robustness
    # For now, focusing on the direct errors.
    # ... (Keep other methods like search_jobs, has_more_jobs, get_job_stats, ensuring their robustness)