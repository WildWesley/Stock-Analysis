from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone

# NOTE: models.py is meant to define database structures

# This sets up the Object-Relational Mapper
# It is an interface between Python objects and
# the database (tables/rows)
db = SQLAlchemy()

# User table (Each instance is a website user, with column info being the different attributes)
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Now, we set methods to create and check password hashes in order to avoid storing raw passwords in the database
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Stock predictions table (Note the required syntax to set these attributes to the table)
class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(10), nullable=False)
    score = db.Column(db.Float, nullable=True)
    recommendation = db.Column(db.String(10), nullable=True)
    sector = db.Column(db.String(30), nullable=True)
    price = db.Column(db.Float, nullable=True)
    change_percent = db.Column(db.Float, nullable=True)
    scraped_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))