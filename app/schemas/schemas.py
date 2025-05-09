from pydantic import BaseModel

from typing import List


class BaseResponse(BaseModel):
    message: str


class ResumeDataInput(BaseModel):
    skills: List[str] = []
    experience: List[str] = []
    education: List[str] = []
    location: str | None = None
