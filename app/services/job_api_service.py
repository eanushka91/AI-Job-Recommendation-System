import requests
from typing import List, Dict, Any, Optional

# JOOBLE_API_KEY is now imported dynamically and more safely inside fetch_jobs

class JobAPIService:
    """Service for fetching real-time job listings from Jooble API"""

    JOOBLE_API_URL = "https://jooble.org/api/"

    @staticmethod
    def fetch_jobs(
            keywords: Optional[List[str]] = None,
            location: Optional[str] = None,
            limit: int = 50,
            page: int = 1
    ) -> List[Dict[str, Any]]:
        api_key = None
        try:
            # Try to import at the point of use to ensure mocks are effective
            # and to handle potential circular dependencies or late configurations.
            from app.config import settings as app_settings # Import the module
            api_key = getattr(app_settings, 'JOOBLE_API_KEY', None) # Safely get the attribute
        except ImportError:
            print("Critical Error: app.config.settings module could not be imported in JobAPIService.")
        except AttributeError:
            print("Warning: JOOBLE_API_KEY not found as an attribute in app.config.settings.")


        if not api_key:
            print("Warning: Jooble API key is not configured or not found. Cannot fetch jobs.")
            return []

        try:
            search_query = {}
            if keywords and len(keywords) > 0:
                search_query["keywords"] = " ".join(keywords)
            if location:
                search_query["location"] = location

            search_query["pageSize"] = limit
            search_query["page"] = page

            api_key_display = f"...{api_key[-4:]}" if isinstance(api_key, str) and len(api_key) >= 4 else "INVALID_KEY"
            print(f"JobAPIService: Sending API request to Jooble. Params: {search_query}, Key ending: {api_key_display}")

            headers = {'Content-Type': 'application/json'}
            response = requests.post(
                f"{JobAPIService.JOOBLE_API_URL}{api_key}",
                json=search_query,
                headers=headers,
                timeout=15
            )

            if response.status_code == 200:
                print(f"JobAPIService: Successfully received Jooble API response for page {page}, status {response.status_code}")
                return JobAPIService._process_jooble_response(response.json())
            else:
                print(f"JobAPIService: Jooble API error. Status: {response.status_code}, Response: {response.text}")
                return []
        except requests.exceptions.Timeout:
            print("JobAPIService: Error fetching jobs from Jooble API - Request timed out.")
            return []
        except requests.exceptions.RequestException as e:
            print(f"JobAPIService: Error fetching jobs from Jooble API (RequestException) - {str(e)}")
            return []
        except Exception as e:
            print(f"JobAPIService: Unexpected error fetching jobs - {type(e).__name__}: {str(e)}")
            return []

    @staticmethod
    def _process_jooble_response(api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        processed_jobs = []
        if not isinstance(api_response, dict):
            print("JobAPIService Process Error: API response is not a dictionary.")
            return []

        jobs_list = api_response.get("jobs") # Use .get for safer access

        if not isinstance(jobs_list, list): # Check if 'jobs' is a list
            print(f"JobAPIService Process Error: 'jobs' key is missing or not a list in API response. Found: {type(jobs_list)}")
            return []

        for job_data in jobs_list:
            if not isinstance(job_data, dict): # Ensure each item in jobs_list is a dict
                print(f"JobAPIService Process Warning: Skipping non-dictionary job item: {job_data}")
                continue # Skip this item and proceed with the next

            # Safely get data using .get() with defaults
            job_id = job_data.get("id", "")
            title = job_data.get("title", "Unknown Position")
            company = job_data.get("company", "Unknown Company")
            location = job_data.get("location", "Unknown Location")
            description = job_data.get("snippet", "No description available")
            url = job_data.get("link", "")
            date_posted = job_data.get("updated", "")
            salary = job_data.get("salary", "")

            content = f"{title} {description} {company}".lower()
            processed_job = {
                "id": job_id, "title": title, "company": company,
                "location": location, "description": description, "url": url,
                "date_posted": date_posted, "content": content
            }
            if salary:
                processed_job["salary"] = salary
            processed_jobs.append(processed_job)

        print(f"JobAPIService: Processed {len(processed_jobs)} jobs from API response.")
        return processed_jobs