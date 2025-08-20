from flask import Flask
from dotenv import load_dotenv
import os
from models import db

# NOTE: app.py is meant to configure Flask, initialize 
# the database, and create the tables

# Load and environment variables to be applied
load_dotenv()

def create_app():
    # EquiSight is my cool app name
    app = Flask("EquiSight")

    # Apply environment variables
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///site.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Test
    @app.route("/")
    def home():
        return "Hello, Flask!"
    
    # Connect SQLAlchemy into Flask
    db.init_app(app)

    # Create the database tables
    with app.app_context():
        db.create_all()

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)