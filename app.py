from flask import Flask, render_template, flash, url_for, redirect
from flask_login import LoginManager, login_required, login_user, logout_user
from dotenv import load_dotenv
from rcon.source import Client
import os

from extensions import db
from models import User
from forms import LoginForm, RegisterForm

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))

PZ_HOST = os.getenv("PZ_HOST")
PZ_RCON_PORT = int(os.getenv("PZ_RCON_PORT"))
PZ_RCON_PASSWORD = os.getenv("PZ_RCON_PASSWORD")

def get_player_count():
    """Connects to the server via RCON and gets the player count."""
    try:
        with Client(PZ_HOST, PZ_RCON_PORT, passwd=PZ_RCON_PASSWORD) as client:
            response = client.run('players')
            # The 'players' command returns a string.
            # We filter out empty lines and the header to get an accurate count.
            players = [line for line in response.split('\n') if line.strip() and "name" not in line]
            return len(players)
    except Exception as e:
        # This will catch connection errors, auth failures, etc.
        print(f"Error connecting to RCON: {e}")
        return "Offline"

app = Flask(__name__)
# Configure the SQLite database URI with an absolute path
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "instance", "database.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False  # Optional: to suppress a warning
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

# Create the instance folder if it doesn't exist
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

db.init_app(app)

with app.app_context():
    db.create_all()

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        # The form's custom validate() method handles the checks
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user)
            # Redirect to the main page or a dashboard after login
            return redirect(url_for('projects')) 
        flash('Invalid email or password.')

    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(email=form.email.data,
                    username=form.username.data,
                    password=form.password.data) # Your User model should hash the password
        db.session.add(user)
        db.session.commit()
        flash('You can now log in.')
        return redirect(url_for('login'))
        
    return render_template('register.html', form=form)

@app.route("/")
def index():
    return render_template("index.html")

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been successfully logged out.')
    return redirect(url_for('index')) 

@app.route("/projects")
@login_required
def projects():
    return render_template("projects.html")

@app.route("/server-stats")
@login_required
def server_stats():
    """Endpoint that HTMX will call to get the player count."""
    player_count = get_player_count()
    # This endpoint returns an HTML fragment directly.
    return f"""
    <span class="player-count good">{player_count}</span>
    """

if __name__ == "__main__":
    app.run(debug=True)