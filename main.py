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
from azure_utils import AzureStorageHelper, AzureKeyVaultHelper
from cryptography.fernet import Fernet

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

# Load environment variables
load_dotenv()

# Initialize Azure Helpers
kv_helper = AzureKeyVaultHelper()
storage_helper = AzureStorageHelper()

# Get Secret Key from Key Vault if available
SECRET_KEY = kv_helper.get_secret("SECRET-KEY") or os.environ.get("SECRET_KEY", "fallback-secret-key-for-dev")
ENCRYPTION_KEY = kv_helper.get_secret("ENCRYPTION-KEY") or os.environ.get("ENCRYPTION_KEY")

if not ENCRYPTION_KEY:
    # Generate a key for demo purposes if not found, in production this should be in Key Vault
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    logger.warning("ENCRYPTION_KEY not found in environment or Key Vault. Generated a temporary key.")

fernet = Fernet(ENCRYPTION_KEY.encode())

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Initialize Security Extensions
csrf = CSRFProtect(app)
talisman = Talisman(app, content_security_policy=None) # Disable CSP for now to avoid breaking existing external assets

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

# User model with Role
class User(UserMixin):
    def __init__(self, id, email, password, role, name=None):
        self.id = id
        self.email = email
        self.password = password
        self.role = role
        self.name = name

    def encrypt_data(self, data: str) -> str:
        if not data or data == 'N/A':
            return data
        return fernet.encrypt(data.encode()).decode()

    def decrypt_data(self, encrypted_data: str) -> str:
        if not encrypted_data or encrypted_data == 'N/A':
            return encrypted_data
        try:
            return fernet.decrypt(encrypted_data.encode()).decode()
        except Exception:
            return encrypted_data

# Manual Patient Entry Form
class ManualPatientForm(FlaskForm):
    name = StringField('Patient Name', validators=[DataRequired()])
    dob = StringField('Date of Birth', validators=[DataRequired()])
    insurance_policy_id = StringField('Insurance Policy ID', validators=[DataRequired()])
    email = StringField('Email ID', validators=[Email()])
    refund_bank_account_id = StringField('Refund Bank Account ID')
    submit = SubmitField('Register Patient')

# Mock user database
users = {
    "1": User("1", "provider@example.com", generate_password_hash("password123"), "Provider", "Dr. Smith"),
    "2": User("2", "patient@example.com", generate_password_hash("password123"), "Patient", "John Doe"),
    "3": User("3", "payer@example.com", generate_password_hash("password123"), "Payer", "Aetna Claims")
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

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

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
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = next((u for u in users.values() if u.email == form.email.data), None)
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'warning')
    
    return render_template('login.html', form=form)

@app.route('/')
@login_required
def dashboard():
    if current_user.role == 'Provider':
        return redirect(url_for('provider_dashboard'))
    elif current_user.role == 'Patient':
        return redirect(url_for('patient_dashboard'))
    elif current_user.role == 'Payer':
        return redirect(url_for('payer_dashboard'))
    return redirect(url_for('logout'))

@app.route('/provider', methods=['GET', 'POST'])
@login_required
def provider_dashboard():
    if current_user.role != 'Provider':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    
    # Handle auto-filling if data was extracted in the session
    autofill_data = {}
    if 'extracted_results' in session:
        for result in session['extracted_results']:
            if result.get('record_type') == 'Personal Record':
                autofill_data.update({
                    'name': result.get('name'),
                    'dob': result.get('dob'),
                    'insurance_policy_id': result.get('policy_id'),
                    'email': result.get('email')
                })
                break
    
    form = ManualPatientForm(data=autofill_data) if autofill_data else ManualPatientForm()
    if form.validate_on_submit():
        # Assign a random patient ID
        import random
        patient_id = f"P{random.randint(5000, 9999)}"
        
        patient_data = {
            'patient_id': patient_id,
            'name': current_user.encrypt_data(form.name.data),
            'dob': current_user.encrypt_data(form.dob.data),
            'insurance_policy_id': form.insurance_policy_id.data,
            'email': current_user.encrypt_data(form.email.data),
            'refund_bank_account_id': current_user.encrypt_data(form.refund_bank_account_id.data),
            'registration_date': '2025-12-31'
        }
        
        # Save to local for now, but also upload to Azure Blob
        import json
        filename = f"{patient_id}_info.json"
        filepath = os.path.join(app.config['PERSONAL_FOLDER'], filename)
        with open(filepath, 'w') as f:
            json.dump(patient_data, f)
        
        # Upload to Azure
        with open(filepath, 'rb') as f:
            storage_helper.upload_blob('personal-data', filename, f.read())

        flash(f'Patient {form.name.data} registered successfully with ID: {patient_id}. Data encrypted and stored in Azure.', 'success')
        # Clear extraction session after manual registration
        session.pop('extracted_results', None)
        return redirect(url_for('provider_dashboard'))
    
    return render_template('index.html', form=form)

