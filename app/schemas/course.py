from pydantic import BaseModel, Field
from typing import List, Optional

class CourseBase(BaseModel):
    title: str
    description: Optional[str] = None
    branch: str

class CourseCreate(CourseBase):
    pass

class Course(CourseBase):
    id: str
    created_at: str

    class Config:
        from_attributes = True
