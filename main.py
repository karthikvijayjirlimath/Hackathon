import os
import re
import logging
from typing import List, Dict, Any, Tuple, Optional
from flask import Flask, render_template, request, flash, redirect, url_for, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email
from flask_wtf import FlaskForm
from dotenv import load_dotenv
from extractionLogic import BillExtractor, ReportExtractor, PersonalExtractor

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallback-secret-key-for-dev")

# Security
csrf = CSRFProtect(app)

# Use HTTPS only in production as per guidelines
is_prod = os.environ.get('FLASK_ENV') == 'production'
Talisman(
    app, 
    content_security_policy=None, 
    force_https=is_prod
)  # Basic security headers, CSP disabled for simplicity in this demo

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configure folders
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
REPORTS_FOLDER = os.environ.get('REPORTS_FOLDER', 'reports')
BILLINGS_FOLDER = os.environ.get('BILLINGS_FOLDER', 'billings')
PERSONAL_FOLDER = os.environ.get('PERSONAL_FOLDER', 'personal_data')
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['REPORTS_FOLDER'] = REPORTS_FOLDER
app.config['BILLINGS_FOLDER'] = BILLINGS_FOLDER
app.config['PERSONAL_FOLDER'] = PERSONAL_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Create the directory if it doesn't exist
for folder in [UPLOAD_FOLDER, REPORTS_FOLDER, BILLINGS_FOLDER, PERSONAL_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Initialize Extractors
bill_extractor = BillExtractor(UPLOAD_FOLDER)
report_extractor = ReportExtractor()
personal_extractor = PersonalExtractor()

# User model for testing
class User(UserMixin):
    def __init__(self, id, email, password):
        self.id = id
        self.email = email
        self.password = password

# Mock user database
users = {
    "1": User("1", "provider@example.com", generate_password_hash("password123"))
}

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id)

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

def allowed_file(filename: str) -> bool:
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    logger.error(f"Internal Server Error: {e}")
    return render_template('500.html'), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('upload_file'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = next((u for u in users.values() if u.email == form.email.data), None)
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('upload_file'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'warning')
    
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
@login_required
def upload_file():
    if request.method == 'POST':
        # Check which files were uploaded
        upload_types = {
            'bill_files': (bill_extractor, 'Bill'),
            'report_files': (report_extractor, 'Clinical Report'),
            'personal_files': (personal_extractor, 'Personal Record')
        }
        
        # Initialize session results if not present
        if 'extracted_results' not in session:
            session['extracted_results'] = []
            
        new_results = []
        
        files_found = False
        for field_name, (extractor, type_label) in upload_types.items():
            if field_name in request.files:
                files = request.files.getlist(field_name)
                for file in files:
                    if file.filename == '':
                        continue
                    
                    files_found = True
                    if file and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(filepath)

                        # Process the PDF using appropriate extractor
                        data, error = extractor.process_pdf(filepath)
                        
                        if error:
                            if os.path.exists(filepath):
                                os.remove(filepath)
                            flash(f"Error processing {filename}: {error}")
                            continue

                        if data:
                            data['record_type'] = type_label
                            new_results.append(data)
        
        if not files_found:
            # Fallback for "Upload More" button which uses 'files' field
            if 'files' in request.files:
                files = request.files.getlist('files')
                for file in files:
                    if file.filename == '' or not (file and allowed_file(file.filename)):
                        continue
                    
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)

                    # For "Upload More", we try to detect or default to Bill
                    data, error = bill_extractor.process_pdf(filepath)
                    if data:
                        data['record_type'] = 'Bill'
                        new_results.append(data)
                    else:
                        flash(f"Could not automatically process {filename} as a bill.")

        timeline_events = []
        if new_results:
            # Append new results to session
            current_results = session.get('extracted_results', [])
            current_results.extend(new_results)
            session['extracted_results'] = current_results
            
            # Check if all results belong to the same patient
            patient_ids = {res.get('patient_id') for res in session['extracted_results'] if res.get('patient_id') != 'N/A'}
            if len(patient_ids) > 1:
                flash("Multiple patient records detected. Displaying all records.")
            
            if patient_ids:
                # Use the first patient ID found to generate a timeline
                primary_patient_id = list(patient_ids)[0]
                
                # Scan billings
                if os.path.exists(app.config['BILLINGS_FOLDER']):
                    for filename in os.listdir(app.config['BILLINGS_FOLDER']):
                        if filename.endswith('.pdf'):
                            filepath = os.path.join(app.config['BILLINGS_FOLDER'], filename)
                            data, error = bill_extractor.process_pdf(filepath)
                            if data and data.get('patient_id') == primary_patient_id:
                                data['event_type'] = 'Billing'
                                timeline_events.append(data)
                            
                # Scan reports
                if os.path.exists(app.config['REPORTS_FOLDER']):
                    for filename in os.listdir(app.config['REPORTS_FOLDER']):
                        if filename.endswith('.pdf'):
                            filepath = os.path.join(app.config['REPORTS_FOLDER'], filename)
                            data, error = report_extractor.process_pdf(filepath)
                            if data and data.get('patient_id') == primary_patient_id:
                                data['event_type'] = 'Clinical Report'
                                timeline_events.append(data)
                            
                # Sort by date
                timeline_events.sort(key=lambda x: x.get('date', '0000-00-00'))
            
        return redirect(url_for('display_results'))

    # Clear all data when the index page is reloaded (GET request)
    session.pop('extracted_results', None)
    session.modified = True
    return render_template('index.html')

@app.route('/results')
@login_required
def display_results():
    if 'extracted_results' not in session:
        return redirect(url_for('upload_file'))
    return render_template('results.html', results=session['extracted_results'])

@app.route('/timeline/<patient_id>')
@login_required
def timeline(patient_id):
    timeline_events = []
    
    # Scan billings
    if os.path.exists(app.config['BILLINGS_FOLDER']):
        for filename in os.listdir(app.config['BILLINGS_FOLDER']):
            if filename.endswith('.pdf'):
                filepath = os.path.join(app.config['BILLINGS_FOLDER'], filename)
                data, error = bill_extractor.process_pdf(filepath)
                if data and data.get('patient_id') == patient_id:
                    data['event_type'] = 'Billing'
                    timeline_events.append(data)
                
    # Scan reports
    if os.path.exists(app.config['REPORTS_FOLDER']):
        for filename in os.listdir(app.config['REPORTS_FOLDER']):
            if filename.endswith('.pdf'):
                filepath = os.path.join(app.config['REPORTS_FOLDER'], filename)
                data, error = report_extractor.process_pdf(filepath)
                if data and data.get('patient_id') == patient_id:
                    data['event_type'] = 'Clinical Report'
                    timeline_events.append(data)
                
    # Sort by date
    timeline_events.sort(key=lambda x: x.get('date', '0000-00-00'))
    
    return render_template('timeline.html', patient_id=patient_id, events=timeline_events)

if __name__ == '__main__':
    # Never run with debug=True in production. 
    # Use environment variable to determine debug mode.
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug_mode, port=8124)