from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import JSONResponse, RedirectResponse
from apps.auth.utils import get_current_user
from database.models import Job, Applicant, User, SaveJob, Interview
from sqlalchemy.orm import Session
from database.database import get_db
from database.schema import JobResponse, JobCreate, ApplicantResponse, JobEdit, UpdateUser, SaveJobResponse
import cloudinary.uploader
from apps.auth.utils import get_password_hash, verify_password
from typing import List
from config import templates
import subprocess
from datetime import datetime, timedelta
import requests
import sys
from utils.ai_model import analyze_resume
import io
from smtplib import SMTP
from sqlalchemy import and_
from email.mime.text import MIMEText
from PyPDF2 import PdfReader
import os
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import asyncio

load_dotenv()

dashboard_router = APIRouter()


@dashboard_router.get("/landing-page")
async def landing_page(request:Request):
    return templates.TemplateResponse("landingpage.html", {"request":request})


@dashboard_router.get("/", response_model=list[JobResponse])
async def dashboard(request:Request, 
    current_user: str = Depends(get_current_user),
    db:Session=Depends(get_db)
    ):
    jobs = db.query(Job).order_by(Job.created_at.desc()).all()
    applications_count = db.query(Applicant).filter(Applicant.applicant == current_user.id).count()
    saved_count = db.query(SaveJob).filter(SaveJob.user_id == current_user.id).count()
    shortlisted_count = db.query(Applicant).filter(
        Applicant.applicant == current_user.id,
        Applicant.status == "shortlisted"
    ).count()
    stats = {
        "applications": applications_count,
        "saved": saved_count,
        "shortlisted": shortlisted_count
    }
    return templates.TemplateResponse("dashboard.html", {"request":request, "jobs":jobs, "current_user":current_user, "stats":stats})


@dashboard_router.get("/add-job")
async def add_job(request:Request, current_user:str=Depends(get_current_user)):
    return templates.TemplateResponse("addjob.html", {"request":request, "current_user":current_user})


@dashboard_router.post("/add-job", response_model=JobResponse)
async def add_job(
    request:Request, 
    job:JobCreate,
    db:Session=Depends(get_db),
    current_user=Depends(get_current_user)
    ):
    if current_user.is_recruiter:
        existing_job = db.query(Job).filter(
            Job.title == job.title,
            Job.company == job.company,
            Job.location == job.location,
            Job.posted_on == job.posted_on
        ).first()

        if existing_job:
            return JSONResponse({"msg": "Job already exists, skipping insert."}, status_code=400)

        new_job = Job(
            link=job.link if job.link else None,
            logo=job.logo,
            title=job.title,
            company=job.company,
            location=job.location,
            description=job.description,
            responsibilities=job.responsibilities, 
            requirements = job.requirements,
            job_function=job.job_function,
            salary=job.salary,
            industry=job.industry,
            seniority_level = job.seniority_level,
            employment_type = job.employment_type,
            posted_on = job.posted_on,
            source = job.source,
            skills = job.skills,
            user_id = current_user.id
            )
        if not new_job:
            return JSONResponse({"msg":"No data entered"})
        db.add(new_job)
        db.commit()
        db.refresh(new_job)
        return new_job
    return RedirectResponse(url="/", headers={"success":"Job Added Successfully"}, status_code=302)


