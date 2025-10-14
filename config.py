import os
from dotenv import load_dotenv
import cloudinary
from fastapi.templating import Jinja2Templates

load_dotenv()

templates = Jinja2Templates(directory="templates")

SECRET_KEY = os.getenv("SECRET_KEY") 

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY") 
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI")

cloudinary.config( 
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"), 
    api_key = os.getenv("CLOUDINARY_API_KEY"), 
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
)
