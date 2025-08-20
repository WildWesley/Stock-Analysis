from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
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

# Stock predictions table (Note the required syntax to set these attributes to the table)
class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    price = db.Column(db.Float, nullable=True)
    confidence = db.Column(db.Float, nullable=True)
    scraped_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))