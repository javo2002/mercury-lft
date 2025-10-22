import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # API Keys
    API_KEY = os.getenv('API_KEY')
    API_SECRET = os.getenv('API_SECRET')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    
    # Environment
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    
    # Database
    POSTGRES_USER = os.getenv('POSTGRES_USER')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
    POSTGRES_DB = os.getenv('POSTGRES_DB')
    DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@db:5432/{POSTGRES_DB}"
    
    # Celery & Redis
    CELERY_BROKER_URL = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND = "redis://redis:6379/0"

settings = Settings()
