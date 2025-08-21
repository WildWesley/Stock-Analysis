from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
import os
# We import our model here so that we can save information to the database of that form
from models import db, User

# NOTE: app.py is meant to configure Flask, initialize 
# the database, and create the tables

# Load and environment variables to be applied
load_dotenv()

# This gives us access to the login extension
login_manager = LoginManager()

def create_app():
    # EquiSight is my cool app name
    app = Flask("EquiSight")

    # Apply environment variables
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///site.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Initialize Flask extensions
    db.init_app(app)
    login_manager.init_app(app)

    # Where to send anonymous users
    login_manager.login_view = "login"
    # Flask category
    login_manager.login_message_category = "error" 

    # Create database
    with app.app_context():
        db.create_all()

    # Page routes
    # Home page
    @app.route("/")
    def home():
        return render_template("home.html")

    # Register page
    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            # Grab username and password
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            # Require both
            if not username or not password:
                flash("Username and password are required.", "error")
                return redirect(url_for("register"))
            
            # Check to see if it's a duplicate
            if User.query.filter_by(username=username).first():
                flash("That username is taken.", "error")
                return redirect(url_for("register"))
            
            # Add user to database
            user = User(username=username)
            # Apply hash to password and save as attribute
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            flash("Account created. Please log in.", "success")
            return redirect(url_for("login"))

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            remember = request.form.get("remember") == "on"

        if not username or not password:
            pass
            # NOTE: STOPPED HERE!
    
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)