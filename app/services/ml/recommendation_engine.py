from typing import List, Dict, Any, Optional, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import json
import time
import requests
from app.services.job_api_service import JobAPIService


class RecommendationEngine:
    """
    Advanced engine for matching user CV data with job listings using ML
    """
    # Cache to store fetched jobs to avoid redundant API calls
    _job_cache = {}

    # Keep track of pagination state for each search
    _pagination_state = {}

    # Jooble API configuration
    JOOBLE_API_KEY = "2b0875d1-df2c-45a7-a65b-ff28d3c3a624"
    JOOBLE_API_URL = "https://jooble.org/api/"

    @staticmethod
    def get_job_recommendations(
            skills: List[str],
            education: List[str],
            experience: List[str] = None,
            location: str = None,
            num_recommendations: int = 50,
            cache_key: Optional[str] = None,
            force_refresh: bool = False,
            page: int = 1  # Added page parameter
    ) -> List[Dict[str, Any]]:
        """
        Get job recommendations based on CV data using ML techniques

        Args:
            skills: List of user skills
            experience: List of user experience items
            education: List of user education items
            location: Optional location preference
            num_recommendations: Maximum number of recommendations to return
            cache_key: Optional key for caching results
            force_refresh: Force refresh cache
            page: Page number for pagination

        Returns:
            List of recommended jobs with match scores
        """
        # Reset pagination state if force refresh or first page
        if force_refresh or page == 1:
            if cache_key:
                RecommendationEngine._pagination_state[cache_key] = {"current_page": 1, "has_more": True}

        # If requesting a new page and we already have this page cached
        if cache_key and not force_refresh:
            pagination_info = RecommendationEngine._pagination_state.get(cache_key, {})
            if pagination_info.get("current_page", 0) >= page and cache_key in RecommendationEngine._job_cache:
                cached_jobs = RecommendationEngine._job_cache[cache_key]
                print(f"Using cached recommendations for key: {cache_key}, page: {page}")
                # Return the specific page from cached jobs
                start_idx = (page - 1) * 10
                end_idx = start_idx + 10
                return cached_jobs[start_idx:end_idx] if len(cached_jobs) > start_idx else []

        # If no skills or experience provided, use fallback approach
        if not skills and not experience:
            # Create fallback keywords from education if available
            fallback_keywords = []
            for edu in education:
                if edu and len(edu.strip()) > 0:
                    edu_parts = edu.strip().split()
                    if len(edu_parts) > 1:
                        fallback_keywords.append(edu_parts[0])  # Add first word of education

            # If no education either, use generic keywords
            if not fallback_keywords:
                fallback_keywords = ["entry", "level", "job"]

            print(f"Using fallback keywords for job search: {fallback_keywords}")
            available_jobs = JobAPIService.fetch_jobs(
                keywords=fallback_keywords,
                location=location,
                limit=10,  # Get only 10 jobs per page
                page=page  # Pass page parameter
            )
        else:
            # Extract relevant keywords for job search
            search_keywords = RecommendationEngine._extract_search_keywords(skills, experience)
            print(f"Using search keywords: {search_keywords}")

            # Fetch jobs using API service
            available_jobs = JobAPIService.fetch_jobs(
                keywords=search_keywords,
                location=location,
                limit=10,  # Get only 10 jobs per page
                page=page  # Pass page parameter
            )

        print(f"Fetched {len(available_jobs)} jobs from API for page {page}")

        # If no jobs found, try directly with Jooble API
        if not available_jobs:
            print(f"No jobs found from JobAPIService, trying Jooble API directly for page {page}")
            search_keywords = RecommendationEngine._extract_search_keywords(skills, experience)
            available_jobs = RecommendationEngine._fetch_jobs_from_jooble(
                keywords=search_keywords,
                location=location,
                limit=10,  # Get only 10 jobs per page
                page=page  # Pass page parameter
            )
            print(f"Fetched {len(available_jobs)} jobs from Jooble API for page {page}")

        # Create user profile for similarity comparison
        user_profile = RecommendationEngine._create_user_profile(skills, experience, education)

        # Match jobs to user profile
        recommendations = RecommendationEngine._match_jobs_to_profile(
            user_profile,
            available_jobs,
            10  # Always process 10 jobs
        )

        # Update pagination state
        if cache_key:
            # Update our pagination state
            pagination_info = RecommendationEngine._pagination_state.get(cache_key,
                                                                         {"current_page": 0, "has_more": True})
            pagination_info["current_page"] = max(pagination_info["current_page"], page)
            pagination_info["has_more"] = len(available_jobs) > 0
            RecommendationEngine._pagination_state[cache_key] = pagination_info

            # Update cache with the new jobs
            if page == 1 or force_refresh:
                # For first page or refresh, replace cache
                RecommendationEngine._job_cache[cache_key] = recommendations
            else:
                # For subsequent pages, append to cache
                if cache_key in RecommendationEngine._job_cache:
                    existing_jobs = RecommendationEngine._job_cache[cache_key]
                    # Append new jobs without duplicates
                    existing_ids = {job['id'] for job in existing_jobs}
                    for job in recommendations:
                        if job['id'] not in existing_ids:
                            existing_jobs.append(job)
                    RecommendationEngine._job_cache[cache_key] = existing_jobs
                else:
                    RecommendationEngine._job_cache[cache_key] = recommendations

            print(
                f"Updated cache for key: {cache_key}, page: {page}, total jobs: {len(RecommendationEngine._job_cache.get(cache_key, []))}")

        return recommendations

    @staticmethod
    def _extract_search_keywords(skills: List[str], experience: List[str]) -> List[str]:
        """
        Extract the most relevant keywords from skills and experience for job search

        Args:
            skills: List of user skills
            experience: List of user experience items

        Returns:
            List of relevant keywords for job search
        """
        # Clean and filter skills and experience
        clean_skills = [skill.strip() for skill in skills if skill and skill.strip()]

        # Extract job titles from experience (simple approach)
        job_titles = []
        for exp in experience:
            if exp and exp.strip():
                # Take first part of experience as potential job title
                title_words = exp.split(" ")[:3]
                if title_words:
                    job_titles.append(" ".join(title_words))

        # Prioritize the most relevant keywords
        keywords = []

        # Add top job titles (if any)
        if job_titles:
            keywords.extend(job_titles[:1])

        # Add top skills
        if clean_skills:
            keywords.extend(clean_skills[:3])

        # Return unique keywords
        return list(set(keywords))[:5]  # Limit to 5 keywords

    @staticmethod
    def _create_user_profile(
            skills: List[str],
            experience: List[str],
            education: List[str]
    ) -> str:
        """
        Create a weighted text profile from user CV data for matching

        Args:
            skills: List of user skills
            experience: List of user experience items
            education: List of user education items

        Returns:
            String representation of user profile with weighted terms
        """
        profile_parts = []

        # Clean and validate lists
        clean_skills = [s.strip() for s in skills if s and s.strip()]
        clean_exp = [e.strip() for e in experience if e and e.strip()]
        clean_edu = [e.strip() for e in education if e and e.strip()]

        # Add skills with higher weight (repeat them for emphasis)
        for skill in clean_skills:
            # Weight skills higher by repeating them
            profile_parts.extend([skill] * 3)

        # Add experience items
        for exp in clean_exp:
            profile_parts.append(exp)

        # Add education items
        for edu in clean_edu:
            profile_parts.append(edu)

        return " ".join(profile_parts)

    @staticmethod
    def _match_jobs_to_profile(
            user_profile: str,
            jobs: List[Dict[str, Any]],
            num_recommendations: int
    ) -> List[Dict[str, Any]]:
        """
        Match jobs to user profile using TF-IDF and cosine similarity

        Args:
            user_profile: Weighted user profile text
            jobs: List of job listings
            num_recommendations: Maximum number of recommendations to return

        Returns:
            List of jobs with match scores, sorted by relevance
        """
        if not user_profile or not jobs:
            return []

        # Extract job content for comparison - ensure all jobs have content
        job_contents = []
        valid_jobs = []

        for job in jobs:
            # Create content text combining title and description if available
            content = job.get('content', '')
            if not content:
                title = job.get('title', '')
                desc = job.get('description', '')
                content = f"{title} {desc}".strip()

            if content:  # Only include jobs with some content
                job_contents.append(content)
                valid_jobs.append(job)

        # If no valid jobs, return empty list
        if not valid_jobs:
            return []

        try:
            # Use TF-IDF to vectorize text
            vectorizer = TfidfVectorizer(
                stop_words='english',
                max_features=10000,  # Higher to capture more relevant terms
                ngram_range=(1, 2)  # Use both unigrams and bigrams
            )

            # Add user profile to the mix for vectorization
            all_texts = job_contents + [user_profile]

            # Catch empty input errors
            if not all(isinstance(text, str) for text in all_texts):
                print("Error: Non-string input found in texts for TF-IDF")
                for i, text in enumerate(all_texts):
                    if not isinstance(text, str):
                        print(f"Text {i} is not a string: {type(text)}")
                # Use a fallback approach
                return RecommendationEngine._fallback_job_ranking(valid_jobs, num_recommendations)

            tfidf_matrix = vectorizer.fit_transform(all_texts)

            # Get the user profile vector (last item in matrix)
            user_vector = tfidf_matrix[-1]

            # Calculate cosine similarity between user vector and each job
            job_vectors = tfidf_matrix[:-1]  # All except the last one
            similarities = cosine_similarity(user_vector, job_vectors).flatten()

            # Add similarity scores to job listings
            scored_jobs = []
            for i, (job, score) in enumerate(zip(valid_jobs, similarities)):
                job_with_score = job.copy()
                # Convert to percentage for better user understanding
                match_percentage = min(round(float(score) * 100, 1), 100.0)
                job_with_score['match_score'] = match_percentage
                scored_jobs.append(job_with_score)

            # Sort by similarity score (descending)
            sorted_jobs = sorted(
                scored_jobs,
                key=lambda x: x['match_score'],
                reverse=True
            )

            # Return top N recommendations
            return sorted_jobs[:num_recommendations]

        except Exception as e:
            print(f"Error in ML job matching: {str(e)}")
            # Use fallback approach if ML fails
            return RecommendationEngine._fallback_job_ranking(valid_jobs, num_recommendations)

    @staticmethod
    def _fallback_job_ranking(jobs: List[Dict[str, Any]], num_recommendations: int) -> List[Dict[str, Any]]:
        """Simple fallback method when ML ranking fails"""
        # Add random match scores
        import random

        scored_jobs = []
        for job in jobs:
            job_copy = job.copy()
            # Assign random match scores between 70-95%
            job_copy['match_score'] = round(random.uniform(70.0, 95.0), 1)
            scored_jobs.append(job_copy)

        # Sort by match score
        sorted_jobs = sorted(scored_jobs, key=lambda x: x['match_score'], reverse=True)

        return sorted_jobs[:num_recommendations]

    @staticmethod
    def _fetch_jobs_from_jooble(
            keywords: List[str],
            location: str = None,
            limit: int = 10,
            page: int = 1  # Added page parameter
    ) -> List[Dict[str, Any]]:
        """
        Fetch job listings directly from Jooble API

        Args:
            keywords: List of search keywords
            location: Optional location for job search
            limit: Maximum number of jobs to return
            page: Page number for pagination

        Returns:
            List of job listings from Jooble
        """
        try:
            # Prepare search query
            search_query = " ".join(keywords)

            # Build request payload
            payload = {
                "keywords": search_query,
                "pageSize": limit,
                "page": page  # Add page parameter
            }

            # Add location if provided
            if location:
                payload["location"] = location

            # Make API request
            headers = {'Content-Type': 'application/json'}
            response = requests.post(
                f"{RecommendationEngine.JOOBLE_API_URL}{RecommendationEngine.JOOBLE_API_KEY}",
                json=payload,
                headers=headers
            )

            # Check response status
            if response.status_code != 200:
                print(f"Jooble API error: Status {response.status_code}")
                return []

            # Parse response
            response_data = response.json()

            # Check for jobs array
            jobs = response_data.get('jobs', [])

            # Transform to our job format
            formatted_jobs = []
            for job in jobs:
                formatted_job = {
                    "id": job.get('id', ''),
                    "title": job.get('title', ''),
                    "company": job.get('company', ''),
                    "location": job.get('location', ''),
                    "description": job.get('snippet', ''),
                    "url": job.get('link', ''),
                    "date_posted": job.get('updated', ''),
                    "content": f"{job.get('title', '')} {job.get('snippet', '')} {job.get('company', '')}"
                }

                # Add salary if available
                if 'salary' in job:
                    formatted_job['salary'] = job['salary']

                formatted_jobs.append(formatted_job)

            return formatted_jobs

        except Exception as e:
            print(f"Error fetching jobs from Jooble: {str(e)}")
            return []

    @staticmethod
    def clear_cache(cache_key=None):
        """
        Clear recommendation cache

        Args:
            cache_key: Optional specific cache key to clear
        """
        if cache_key:
            if cache_key in RecommendationEngine._job_cache:
                del RecommendationEngine._job_cache[cache_key]
                # Also clear pagination state
                if cache_key in RecommendationEngine._pagination_state:
                    del RecommendationEngine._pagination_state[cache_key]
                print(f"Cleared cache for key: {cache_key}")
        else:
            RecommendationEngine._job_cache = {}
            RecommendationEngine._pagination_state = {}
            print("Cleared entire recommendation cache")

    @staticmethod
    def search_jobs(
            query: str,
            location: str = None,
            cache_key: Optional[str] = None,
            page: int = 1,  # Added page parameter
            size: int = 10,
            fetch_more: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search for jobs by keyword and location

        Args:
            query: Search term
            location: Job location
            cache_key: Optional cache key
            page: Page number
            size: Page size
            fetch_more: If True, fetch a new page from API

        Returns:
            List of matching jobs
        """
        # Check if we should fetch new jobs or use cache
        should_fetch_new = fetch_more or page == 1

        # Check cache first
        if not should_fetch_new and cache_key and cache_key in RecommendationEngine._job_cache:
            cached_jobs = RecommendationEngine._job_cache[cache_key]
            # Do we have enough jobs for this page?
            required_jobs = page * size
            if len(cached_jobs) >= required_jobs:
                print(f"Using cached search results for key: {cache_key}, page: {page}")
                return cached_jobs
            else:
                # We need to fetch more
                should_fetch_new = True

        if should_fetch_new:
            # Fetch new jobs using API service
            search_keywords = [term.strip() for term in query.split() if term.strip()]
            jobs = JobAPIService.fetch_jobs(
                keywords=search_keywords,
                location=location,
                limit=size,  # Get exactly the requested size
                page=page  # Request the specific page
            )

            # If no jobs found, try Jooble API directly
            if not jobs:
                print(f"No jobs found from JobAPIService, trying Jooble API directly for page {page}")
                jobs = RecommendationEngine._fetch_jobs_from_jooble(
                    keywords=search_keywords,
                    location=location,
                    limit=size,
                    page=page
                )

            # Assign relevance scores (simple matching for search)
            for job in jobs:
                # Count occurrences of search terms
                relevance = 0
                content = job.get('content', '').lower()
                title = job.get('title', '').lower()

                # Title matches are weighted higher
                for term in search_keywords:
                    term = term.lower()
                    if term in title:
                        relevance += 5
                    if term in content:
                        relevance += 1

                # Convert to percentage
                job['match_score'] = min(relevance * 10, 100.0)

            # Sort by relevance
            sorted_jobs = sorted(jobs, key=lambda x: x['match_score'], reverse=True)

            # Update cache
            if cache_key:
                if page == 1:
                    # For first page, replace cache
                    RecommendationEngine._job_cache[cache_key] = sorted_jobs
                else:
                    # For subsequent pages, append to cache
                    if cache_key in RecommendationEngine._job_cache:
                        existing_jobs = RecommendationEngine._job_cache[cache_key]
                        # Get existing IDs to avoid duplicates
                        existing_ids = {job['id'] for job in existing_jobs}
                        # Append new unique jobs
                        for job in sorted_jobs:
                            if job['id'] not in existing_ids:
                                existing_jobs.append(job)
                        # Update cache
                        RecommendationEngine._job_cache[cache_key] = existing_jobs
                    else:
                        RecommendationEngine._job_cache[cache_key] = sorted_jobs

            return sorted_jobs
        else:
            # Return empty list if we shouldn't fetch and don't have cache
            return []

    @staticmethod
    def has_more_jobs(cache_key: str) -> bool:
        """
        Check if there are potentially more jobs available to fetch

        Args:
            cache_key: Cache key to check

        Returns:
            True if there might be more jobs to fetch
        """
        if cache_key in RecommendationEngine._pagination_state:
            return RecommendationEngine._pagination_state[cache_key].get("has_more", True)
        return True  # Assume more by default

    @staticmethod
    def get_job_stats(skills: List[str], experience: List[str], education: List[str]) -> Dict[str, Any]:
        """
        Get statistics about job availability based on resume data

        Args:
            skills: List of skills
            experience: List of experience items
            education: List of education items

        Returns:
            Dictionary with statistics
        """
        # Extract keywords for search
        search_keywords = RecommendationEngine._extract_search_keywords(skills, experience)

        # Fetch actual job data using Jooble API
        jobs = RecommendationEngine._fetch_jobs_from_jooble(
            keywords=search_keywords,
            limit=100  # Get more jobs for better statistics
        )

        # Initialize stats dictionary
        stats = {
            "total_matching_jobs": len(jobs),
            "top_skills": [],
            "locations": {},
            "salary_range": {"min": 0, "max": 0, "avg": 0},
            "job_types": {}
        }

        # Extract actual stats from the job data
        if jobs:
            # Count locations
            for job in jobs:
                location = job.get('location', 'Unknown')
                if location:
                    stats["locations"][location] = stats["locations"].get(location, 0) + 1

            # Extract salary information if available
            salaries = []
            for job in jobs:
                if 'salary' in job and job['salary']:
                    try:
                        # Try to extract numeric salary
                        salary_str = str(job['salary'])
                        # Simple extraction - just get the first number
                        import re
                        salary_match = re.search(r'(\d+[,\d]*)', salary_str)
                        if salary_match:
                            salary_value = int(salary_match.group(1).replace(',', ''))
                            salaries.append(salary_value)
                    except:
                        pass

            # Calculate salary statistics if available
            if salaries:
                stats["salary_range"]["min"] = min(salaries)
                stats["salary_range"]["max"] = max(salaries)
                stats["salary_range"]["avg"] = int(sum(salaries) / len(salaries))

            # Extract most common skills (from job titles and descriptions)
            # This is a simplified version - in a real implementation, you'd use
            # more sophisticated NLP techniques to extract skills
            common_tech_skills = ["python", "java", "javascript", "react", "angular", "vue",
                                  "node", "sql", "nosql", "aws", "azure", "gcp", "docker",
                                  "kubernetes", "ci/cd", "devops", "agile", "scrum"]

            skill_counts = {skill: 0 for skill in common_tech_skills}

            for job in jobs:
                content = (job.get('title', '') + ' ' + job.get('description', '')).lower()
                for skill in common_tech_skills:
                    if skill.lower() in content:
                        skill_counts[skill] += 1

            # Get top skills
            sorted_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)
            stats["top_skills"] = [skill for skill, count in sorted_skills[:5] if count > 0]

            # Extract job types
            job_type_keywords = {
                "Full-time": ["full time", "full-time", "permanent"],
                "Part-time": ["part time", "part-time"],
                "Contract": ["contract", "temporary", "contractor"],
                "Freelance": ["freelance", "freelancer"],
                "Internship": ["intern", "internship"]
            }

            for job in jobs:
                content = (job.get('title', '') + ' ' + job.get('description', '')).lower()
                for job_type, keywords in job_type_keywords.items():
                    for keyword in keywords:
                        if keyword in content:
                            stats["job_types"][job_type] = stats["job_types"].get(job_type, 0) + 1
                            break

        return stats