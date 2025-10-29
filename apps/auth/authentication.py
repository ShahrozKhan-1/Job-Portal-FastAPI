from fastapi import APIRouter, Depends, Request, HTTPException, Response, Query, Body
from fastapi.staticfiles import StaticFiles
from database.models import User
from database.schema import AddUser, LoginUser, UserResponse
from database.database import get_db
from sqlalchemy.orm import Session
from apps.auth.utils import get_password_hash, create_access_token, verify_password, ACCESS_TOKEN_EXPIRY_MINUTES
from datetime import timedelta
from fastapi.responses import JSONResponse, RedirectResponse
from config import templates



auth_router = APIRouter()
auth_router.mount("/static", StaticFiles(directory="static"), name="static")


@auth_router.get("/register")
async def get_register(request: Request):
    return templates.TemplateResponse("register.html", {"request":request})


@auth_router.post("/register", response_model=UserResponse)
async def post_registration(
    user: AddUser, 
    db: Session = Depends(get_db),
    ):
    existed_user = db.query(User).filter_by(email=user.email).first()
    if existed_user:
        return JSONResponse(status_code=400, content={"error":"User already exists!"})
    new_user = User(
        name=user.name,
        email=user.email,
        password=get_password_hash(user.password),
        is_recruiter=user.is_recruiter
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return RedirectResponse(url="/login", headers={"success":"User Registered Successfully"}, status_code=302)


@auth_router.get("/login")
async def get_login(request: Request, next: str = Query(None)):
    return templates.TemplateResponse("login.html", {"request": request, "next":next})



@auth_router.post("/login")
async def post_login(
    user: LoginUser = Body(...),  # <-- ensure JSON body is parsed
    db: Session = Depends(get_db),
):
    existed_user = db.query(User).filter_by(email=user.email).first()
    if not existed_user:
        return JSONResponse(status_code=400, content={"error": "User not registered"})
    
    if not verify_password(user.password, existed_user.password):
        return JSONResponse(status_code=400, content={"error": "Incorrect Password"})
    
    access_token = create_access_token(
        data={"sub": existed_user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRY_MINUTES)
    )
    print("=====", user.next)
    next_url = user.next or "/dashboard"
    
    response = JSONResponse({"success": True, "next": next_url})
    response.set_cookie(key="access_token", value=access_token, httponly=True)
    return response



@auth_router.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    return response

