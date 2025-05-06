import requests
from typing import List, Dict, Any, Optional
from app.config.settings import JOOBLE_API_KEY


class JobAPIService:
    """Service for fetching real-time job listings from Jooble API"""

    # Jooble API configuration
    JOOBLE_API_URL = "https://jooble.org/api/"

    @staticmethod
    def fetch_jobs(
            keywords: Optional[List[str]] = None,
            location: Optional[str] = None,
            limit: int = 50,
            page: int = 1  # Added page parameter
    ) -> List[Dict[str, Any]]:
        """
        Fetch jobs from Jooble API

        Args:
            keywords: List of job keywords (e.g., skills)
            location: Job location
            limit: Maximum number of jobs to return
            page: Page number for pagination

        Returns:
            List of job listings
        """
        # Get API key from settings
        api_key = JOOBLE_API_KEY

        if not api_key:
            print("Warning: Jooble API key not provided in environment variables")
            return []

        try:
            # Prepare search query
            search_query = {}

            if keywords and len(keywords) > 0:
                # Join keywords for the API query
                search_query["keywords"] = " ".join(keywords)

            if location:
                search_query["location"] = location

            # Add page size to query
            search_query["pageSize"] = limit

            # Add page number for pagination
            search_query["page"] = page

            print(f"Sending API request to Jooble with params: {search_query}")

            # Jooble uses POST requests with a JSON body
            headers = {
                'Content-Type': 'application/json'
            }

            # Send the request with API key in the URL and search parameters in body
            response = requests.post(
                f"{JobAPIService.JOOBLE_API_URL}{api_key}",
                json=search_query,
                headers=headers
            )

            if response.status_code == 200:
                print(f"Successfully received Jooble API response for page {page}")
                return JobAPIService._process_jooble_response(response.json())
            else:
                print(f"Jooble API error: {response.status_code} - {response.text}")
                return []

        except Exception as e:
            print(f"Error fetching jobs from Jooble API: {str(e)}")
            return []

    @staticmethod
    def _process_jooble_response(api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process and standardize Jooble API response

        Args:
            api_response: Raw JSON response from Jooble API

        Returns:
            List of standardized job listings
        """
        processed_jobs = []

        # Check if jobs exist in the response
        if "jobs" in api_response and api_response["jobs"]:
            jobs_list = api_response["jobs"]
        else:
            print("No job results found in API response")
            return []

        # Process each job in the response
        for job in jobs_list:
            # Extract job data
            job_id = job.get("id", "")
            title = job.get("title", "Unknown Position")
            company = job.get("company", "Unknown Company")
            location = job.get("location", "Unknown Location")
            description = job.get("snippet", "No description available")
            url = job.get("link", "")
            date_posted = job.get("updated", "")
            salary = job.get("salary", "")

            # Create content field for search/matching
            content = f"{title} {description} {company}".lower()

            # Create standardized job object
            processed_job = {
                "id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "description": description,
                "url": url,
                "date_posted": date_posted,
                "content": content
            }

            # Add salary if available
            if salary:
                processed_job["salary"] = salary

            processed_jobs.append(processed_job)

        print(f"Processed {len(processed_jobs)} jobs from API response")
        return processed_jobs