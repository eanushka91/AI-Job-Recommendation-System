import pytest
from app.services.ml.recommendation_engine import RecommendationEngine
from app.services.job_api_service import JobAPIService

sample_skills = ["Python", "API"]
sample_experience = ["API Developer"]
sample_education = ["BSc CS"]

# sample_jobs_from_api should have enough items for tests that might request more.
# For num_recommendations=1, 3 items are plenty.
sample_jobs_from_api_for_re = [
    {"id": "re_j1", "title": "Python API Dev", "content": "Python API Dev content A"},
    {"id": "re_j2", "title": "Senior Python Eng", "content": "Senior Python Eng content B"},
    {"id": "re_j3", "title": "Backend Python Coder", "content": "Backend Python Coder content C"}
]

class TestRecommendationEngine:
    def setup_method(self):
        RecommendationEngine.clear_cache()
    def teardown_method(self):
        RecommendationEngine.clear_cache()

    def test_get_job_recommendations_success(self, mocker):
        # Application code fix: RecommendationEngine.get_job_recommendations now passes
        # its own 'num_recommendations' param to _match_jobs_to_profile,
        # and _match_jobs_to_profile slices its result to that number.
        mocker.patch.object(JobAPIService, 'fetch_jobs', return_value=sample_jobs_from_api_for_re)
        mocker.patch.object(RecommendationEngine, '_fetch_jobs_from_jooble', return_value=[])

        # Request exactly 1 recommendation
        recommendations = RecommendationEngine.get_job_recommendations(
            skills=sample_skills, education=sample_education, experience=sample_experience,
            num_recommendations=1
        )
        assert len(recommendations) == 1, \
            f"Expected 1 recommendation, but got {len(recommendations)}. This indicates an issue with slicing in RecommendationEngine."
        if recommendations:
            assert "match_score" in recommendations[0]

    def test_get_job_recommendations_fallback_to_jooble(self, mocker):
        mocker.patch.object(JobAPIService, 'fetch_jobs', return_value=[]) # JobAPIService returns no jobs
        # _fetch_jobs_from_jooble (internal RE method) returns 3 sample jobs
        mocker.patch.object(RecommendationEngine, '_fetch_jobs_from_jooble', return_value=sample_jobs_from_api_for_re)

        # Request exactly 1 recommendation
        recommendations = RecommendationEngine.get_job_recommendations(
            skills=sample_skills, education=sample_education, experience=sample_experience,
            num_recommendations=1
        )
        assert len(recommendations) == 1, \
            f"Expected 1 recommendation after fallback, but got {len(recommendations)}. Issue with slicing in RecommendationEngine."
        if recommendations:
            assert "match_score" in recommendations[0]

    # Other tests for RecommendationEngine (extract_keywords, create_profile, match_jobs, etc.)
    # should be reviewed to ensure their assertions are still valid with any app code changes.
    # For example, if _match_jobs_to_profile's internal logic changed significantly.