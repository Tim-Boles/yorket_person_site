import threading
from flask import Flask, render_template, flash, url_for, redirect, request
from flask_login import LoginManager, login_required, login_user, logout_user, current_user
from dotenv import load_dotenv
from urllib.parse import urlparse

import os
import io
import re
import pypdf

from extensions import db
from models import User, Sheet
from forms import LoginForm, RegisterForm

from google.cloud import storage

import discord_blueprint

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
# Configure the SQLite database URI with an absolute path
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "instance", "database.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False  # Optional: to suppress a warning
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

storage_client = storage.Client()
bucket_name = os.getenv("BUCKET_NAME")
bucket = storage_client.bucket(bucket_name)

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

app.register_blueprint(discord_blueprint.discord_bp, url_prefix="/discord/api")

def clean_text(text):
  """Removes citation tags like [cite: 123] from a string."""
  if not isinstance(text, str):
    return text
  # This regular expression finds and removes any text that starts with '[cite' and ends with ']'
  return re.sub(r'\[cite.*?\]', '', text).strip()

def load_pdf(blob_name):
    try:
        blob = bucket.blob(blob_name)
        pdf_file_object = io.BytesIO(blob.download_as_bytes())
    except Exception as e:
        print(f"Error loading PDF: {e}")
        return {"error": str(e), "status": "error"}
    return {"pdf_file_object": pdf_file_object, "status": "success"}

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user)
            next_content = request.args.get("next")
            if next_content and urlparse(next_content).netloc == '':
                return redirect(next_content)
            return redirect(url_for('coc')) 
        flash('Invalid email or password.')

    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(email=form.email.data,
                    username=form.username.data,
                    password=form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('You can now log in.')
        return redirect(url_for('login'))
        
    return render_template('register.html', form=form)

@app.route("/")
def index():
    return render_template("content.html", 
                           buttons = [  {"url": "home", "name": "Home"}, 
                                        {"url": "coc", "name": "Call of Cuthulhu"},
                                        {"url": "login", "name": "Login"}])

@app.route("/upload/<service>", methods=["GET", "POST"])
def upload(service):
    if(service == "coc"):
        pdf_file = request.files['pdf_file']
        blob = bucket.blob(f"{current_user.username}_sheet.pdf")
        blob.upload_from_file(pdf_file)
        return redirect(url_for('index'))
    elif(service == "test"):
        return render_template("upload.html", service={"NAME": "test"})
    return

@app.route("/coc")
@login_required
def coc():
    try:
        pdf = load_pdf(f"{current_user.username}_sheet.pdf")
        if pdf["status"] == "error":
            return render_template("upload.html", service={"NAME": "coc"})
        reader = pypdf.PdfReader(pdf["pdf_file_object"])
        form_fields = reader.get_form_text_fields()
    except FileNotFoundError:
        flash("The character sheet PDF could not be found.")
        return redirect(url_for('index'))

    character_data = {k: clean_text(v) for k, v in form_fields.items()}
    
    # --- Process Skills ---
    all_skills_data = {k: v for k, v in character_data.items() if k.startswith("Skill_")}
    formatted_skills = {}
    base_skill_keys = [k for k in all_skills_data.keys() if k.count('_') == 1 and all_skills_data.get(k)]
    for base_key in base_skill_keys:
        base_name = base_key.replace('Skill_', '')
        base_value = all_skills_data.get(base_key, '0')
        half_value = all_skills_data.get(f"{base_key}_half", '0')
        fifth_value = all_skills_data.get(f"{base_key}_fifth", '0')
        skill_name_display = re.sub(r'(?<!^)(?=[A-Z])', ' ', base_name)
        
        # Handle special named skills
        if "OwnLanguage" in base_name: skill_name_display = f"Language ({character_data.get('SkillDef_OwnLanguage', '')})"
        elif "OtherLanguage" in base_name: skill_name_display = f"Language ({character_data.get(f'SkillDef_{base_name}', '')})"
        elif "Science" in base_name: skill_name_display = f"Science ({character_data.get(f'SkillDef_{base_name}', '')})"
        elif "ArtCraft" in base_name: skill_name_display = f"Art/Craft ({character_data.get(f'SkillDef_{base_name}', '')})"
        
        formatted_skills[skill_name_display] = [base_value, half_value, fifth_value]
    sorted_skills = dict(sorted(formatted_skills.items()))

    # --- Process Weapons ---
    weapons = []
    # Handle Unarmed/Brawl which is weapon slot 0
    if character_data.get('Weapon_Regular0'):
        weapons.append({
            'name': 'Unarmed / Brawl',
            'regular': character_data.get('Weapon_Regular0'), 'hard': character_data.get('Weapon_Hard0'), 'extreme': character_data.get('Weapon_Extreme0'),
            'damage': f"1D3 + {character_data.get('DamageBonus', '0')}", 'range': 'Touch', 'attacks': '1', 'ammo': 'N/A', 'malf': 'N/A'
        })
    # Loop through numbered weapon slots
    for i in range(1, 4):
        if character_data.get(f'Weapon_Name{i}'):
            weapons.append({
                'name': character_data.get(f'Weapon_Name{i}'),
                'regular': character_data.get(f'Weapon_Regular{i}'), 'hard': character_data.get(f'Weapon_Hard{i}'), 'extreme': character_data.get(f'Weapon_Extreme{i}'),
                'damage': character_data.get(f'Weapon_Damage{i}'), 'range': character_data.get(f'Weapon_Range{i}'), 'attacks': character_data.get(f'Weapon_Attacks{i}'),
                'ammo': character_data.get(f'Weapon_Ammo{i}'), 'malf': character_data.get(f'Weapon_Malf{i}')
            })

    # --- Process Fellow Investigators ---
    investigators = []
    for i in range(1, 7):
        if character_data.get(f'Character_Name{i}'):
            investigators.append({
                'name': character_data.get(f'Character_Name{i}'),
                'player': character_data.get(f'Character_Player{i}')
            })

    return render_template("coc.html", 
                           sheet=character_data, 
                           skills=sorted_skills, 
                           weapons=weapons, 
                           investigators=investigators)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been successfully logged out.')
    return redirect(url_for('index')) 

if __name__ == "__main__":
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    bot_thread = threading.Thread(target=lambda: discord_blueprint.discord_bot.run(BOT_TOKEN))
    bot_thread.daemon = True # Allows main thread to exit even if this thread is running
    bot_thread.start()
    app.run(debug=True)