from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime, date

class Token(BaseModel):
    access_token:str
    token_type:str


class AddUser(BaseModel):
    name:str
    email:str
    password:str = Field(min_length=8, max_length=12)
    is_recruiter:bool = Field(default=False)
    
class LoginUser(BaseModel):
    email:str
    password:str = Field(min_length=8, max_length=12)

class UpdateUser(BaseModel):
    name: str | None = None
    current_password: str | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=12)


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    class Config:
        from_attributes = True  



class JobBase(BaseModel):
    link: Optional[str] = None
    logo: str | None = None
    title: str
    company: str
    location: str
    salary: str | None = None
    description: str
    seniority_level: str | None = None
    employment_type: str | None = None
    job_function: str | None = None
    industry: str | None = None
    requirements: str | None = None
    responsibilities: str | None = None
    skills: List[str] = []
    posted_on: str | None = None
    source:str

class JobCreate(JobBase):
    pass

class JobEdit(JobBase):
    user_id: int 

class JobResponse(JobBase):
    pass
    class Config:
        from_attributes = True 




class ApplicantBase(BaseModel):
    job_id: int
    user_id: int

class ApplicantCreate(ApplicantBase):
    resume: str
    number: str
    address: str

class ApplicantResponse(BaseModel):
    user:UserResponse
    applied_for:JobResponse
    applied_time:datetime
    resume:str
    number: str
    address: str    
    class Config:
        from_attributes = True



class SaveJobBase(BaseModel):
    job_id: int

class SaveJobResponse(BaseModel):
    id: int
    job_id: JobResponse
    user_id: UserResponse

    class Config:
        from_attributes = True



class PublicInterviewAttemptBase(BaseModel):
    answers: List[str] = []
    score: float = None
    feedback: str = None

class PublicInterviewAttemptCreate(PublicInterviewAttemptBase):
    interview_id: int
    user_id: int

class PublicInterviewAttemptResponse(PublicInterviewAttemptBase):
    id: int
    interview_id: int
    user_id: int
    attempted_at: datetime

    class Config:
        from_attributes = True



class PublicInterviewBase(BaseModel):
    title: str
    role: str
    skills: List[str] = []
    description: str = None
    category: str = None
    status: bool = Field(default=True)

class PublicInterviewCreate(PublicInterviewBase):
    pass

class PublicInterviewUpdate(BaseModel):
    title: str = None
    role: str = None
    skills: List[str] = []
    description: str = None
    category: str = None
    status: bool = Field(default=True)

class PublicInterviewResponse(PublicInterviewBase):
    id: int
    created_by: int
    created_at: datetime
    updated_at: datetime
    attempts: List[PublicInterviewAttemptResponse] = []
    status: bool = Field(default=True)

    class Config:
        from_attributes = True