import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "I am patient 0")
    SECURITY_PASSWORD_SALT = os.environ.get("SECURIY_PASWORD_SALT", "dev-salt")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    AQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session/cookie hardening
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"

    # CSRF settings
    WTF_CSRF_TIME_LIMIT = None
    