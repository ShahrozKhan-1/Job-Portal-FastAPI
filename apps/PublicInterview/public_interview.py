from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import JSONResponse, RedirectResponse
from apps.auth.utils import get_current_user
from database.models import PublicInterview, Job, PublicInterviewAttempt, User
from sqlalchemy.orm import Session
from database.database import get_db, engine
import os
from datetime import datetime
from database.schema import PublicInterviewCreate, PublicInterviewUpdate
import cloudinary.uploader
from config import templates
from fastapi.exceptions import HTTPException



public_interview_router = APIRouter()


@public_interview_router.api_route("/create-public-interview", methods=["GET", "POST"])
async def create_public_interview(
    request:Request,
    interview:PublicInterviewCreate | None = None,
    db:Session=Depends(get_db),
    current_user=Depends(get_current_user)
    ):
    if request.method=="GET":
        return templates.TemplateResponse("create_public_interview.html", {"request":request, "current_user":current_user})
    elif request.method=="POST":
        if current_user.is_recruiter:
            new_interview = PublicInterview(created_by=current_user.id, title=interview.title, role=interview.role, skills=interview.skills, description=interview.description, category=interview.category, status=interview.status)
            db.add(new_interview)
            db.commit()
            db.refresh(new_interview)
        return RedirectResponse(url="/", headers={"success":"Public Interview Added Successfully"}, status_code=302)



@public_interview_router.get("/recruiter-public-interview")
async def recruiter_public_interview(
    request:Request,
    interview:PublicInterviewCreate | None = None,
    db:Session=Depends(get_db),
    current_user=Depends(get_current_user)
):
    interviews = db.query(PublicInterview).filter_by(created_by=current_user.id).all()
    return templates.TemplateResponse("recruiter_public_interview.html", {"request":request, "interviews":interviews, "current_user":current_user})


@public_interview_router.api_route("/edit-public-interview/{interview_id}", methods=["GET", "PUT"])
async def edit_public_interview(
    request:Request,
    interview_id:int,
    interview:PublicInterviewUpdate | None = None,
    db:Session=Depends(get_db),
    current_user=Depends(get_current_user)
    ):
    if request.method=="GET":
        if current_user.is_recruiter:
            ex_interview = db.query(PublicInterview).filter_by(id=interview_id).first()
            return templates.TemplateResponse("edit_public_interview.html", {"request":request, "current_user":current_user, "interview":ex_interview})
    elif request.method=="PUT":
        db_interview = db.query(PublicInterview).filter_by(id=interview_id).first()
        db_interview.title = interview.title
        db_interview.skills = interview.skills
        db_interview.role = interview.role
        db_interview.status = interview.status
        db_interview.description = interview.description
        db_interview.category = interview.category
        db.commit()
        db.refresh(db_interview)
        return JSONResponse(status_code=200,content={"message": "Public Interview Updated Successfully", "id": db_interview.id})



@public_interview_router.get("/delete-public-interview/{interview_id}")
async def delete_public_interview(
    request:Request,
    interview_id:int,
    db:Session=Depends(get_db),
    current_user=Depends(get_current_user)
    ):
        if current_user.is_recruiter:
            delete_interview = db.query(PublicInterview).filter_by(id=interview_id).first()
            db.delete(delete_interview)
            db.commit()
        return RedirectResponse(url="/recruiter-public-interview", headers={"success":"Public Interview Added Successfully"}, status_code=302)
    


@public_interview_router.get("/public-interview-detail/{interview_id}")
async def public_interview_detail(
    request:Request,
    interview_id:int,
    db:Session=Depends(get_db),
    current_user=Depends(get_current_user)
):
    interview = db.query(PublicInterview).filter_by(id=interview_id).first()
    user_attempt = db.query(PublicInterviewAttempt).filter_by(interview_id=interview_id).first()
    already_attempted = user_attempt is not None
    return templates.TemplateResponse("public_interview_detail.html", {"request":request, "current_user":current_user, "interview":interview, "already_attempted": already_attempted})