@app.route('/patient')
@login_required
def patient_dashboard():
    if current_user.role != 'Patient':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    
    # Try to find patient details in personal_data folder
    patient_data = {
        'name': 'Unknown',
        'dob': 'N/A',
        'patient_id': 'N/A',
        'insurance_status': 'Pending',
        'email': current_user.email
    }
    
    # Mock data for demonstration if no file found
    if current_user.email == 'patient@example.com':
        patient_data.update({
            'name': 'John Doe',
            'dob': '1985-05-20',
            'patient_id': 'P2002',
            'insurance_status': 'Partial'
        })

    notifications = [
        {'title': 'Welcome', 'message': f'Welcome to EmilY, {patient_data["name"]}.'},
        {'title': 'Profile Complete', 'message': 'Your personal record has been successfully processed.'}
    ]
    
    return render_template('patient_dashboard.html', patient=patient_data, notifications=notifications)

@app.route('/payer')
@login_required
def payer_dashboard():
    if current_user.role != 'Payer':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    
    # Mock list of patient records for payer
    records = [
        {'id': 'P2002', 'name': 'John Doe', 'status': 'partial', 'records_count': 5},
        {'id': 'P3005', 'name': 'Jane Smith', 'status': 'complete', 'records_count': 3},
        {'id': 'P4010', 'name': 'Robert Brown', 'status': 'pending', 'records_count': 1}
    ]
    return render_template('payer_dashboard.html', records=records)

@app.route('/provider/upload', methods=['POST'])
@login_required
def upload_file():
    if current_user.role != 'Provider':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
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
                        
                        # Upload to Azure
                        with open(filepath, 'rb') as f:
                            storage_helper.upload_blob('uploads', filename, f.read())

                        # Process the PDF using appropriate extractor
                        data, error = extractor.process_pdf(filepath)
                        
                        if data:
                            # Encrypt sensitive extracted data before saving to session/further use
                            data['patient'] = current_user.encrypt_data(data.get('patient'))
                            data['patient_id'] = data.get('patient_id') # Usually ID is kept searchable/indexed but can be encrypted too
                            data['insurance_id'] = current_user.encrypt_data(data.get('insurance_id'))
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
                    
                    # Upload to Azure
                    with open(filepath, 'rb') as f:
                        storage_helper.upload_blob('uploads', filename, f.read())

                    # For "Upload More", we try to detect or default to Bill
                    data, error = bill_extractor.process_pdf(filepath)
                    if data:
                        # Encrypt sensitive extracted data
                        data['patient'] = current_user.encrypt_data(data.get('patient'))
                        data['insurance_id'] = current_user.encrypt_data(data.get('insurance_id'))
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
        
        # After processing, we might want to stay on the dashboard for the provider 
        # but the current logic redirects to results. Let's keep it consistent.
        # But for Auto-fill we need to stay on the provider dashboard.
        if any(res.get('record_type') == 'Personal Record' for res in new_results):
            return redirect(url_for('provider_dashboard'))
            
        return redirect(url_for('display_results'))

    # Clear all data when the index page is reloaded (GET request)
    session.pop('extracted_results', None)
    session.modified = True
    return redirect(url_for('provider_dashboard'))

@app.route('/results')
@login_required
def display_results():
    if 'extracted_results' not in session:
        return redirect(url_for('upload_file'))
    
    results = session.get('extracted_results', [])
    # Decrypt sensitive data for display
    decrypted_results = []
    for res in results:
        dec_res = res.copy()
        dec_res['patient'] = current_user.decrypt_data(res.get('patient'))
        dec_res['insurance_id'] = current_user.decrypt_data(res.get('insurance_id'))
        decrypted_results.append(dec_res)
        
    return render_template('results.html', results=decrypted_results)

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
    
    # Decrypt sensitive data for display
    for event in timeline_events:
        event['patient'] = current_user.decrypt_data(event.get('patient'))
        event['insurance_id'] = current_user.decrypt_data(event.get('insurance_id'))
        
    return render_template('timeline.html', patient_id=patient_id, events=timeline_events)

if __name__ == '__main__':
    # Never run with debug=True in production. 
    # Use environment variable to determine debug mode.
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug_mode, port=8124)