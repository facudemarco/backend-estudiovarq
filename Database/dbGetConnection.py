import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()  

USER = os.getenv("USER")
PASSWORD = os.getenv("PASSWORD")
HOST = os.getenv("HOST")
PORT = os.getenv("PORT") or "3306"
DATABASE = os.getenv("DATABASE")

DATABASE_URL = f"mysql+pymysql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=280)