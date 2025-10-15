import uvicorn
from fastapi import FastAPI
from apps.auth.authentication import auth_router
from apps.dashboard.dashboard import dashboard_router
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apps.websocket.websocket_route import websocket_router
from apps.stt_tts.route import voice_router
from apps.PublicInterview.public_interview import public_interview_router
from apps.Interview.interview import interview_router
from starlette.middleware.sessions import SessionMiddleware
from config import SECRET_KEY


app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


app.include_router(websocket_router)
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(voice_router)
app.include_router(interview_router)
app.include_router(public_interview_router)

if __name__ == '__main__':
    uvicorn.run(
        app,
        port=8000,
        host="0.0.0.0",
        reload=True
       )