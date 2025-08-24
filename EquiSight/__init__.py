from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
import os
# We import our model here so that we can save information to the database of that form
from EquiSight.models import db, User, Prediction
import EquiSight.models
# We import our scraping script to run in the background with multithreading
from EquiSight.scraping_scripts.stock_invest_selenium import run_script
from threading import Thread


# NOTE: app.py is meant to configure Flask, initialize 
# the database, and create the tables

# Load and environment variables to be applied
load_dotenv()

# This gives us access to the login extension
login_manager = LoginManager()

def create_app():
    # EquiSight is my cool app name
    app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "static")
    )

    # Apply environment variables
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///instance/site.db")
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

    # Define background scraper function
    def start_scraper():
        with app.app_context():
            run_script()

    # daemon=True will set the thread to end when flask is closed
    Thread(target=start_scraper, daemon=True).start()

    # Page routes
    # Home page
    @app.route("/")
    def home():
        return render_template("main/home.html")

    @login_manager.user_loader
    def load_user(user_id):
        return models.User.query.get(int(user_id))

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

        return render_template("auth/register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            remember = request.form.get("remember") == "on"

            user = User.query.filter_by(username=username).first()
            if not user or not user.check_password(password):
                flash("Invalid username or password.", "error")
                return redirect(url_for("login"))
            
            login_user(user, remember=remember)
            flash("Logged in.", "success")
            return redirect(url_for("dashboard"))
        
        return render_template("auth/login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user() # Imported function that logs user out
        flash("Logged out.", "success")
        return redirect(url_for("home"))
    
    @app.route("/dashboard")
    @login_required
    def dashboard():
        # Sample dashboard template that injects current user info to customize
        return render_template("main/dashboard.html", user=current_user)

    @app.route("/predictions")
    @login_required
    def predictions():
        # Query the stock data needed from the database, take the user to a predictions page showing predictions and graphs (eventually)
        current_predictions = Prediction.query.order_by(Prediction.ticker).all()
        return render_template("main/predictions.html", results=current_predictions)

    return app