@public_interview_router.get("/all-public-interviews")
async def all_public_interview(
    request:Request,
    db:Session=Depends(get_db),
    current_user=Depends(get_current_user)
):
    interviews = db.query(PublicInterview).all()
    attempted_ids = {
        attempt.interview_id 
        for attempt in db.query(PublicInterviewAttempt)
        .filter(PublicInterviewAttempt.user_id == current_user.id)
        .all()
    }

    return templates.TemplateResponse(
        "public_interviews.html",
        {
            "request": request,
            "current_user": current_user,
            "interviews": interviews,
            "attempted_ids": attempted_ids
        }
    )



@public_interview_router.post("/upload-resume/{interview_id}")
async def upload_resume(
    interview_id: int,
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    if not resume:
        raise HTTPException(status_code=400, detail="Resume file is required.")

    contents = await resume.read()
    upload = cloudinary.uploader.upload(
        contents,
        resource_type="raw",
        public_id=resume.filename,
        use_filename=True,
        unique_filename=False 
    )
    resume_url = upload.get("secure_url")

    attempt = PublicInterviewAttempt(
        interview_id=interview_id,
        user_id=current_user.id,
        resume=resume_url,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return {
        "message": "Resume uploaded successfully",
        "resume_url": resume_url,
        "attempt_id": attempt.id
    }


@public_interview_router.get("/public-interview/start/{interview_id}")
async def start_public_interview(
    request: Request,
    interview_id: int,
    attempt_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    interview = db.query(PublicInterview).filter_by(id=interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    attempt = (
        db.query(PublicInterviewAttempt)
        .filter_by(id=attempt_id, interview_id=interview_id, user_id=current_user.id)
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=403, detail="Unauthorized or invalid attempt")

    return templates.TemplateResponse(
        "public_interview_chat.html",
        {
            "request": request,
            "interview": interview,
            "attempt": attempt,
            "current_user": current_user,
        },
    )


@public_interview_router.post("/upload-public-interview-video")
async def upload_interview_video(
    video: UploadFile = File(...),
    interview_id: str = Form(...),
    attempt_id: str = Form(...),
    db:Session=Depends(get_db)
):
    try:
        upload_result = cloudinary.uploader.upload(
            video.file,
            resource_type="video",
            folder="interview_videos",
            public_id=f"interview_{interview_id}_attempt_{attempt_id}_{datetime.utcnow().timestamp()}",
            overwrite=True
        )
        video_url = upload_result.get("secure_url")

        attempt = db.query(PublicInterviewAttempt).filter(PublicInterviewAttempt.id == attempt_id).first()
        if attempt:
            attempt.video = video_url
            db.commit()

        return {
            "success": True,
            "video_url": video_url,
            "public_id": upload_result.get("public_id")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video upload failed: {str(e)}")
    


@public_interview_router.get("/public-interview-results/{interview_id}")
async def public_interview_results(
    request: Request,
    interview_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    if not current_user.is_recruiter:
        raise HTTPException(status_code=403, detail="Access denied")
    
    interview = db.query(PublicInterview).filter_by(id=interview_id, created_by=current_user.id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    attempts = (
        db.query(PublicInterviewAttempt)
        .join(User, PublicInterviewAttempt.user_id == User.id)
        .filter(PublicInterviewAttempt.interview_id == interview_id)
        .order_by(PublicInterviewAttempt.attempted_at.desc())
        .all()
    )
    
    return templates.TemplateResponse(
        "public_interview_results.html",
        {
            "request": request,
            "current_user": current_user,
            "interview": interview,
            "attempts": attempts
        }
    )

@public_interview_router.get("/public-interview-attempt-detail/{attempt_id}")
async def public_interview_attempt_detail(
    request: Request,
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    if not current_user.is_recruiter:
        raise HTTPException(status_code=403, detail="Access denied")
    attempt = (
        db.query(PublicInterviewAttempt)
        .join(PublicInterview, PublicInterviewAttempt.interview_id == PublicInterview.id)
        .join(User, PublicInterviewAttempt.user_id == User.id)
        .filter(
            PublicInterviewAttempt.id == attempt_id,
            PublicInterview.created_by == current_user.id
        )
        .first()
    )
    
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    
    return templates.TemplateResponse(
        "public_interview_attempt_detail.html",
        {
            "request": request,
            "current_user": current_user,
            "attempt": attempt,
            "interview": attempt.interview,
            "user": attempt.user
        }
    )