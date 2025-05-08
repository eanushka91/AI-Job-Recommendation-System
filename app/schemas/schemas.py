# app/schemas/schemas.py

from pydantic import BaseModel
# Removed Optional from import as it was reported unused (F401)
# Keep List if it is used elsewhere in the file.
from typing import List

# Example Schema (Replace with your actual schemas)
class BaseResponse(BaseModel):
    message: str

class ResumeData(BaseModel): # Example
    skills: List[str] | None = None
    experience: List[str] | None = None
    education: List[str] | None = None

# --- Add your other Pydantic models/schemas here ---
# If you use the `Optional[...]` syntax for type hints, you need to re-add the import.
# If you use `field: type | None = None`, then `Optional` is not needed.

