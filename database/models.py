from database.database import Base
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, JSON, Text, Float
from datetime import datetime
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func


class User(Base):
    __tablename__ = "users"

    id = Column(Integer(), primary_key=True)
    name = Column(String(256), nullable=False)
    email = Column(String(256), nullable=False)
    password = Column(String(256), nullable=False)
    is_recruiter = Column(Boolean, default=False)



class Job(Base):
    __tablename__ = "job"

    id = Column(Integer, primary_key=True, index=True)
    link = Column(String, nullable=True)
    logo = Column(String, nullable=True)
    title = Column(String, nullable=False)
    company = Column(String, nullable=True)
    location = Column(String, nullable=True)
    salary = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    responsibilities = Column(Text, nullable=True)
    requirements = Column(Text, nullable=True)
    skills = Column(JSON, nullable=True) 
    seniority_level = Column(String, nullable=True)
    employment_type = Column(String, nullable=True)
    job_function = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    posted_on = Column(String, nullable=True)
    source = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer(), ForeignKey('users.id'))
    
    user = relationship("User", backref=backref("job", cascade='all, delete-orphan'))

    
    
class Applicant(Base):
    __tablename__="applicants"

    id = Column(Integer(), primary_key=True)
    number = Column(String(256), nullable=False)
    email = Column(String(256), nullable=True)
    address = Column(String(256), nullable=False)
    applicant = Column(Integer(), ForeignKey('users.id'))
    applied_for = Column(Integer(), ForeignKey('job.id'))
    applied_time = Column(DateTime, default = datetime.utcnow)
    interview_time = Column(DateTime, nullable=True)
    resume = Column(String(256), nullable=False)
    status = Column(String(256), nullable=False, default="pending")

    user = relationship("User", backref=backref("applicants", cascade='all, delete-orphan'))
    job = relationship("Job", backref=backref("applicants", cascade='all, delete-orphan'))



class SaveJob(Base):
    __tablename__="savejob"

    id = Column(Integer(), primary_key=True)
    user_id = Column(Integer(), ForeignKey('users.id'))
    job_id = Column(Integer(), ForeignKey('job.id'))
    
    user = relationship("User", backref=backref("savejob", cascade='all, delete-orphan'))
    job = relationship("Job", backref=backref("savejob", cascade='all, delete-orphan'))



class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True)
    applicant_id = Column(Integer, ForeignKey("applicants.id"), nullable=False)
    transcript = Column(JSON, default=[])
    question_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    video = Column(String(256), nullable=True)

    score = Column(Float, nullable=True)
    status = Column(String(50), nullable=True, default=False)  # "pass" / "fail"
    feedback = Column(Text, nullable=True)

    applicant = relationship("Applicant", backref=backref("interview", uselist=False))



class PublicInterview(Base):
    __tablename__ = "public_interviews"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    title = Column(String(255), nullable=False)
    role = Column(String(256), nullable=True)
    skills = Column(JSON, nullable=True) 
    description = Column(Text)
    category = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = relationship("User", backref="public_interviews")
    attempts = relationship("PublicInterviewAttempt", backref="interview", lazy="select", cascade="all, delete-orphan")



class PublicInterviewAttempt(Base):
    __tablename__ = "public_interview_attempts"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("public_interviews.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    transcript = Column(JSON, default=[])
    resume = Column(String(256), nullable=False)
    score = Column(Float, nullable=True)
    feedback = Column(Text, nullable=True)
    attempted_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    video = Column(String(256), nullable=True)

    user = relationship("User", backref="public_interview_attempts")