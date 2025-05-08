# app/schemas/schemas.py

from pydantic import BaseModel

# Removed Optional as unused based on previous Ruff report
# Keep List if used elsewhere
from typing import List


# Example Schema (Replace/Add your actual schemas)
class BaseResponse(BaseModel):
    message: str


class ResumeDataInput(BaseModel):  # Example for input validation
    skills: List[str] = []  # Use default empty list instead of None?
    experience: List[str] = []
    education: List[str] = []
    location: str | None = None  # Use | None syntax


# If you define response models using Pydantic, ensure imports match the types used.
