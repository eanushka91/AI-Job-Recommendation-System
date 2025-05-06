from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ResumeResponse(BaseModel):
    """Schema for resume response"""
    id: int
    user_id: int
    cv_url: str
    skills: List[str]
    experience: List[str]
    education: List[str]
    location: str
    created_at: datetime

class UploadResponse(BaseModel):
    """Schema for upload response"""
    message: str
    url: str
    resume_id: int