@dashboard_router.get("/delete-job/{job_id}")
async def delete_job(job_id:int, db:Session=Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.is_recruiter:
        delete_job = db.query(Job).filter_by(id=job_id).first()
        if current_user.id != delete_job.user_id:
            return JSONResponse({"message":"Only the owner can delete this job"})
        if not delete_job:
            return JSONResponse({"message":"Can not delete the job"})
        db.delete(delete_job)
        db.commit()
    return RedirectResponse(url="/", headers={"success":"Job Deleted Successfully"}, status_code=302)


@dashboard_router.get("/edit-job/{job_id}")
def get_edit_job(
    job_id:int,
    request:Request,
    db:Session=Depends(get_db),
    current_user=Depends(get_current_user)
):
    job = db.query(Job).filter_by(id=job_id).first()
    return templates.TemplateResponse("editjob.html", {"request":request, "job":job, "current_user":current_user})


@dashboard_router.put("/edit-job/{job_id}")
async def put_edit_job(
    job_id: int,
    request: Request,
    job:JobEdit,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    if current_user.is_recruiter:
        db_job = db.query(Job).filter_by(id = job_id).first()
        if current_user.id != db_job.user_id:
            return JSONResponse({"message":"Only the owner can edit this job"})
        if not db_job:
            return JSONResponse({"message":"Job not found"})
        db_job.title=job.title 
        db_job.link=job.link 
        db_job.logo=job.logo 
        db_job.description=job.description 
        db_job.requirements=job.requirements 
        db_job.company=job.company 
        db_job.responsibilities=job.responsibilities 
        db_job.seniority_level=job.seniority_level
        db_job.employment_type=job.employment_type
        db_job.posted_on=job.posted_on
        db_job.job_function=job.job_function
        db_job.industry=job.industry
        db_job.source=job.source
        db_job.salary=job.salary
        db.commit()
        db.refresh(db_job)
        return RedirectResponse(url="/", headers={"success":"Job Edited Successfully"}, status_code=302)
    return JSONResponse({"message":"Only recruiter can edit job"})


@dashboard_router.get("/apply-job/{job_id}")
async def apply_job(
    request:Request,
    job_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    db_job = db.query(Applicant).filter_by(applied_for=job_id, applicant=current_user.id).first()
    if db_job:
        return JSONResponse({"message":"You have already applied for job"})
    job = db.query(Job).filter_by(id=job_id).first()
    return templates.TemplateResponse("applyjob.html", {"request":request, "job":job, "current_user":current_user})


@dashboard_router.post("/apply-job/{job_id}")
async def apply_job(
    request:Request,
    job_id: int,
    address:str = Form(...),
    number:str = Form(...),
    email:str = Form(...),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    db_job = db.query(Applicant).filter_by(applied_for=job_id, applicant=current_user.id).first()
    if db_job:
        return JSONResponse({"message":"You have already applied for job"})
    if current_user.is_recruiter:
        return JSONResponse({"message":"Recruiter can not apply for job"})
    file_url = None
    if resume:
        contents = await resume.read()
        upload = cloudinary.uploader.upload(
            contents,
            resource_type="raw",
            public_id=resume.filename,
            use_filename=True,
            unique_filename=False 
        )
        file_url = upload.get("secure_url")
    applicant = Applicant(
        applicant = current_user.id,
        applied_for=job_id,
        resume=file_url,
        address=address,
        email = email,
        number=number
    )
    db.add(applicant)
    db.commit()
    db.refresh(applicant)
    return RedirectResponse(url="/", headers={"success":"Job Applied Successfully"}, status_code=302)


@dashboard_router.get("/get-applicant", response_model=List[ApplicantResponse])
async def get_applicants(
    request:Request,
    db:Session=Depends(get_db),
    current_user=Depends(get_current_user)
):
    if current_user.is_recruiter:
        jobs = db.query(Job.id).filter_by(user_id=current_user.id).subquery()
        applicants = db.query(Applicant).filter(Applicant.applied_for.in_(jobs)).all()
        return templates.TemplateResponse("getapplicants.html", {"current_user":current_user, "request":request, "applicants":applicants})



@dashboard_router.get("/get-job-applicant/{job_id}", response_model=List[ApplicantResponse])
async def get_job_applicant(
    job_id:int,
    db:Session=Depends(get_db),
    current_user=Depends(get_current_user)
):
    if current_user.is_recruiter:
        job = db.query(Job).filter_by(id=job_id).first()
        if current_user.id != job.user_id:
            return JSONResponse({"message":"Only the owner can see job applicant"})
        applicants = db.query(Applicant).filter_by(applied_for=job_id).all()
        return applicants
    

@dashboard_router.get("/get-job-detail/{job_id}")
async def get_job_detail(
    job_id:int,
    request:Request,
    current_user = Depends(get_current_user),
    db:Session=Depends(get_db)
    ):
    job = db.query(Job).filter_by(id=job_id).first()
    return templates.TemplateResponse("getjobdetail.html", {"job":job, "current_user":current_user, "request":request})


@dashboard_router.get("/profile")
async def get_profile(request:Request, current_user=Depends(get_current_user)):
    return templates.TemplateResponse("profile.html", {"request":request, "current_user":current_user})


@dashboard_router.get("/application-sent", response_model=List[ApplicantResponse])
async def application_sent(
    request:Request,
    current_user=Depends(get_current_user),
    db:Session=Depends(get_db)
):
    if not current_user.is_recruiter:
        applications = db.query(Applicant).filter(Applicant.applicant==current_user.id).all()
        return templates.TemplateResponse("applicationsent.html", {"current_user":current_user, "request":request, "applications":applications, "datetime": datetime, "timedelta":timedelta})
    return JSONResponse({"message":"Only Applicants can access"})


@dashboard_router.post("/profile")
async def post_profile(
    request: Request,
    user: UpdateUser,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    db_user = db.query(User).filter_by(id=current_user.id).first()
    if not db_user:
        return JSONResponse({"message": "User not found"})
    if user.name:
        db_user.name = user.name

    if user.new_password:
        if not user.current_password:
            return JSONResponse({"message": "Current password is required"})

        if not verify_password(user.current_password, db_user.password):
            return JSONResponse({"message": "Current password is incorrect"})

        db_user.password = get_password_hash(user.new_password)

    db.commit()
    db.refresh(db_user)
    return {
        "success": "Profile updated successfully",
        "user": {"name": db_user.name, "email": db_user.email}
    }


@dashboard_router.post("/save-job/{job_id}")
async def save_job(
    request: Request,
    job_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_job = db.query(Job).filter_by(id=job_id).first()
    if not db_job:
        return JSONResponse({"message": "Job not found"})
    existing = db.query(SaveJob).filter_by(job_id=job_id, user_id=current_user.id).first()
    if existing:
        return JSONResponse({"message": "You already saved this job"})

    save_job = SaveJob(job_id=job_id, user_id=current_user.id)
    db.add(save_job)
    db.commit()
    db.refresh(save_job)
    return RedirectResponse(url="/", headers={"success": "Job Saved Successfully"}, status_code=302)


@dashboard_router.get("/saved-job", response_model=List[SaveJobResponse])
async def saved_job(
    request:Request,
    current_user=Depends(get_current_user),
    db:Session=Depends(get_db)
):
    jobs = db.query(SaveJob).filter_by(user_id=current_user.id).all()
    return templates.TemplateResponse("savedjobs.html", {"request":request, "current_user":current_user, "jobs":jobs})


@dashboard_router.get("/delete-saved-job/{job_id}")
async def delete_saved_job(
    request:Request,
    job_id:int,
    current_user=Depends(get_current_user),
    db:Session=Depends(get_db)
):
    job = db.query(SaveJob).filter_by(id=job_id).first()
    if not job:
        return JSONResponse({"message":"Job not found"})
    db.delete(job)
    db.commit()
    return RedirectResponse(url="/saved-job",headers={"sucess":"job removed from save successfully"} ,status_code=302)


@dashboard_router.get("/applicant-detail/{applicant_id}", response_model=List[ApplicantResponse])
async def applicant_detail(
    applicant_id:int,
    request:Request,
    current_user=Depends(get_current_user),
    db:Session=Depends(get_db)
):
    applicant = db.query(Applicant).filter_by(id=applicant_id).first()
    return templates.TemplateResponse("applicantdetail.html", {"request":request, "current_user":current_user, "applicant":applicant})



async def send_email(recipient_email: str, status: str, interview_time: datetime | None = None):
    sender = os.getenv("SENDER_EMAIL")
    app_password = os.getenv("GOOGLE_EMAIL_PASSWORD")

    if not sender or not app_password:
        print("Missing email credentials in environment variables.")
        return
    subject = f"Application Status Update: {status.capitalize()}"
    interview_info = ""
    if interview_time:
        interview_info = f"<p><strong>Interview Scheduled:</strong> {interview_time.strftime('%A, %d %B %Y at %I:%M %p')}</p>"

    if status.lower() == "accepted":
        body_html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                <p>Dear Applicant,</p>
                <p>🎉 Congratulations! Your application has been 
                <strong style="color: green;">Accepted</strong>.</p>
                {interview_info}
                <p>Our team will reach out soon with the next steps.</p>
                <p>Best regards,<br><strong>Your HR Team</strong></p>
            </body>
        </html>
        """
    elif status.lower() == "rejected":
        body_html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                <p>Dear Applicant,</p>
                <p>We regret to inform you that your application has been 
                <strong style="color: red;">Rejected</strong>.</p>
                <p>Thank you for taking the time to apply. We encourage you to apply again in the future.</p>
                <p>Best wishes,<br><strong>Your HR Team</strong></p>
            </body>
        </html>
        """
    else:
        body_html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                <p>Dear Applicant,</p>
                <p>Your application status has been updated to 
                <strong>{status.capitalize()}</strong>.</p>
                {interview_info}
                <p>Our team is still reviewing your details.</p>
                <p>Best regards,<br><strong>Your HR Team</strong></p>
            </body>
        </html>
        """

    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = recipient_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body_html, "html"))

    def _send_email_blocking():
        try:
            with SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(sender, app_password)
                server.send_message(msg)
            print(f"Email sent successfully to {recipient_email}")
        except Exception as e:
            print(f"Failed to send email to {recipient_email}: {e}")

    await asyncio.to_thread(_send_email_blocking)




@dashboard_router.post("/applicant-status/{applicant_id}")
async def applicant_status(
    applicant_id: int,
    request: Request,
    status: str = Form(...),
    interview_date: str = Form(None),
    interview_time: str = Form(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    applicant = db.query(Applicant).filter_by(id=applicant_id).first()
    if not applicant:
        return JSONResponse({"message": "Applicant not found"}, status_code=404)

    applicant.status = status

    if interview_date and interview_time:
        try:
            combined_dt = datetime.strptime(f"{interview_date} {interview_time}", "%Y-%m-%d %H:%M")
            applicant.interview_time = combined_dt
        except ValueError:
            return JSONResponse({"message": "Invalid date or time format"}, status_code=400)
    db.commit()
    db.refresh(applicant)

    asyncio.create_task(send_email(applicant.email, status, applicant.interview_time))

    return RedirectResponse(
        url="/get-applicant",
        status_code=302,
        headers={"success": "User status and interview time updated successfully"},
    )



@dashboard_router.post("/search")
async def post_search(
    title: str = Form(None),
    location: str = Form(None),
):
    query_params = []

    if title:
        query_params.append(f"title={title}")
    if location:
        query_params.append(f"location={location}")

    query_string = "&".join(query_params)
    return RedirectResponse(url=f"/search?{query_string}", status_code=303)


@dashboard_router.get("/search")
async def get_search(
    request: Request,
    title: str = None,
    location: str = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    results = []

    if title or location:
        query = db.query(Job)

        if title and location:
            query = query.filter(
                and_(
                    Job.title.ilike(f"%{title}%"),
                    Job.location.ilike(f"%{location}%")
                )
            )
        elif title:
            query = query.filter(Job.title.ilike(f"%{title}%"))
        elif location:
            query = query.filter(Job.location.ilike(f"%{location}%"))

        results = query.all()

    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "current_user": current_user,
            "results": results,
            "title": title,
            "location": location,
        }
    )


@dashboard_router.get("/created-jobs")
async def created_jobs(
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.is_recruiter:
        jobs = db.query(Job).filter_by(user_id=current_user.id).all()
        return templates.TemplateResponse("createdjobs.html", {
            "request": request,
            "current_user": current_user,
            "jobs": jobs
        })
    return RedirectResponse(url="/", status_code=302)


@dashboard_router.post('/scrap_rozeepk')
async def scrap_rozeepk(request:Request, job_title = Form(...), location = Form(...), source=Form(...), current_user=Depends(get_current_user)):  # rozeepk or linkedin
    if source == "rozeepk":
        result = scrape_rozee(request, job_title, location)
    elif source == "linkedin":
        result = scrape_linkedin(request, job_title, location)
    else:
        result = {"error": "Unknown source"}
    return result

def scrape_rozee(request:Request,  job_title, location):
    script_path = "scrapper/rozeepk.py"
    token = request.cookies.get("access_token")
    subprocess.Popen([sys.executable, script_path, token, job_title, location])


def scrape_linkedin(request:Request, job_title, location):
    script_path = "scrapper/linkedin_scrapper.py"
    token = request.cookies.get("access_token")
    subprocess.Popen([sys.executable, script_path, token, job_title, location])



async def extract_pdf_text(pdf_input):
    text = ""

    # If input is a URL
    if isinstance(pdf_input, str) and (pdf_input.startswith("http://") or pdf_input.startswith("https://")):
        try:
            response = requests.get(pdf_input)
            response.raise_for_status()
            pdf_file = io.BytesIO(response.content)
            reader = PdfReader(pdf_file)
            for page in reader.pages:
                text += page.extract_text() or ""
            return text
        except Exception as e:
            raise ValueError(f"Error reading PDF from URL: {str(e)}")

    # If input is UploadFile (FastAPI) - ASYNC VERSION
    try:
        if hasattr(pdf_input, 'read') and hasattr(pdf_input, 'filename'):
            # Reset to beginning and read
            await pdf_input.seek(0)
            pdf_bytes = await pdf_input.read()
            pdf_file = io.BytesIO(pdf_bytes)
            reader = PdfReader(pdf_file)
            for page in reader.pages:
                text += page.extract_text() or ""
            return text
    except Exception as e:
        raise ValueError(f"Error reading UploadFile: {str(e)}")

    # If input is already bytes
    if isinstance(pdf_input, (bytes, bytearray)):
        pdf_file = io.BytesIO(pdf_input)
        reader = PdfReader(pdf_file)
        for page in reader.pages:
            text += page.extract_text() or ""
        return text

    raise ValueError(f"Invalid input type: {type(pdf_input)}. Must be URL string, UploadFile, or bytes.")

@dashboard_router.get("/applicant-reviewer/{applicant_id}")
async def applicant_reviewer(applicant_id:int, request:Request, db:Session=Depends(get_db), current_user=Depends(get_current_user)):
    applicant = db.query(Applicant).filter_by(id=applicant_id).first()

    resume = await extract_pdf_text(applicant.resume)
    system_prompt = """
        {
            "role": "professional career advisor and recruitment analyst",
            "primary_goal": "evaluate a candidate's resume against a specific job description and assess alignment with the job role",
            "workflow": [
                {
                    "step": 1,
                    "action": "analyze job description",
                    "tasks": [
                        "extract key requirements, responsibilities, and preferred qualifications"
                    ]
                },
                {
                    "step": 2,
                    "action": "review candidate's resume",
                    "tasks": [
                        "identify relevant experience, skills, education, and accomplishments"
                    ]
                },
                {
                    "step": 3,
                    "action": "compare resume against job description",
                    "tasks": [
                        "highlight strong matches and relevant qualifications",
                        "identify gaps or missing requirements",
                        "note transferable skills or potential strengths (if clearly evidenced)"
                    ]
                }
            ],
            "output_format": {
                "required_structure": "JSON only, no text outside JSON",
                "fields": {
                    "match_score": {
                        "type": "integer",
                        "range": "0-100",
                        "description": "overall alignment score based on qualifications, skills, and experience"
                    },
                    "strengths": {
                        "type": "array",
                        "description": "key strengths that match with the job"
                    },
                    "weaknesses": {
                        "type": "array",
                        "description": "gaps or missing qualifications or information relevant to the job"
                    },
                    "overview": {
                        "type": "string",
                        "description": "concise summary of how well the candidate fits the role"
                    },
                    "fit_for_job": {
                        "type": "string",
                        "options": ["Yes", "No"],
                        "description": "final recommendation"
                    },
                    "reason_for_fit": {
                        "type": "string",
                        "description": "two to three sentences explaining the decision"
                    }
                }
            },
            "guidelines": [
                "ALWAYS return output in valid JSON only, never include extra commentary or markdown",
                "Use ONLY information present in the resume and job description",
                "Do not fabricate or assume details",
                "Be objective, concise, and professional"
            ]
        }
        """
    result = await analyze_resume(applicant.job.requirements, applicant.job.description, applicant.job.responsibilities, applicant.job.skills, resume, system_prompt)
    return templates.TemplateResponse("applicant_reviewer.html", {"request":request, "current_user":current_user, "result":result, "applicant":applicant})




@dashboard_router.get("/applicant-self-check")
async def applicant_self_check(
    request: Request,
    current_user=Depends(get_current_user)
):
    if not current_user.is_recruiter:
        return templates.TemplateResponse("applicant_self_check.html" ,{"request":request, "current_user":current_user} )
    return JSONResponse({"message":"only applicant can check their resume"})


@dashboard_router.get("/api/jobs/search")
async def job_search(
    title: str = "",
    location: str = "",
    source: str = "",
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    query = db.query(Job)
    if title:
        query = query.filter(Job.title.contains(title))
    if location:
        query = query.filter(Job.location.contains(location))
    if source:
        query = query.filter(Job.source == source)

    results = query.all()
    return results


@dashboard_router.post("/api/ai/assess")
async def job_search(
    job_id: str = Form(None),
    resume: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    job = db.query(Job).filter(Job.id==int(job_id)).first()
    if resume:
        resume_text = await extract_pdf_text(resume)
    system_prompt = """
            {
                "role": "career coach and resume optimization expert",
                "primary_goal": "help candidates understand how well their resume matches a specific job and provide actionable advice for improvement",
                "workflow": [
                    {
                        "step": 1,
                        "action": "analyze job description",
                        "tasks": [
                            "extract required qualifications, skills, and experience",
                            "identify preferred qualifications and nice-to-haves",
                            "note key responsibilities and technologies mentioned"
                        ]
                    },
                    {
                        "step": 2,
                        "action": "review candidate's resume",
                        "tasks": [
                            "identify explicitly stated experience, skills, and education",
                            "look for quantifiable achievements and relevant accomplishments",
                            "note the presentation and organization of information"
                        ]
                    },
                    {
                        "step": 3,
                        "action": "compare and assess alignment",
                        "tasks": [
                            "match specific resume items against job requirements",
                            "identify gaps and missing qualifications",
                            "evaluate the strength of alignment in each area"
                        ]
                    },
                    {
                        "step": 4,
                        "action": "provide constructive feedback",
                        "tasks": [
                            "focus on growth and improvement opportunities",
                            "offer specific, implementable advice",
                            "suggest resume optimization strategies"
                        ]
                    }
                ],
                "output_format": {
                    "required_structure": "JSON only, no text outside JSON",
                    "fields": {
                        "match_score": {
                            "type": "integer",
                            "range": "0-100",
                            "description": "overall alignment score"
                        },
                        "strengths": {
                            "type": "array",
                            "description": "specific qualifications and skill matches from resume"
                        },
                        "improvement_areas": {
                            "type": "array",
                            "description": "missing qualifications and skill gaps with evidence"
                        },
                        "missing_requirements": {
                            "type": "array",
                            "description": "required qualifications and essential skills not found"
                        },
                        "actionable_advice": {
                            "type": "array",
                            "description": "specific improvement steps and skill development suggestions"
                        },
                        "resume_tips": {
                            "type": "array",
                            "description": "concrete resume optimizations and presentation improvements"
                        },
                        "overview": {
                            "type": "string",
                            "description": "2-3 sentence encouraging but honest summary of fit and next steps"
                        }
                    }
                },
                "guidelines": [
                    "ALWAYS return output strictly in valid JSON only, never include extra commentary or markdown",
                    "Use ONLY information present in the resume and job description",
                    "Do not fabricate or assume details",
                    "Be objective, concise, and professional"
                ],
                "core_principles": [
                    "Always be constructive, specific, and evidence-based",
                    "Help candidates understand both their current standing and how to improve"
                ]
            }
        """
    result = await analyze_resume(job.requirements, job.description, job.responsibilities, job.skills, resume_text, system_prompt)
    return result



# @dashboard_router.get("/clear-applicants")
# def clear_applicants(db: Session = Depends(get_db)):
#     db.query(Interview).delete()  # deletes all rows
#     db.commit()
#     return {"message": "All applicants deleted"}