from app.services.ml.recommendation_engine import RecommendationEngine
from app.services.job_api_service import JobAPIService

sample_skills_re = ["Python", "Testing"]
sample_experience_re = ["Test Automation"]
sample_education_re = ["CS Degree"]
sample_jobs_for_re_tests = [
    {
        "id": "re_tst_1",
        "title": "Python Test Engineer",
        "content": "Python Test Engineer using pytest",
    },
    {
        "id": "re_tst_2",
        "title": "QA Automation (Python)",
        "content": "QA Automation (Python) role",
    },
]


class TestRecommendationEngine:
    def setup_method(self):
        RecommendationEngine.clear_cache()

    def teardown_method(self):
        RecommendationEngine.clear_cache()

    def test_get_job_recommendations_success_respects_num_recommendations(self, mocker):
        mocker.patch.object(
            JobAPIService, "fetch_jobs", return_value=sample_jobs_for_re_tests
        )
        mocker.patch.object(
            RecommendationEngine, "_fetch_jobs_from_jooble", return_value=[]
        )
        num_req = 1
        recommendations = RecommendationEngine.get_job_recommendations(
            skills=sample_skills_re,
            education=sample_education_re,
            experience=sample_experience_re,
            num_recommendations=num_req,
        )
        assert len(recommendations) == num_req

    def test_get_job_recommendations_fallback_respects_num_recommendations(
        self, mocker
    ):
        mocker.patch.object(JobAPIService, "fetch_jobs", return_value=[])
        mocker.patch.object(
            RecommendationEngine,
            "_fetch_jobs_from_jooble",
            return_value=sample_jobs_for_re_tests,
        )
        num_req = 1
        recommendations = RecommendationEngine.get_job_recommendations(
            skills=sample_skills_re,
            education=sample_education_re,
            experience=sample_experience_re,
            num_recommendations=num_req,
        )
        assert len(recommendations) == num_req