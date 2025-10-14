from fastapi import APIRouter, Request, Depends, Form, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from apps.auth.utils import get_current_user
from database.models import Applicant, Interview
from sqlalchemy.orm import Session
from database.database import get_db
from config import templates
import datetime
from utils.ai_model import evaluate_interview_ai
import cloudinary.uploader




interview_router = APIRouter()


@interview_router.get("/interview/{job_id}")
async def interview(
    request:Request,
    job_id : int,
    db:Session=Depends(get_db),
    current_user = Depends(get_current_user)
):
    applicant = db.query(Applicant).filter(Applicant.applied_for==job_id).first()
    return templates.TemplateResponse("interview.html", {"current_user":current_user, "request":request, "applicant":applicant})


@interview_router.get("/chat")
async def chat(request: Request, applicant_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    applicant = db.query(Applicant).filter_by(id=applicant_id).first()
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "applicant": applicant,
        "current_user":current_user
    })


@interview_router.post("/save-interview/{applicant_id}")
async def save_interview(applicant_id: int, data: dict, db: Session = Depends(get_db)):
    applicant = db.query(Applicant).filter_by(id=applicant_id).first()
    if not applicant:
        return JSONResponse(status_code=404, content={"detail": "Applicant not found"})
    transcript = data.get("transcript", [])
    if not transcript:
        return JSONResponse(status_code=400, content={"detail": "Transcript is empty"})
    ai_result = await evaluate_interview_ai(transcript)
    score = ai_result.get("score", 0)
    status = ai_result.get("status", "fail")
    feedback = ai_result.get("feedback", "No feedback generated.")
    interview = db.query(Interview).filter_by(applicant_id=applicant_id).first()
    if interview:
        interview.transcript = transcript
        interview.question_count = sum(1 for t in transcript if t.get("sender") == "AI")
        interview.completed_at = datetime.utcnow()
        interview.score = score
        interview.status = status
        interview.feedback = feedback
    else:
        interview = Interview(
            applicant_id=applicant_id,
            transcript=transcript,
            question_count=sum(1 for t in transcript if t.get("sender") == "AI"),
            completed_at=datetime.utcnow(),
            score=score,
            status=status,
            feedback=feedback
        )
        db.add(interview)

    db.commit()
    db.refresh(interview)

    return {
        "message": "Interview saved and evaluated by Gemini AI",
        "interview_id": interview.id,
        "score": score,
        "status": status,
        "feedback": feedback
    }



@interview_router.get("/interview-results/{applicant_id}")
async def get_applicant_interview_results(
    request: Request,
    applicant_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_recruiter:
        raise HTTPException(status_code=403, detail="Only recruiters can access this page")
    applicant = db.query(Applicant).filter(Applicant.id == applicant_id).first()
    if applicant.job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this applicant")
    
    if not applicant:
        raise HTTPException(status_code=404, detail="Applicant not found or unauthorized")
    
    interview = db.query(Interview).filter_by(applicant_id=applicant_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="No AI interview found for this applicant")

    return templates.TemplateResponse("recruiter_interview_results.html", {
        "request": request,
        "applicant": applicant,
        "interview": interview,
        "current_user": current_user
    })


@interview_router.post("/upload-job-interview-video")
async def upload_interview_video(
    video: UploadFile = File(...),
    applicant_id: str = Form(...),
    db:Session=Depends(get_db)
):
    try:
        upload_result = cloudinary.uploader.upload(
            video.file,
            resource_type="video",
            folder="interview_videos",
            public_id=f"interview_{applicant_id}{datetime.utcnow().timestamp()}",
            overwrite=True
        )
        video_url = upload_result.get("secure_url")
        attempt = db.query(Interview).filter(Interview.id == applicant_id).first()
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