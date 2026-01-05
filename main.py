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
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, DateField
from wtforms.validators import DataRequired, Email, ValidationError
from datetime import date
from dotenv import load_dotenv
from extractionLogic import BillExtractor, ReportExtractor, PersonalExtractor
from azure_utils import AzureStorageHelper, AzureKeyVaultHelper
from cryptography.fernet import Fernet
from models import db, User, Patient, Provider, Payer, AuditLog, UserRole, Bill, BillStatus, ClinicalRecord, CPTCode, HCPCSCode, ICDCode
import json

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

# Database Configuration
# In production, use Azure SQL: mssql+pyodbc://<username>:<password>@<server>.database.windows.net/<db>?driver=ODBC+Driver+18+for+SQL+Server
DB_URL = os.environ.get('DATABASE_URL')
if not DB_URL:
    # Fallback to local SQLite for development
    DB_URL = "sqlite:///app.db"
    logger.warning("DATABASE_URL not found. Using local SQLite.")

app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Initialize Security Extensions
csrf = CSRFProtect(app)
talisman = Talisman(app, content_security_policy=None, force_https=False) # Disable force_https for local dev/testing

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
# For BillExtractor, we can optionally pass database-backed descriptions
def get_cpt_descriptions():
    try:
        with app.app_context():
            return {c.code: c.description for c in CPTCode.query.all()}
    except:
        return None

bill_extractor = BillExtractor(UPLOAD_FOLDER, cpt_descriptions=get_cpt_descriptions())
report_extractor = ReportExtractor()
personal_extractor = PersonalExtractor()

# User model with Role is now in models.py

def log_audit(action, resource_type=None, resource_id=None, details=None):
    try:
        audit = AuditLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
            details=details
        )
        db.session.add(audit)
        db.session.commit()
    except Exception as e:
        logger.error(f"Failed to log audit: {e}")
        db.session.rollback()

def enrich_medical_codes(data):
    """Enrich extracted data with descriptions from the database."""
    if 'cpt_codes' in data:
        for item in data['cpt_codes']:
            if item.get('desc') == 'Medical Procedure':
                code_obj = CPTCode.query.filter_by(code=item['code']).first()
                if code_obj:
                    item['desc'] = code_obj.description
    
    if 'hcpcs_codes' in data:
        for item in data['hcpcs_codes']:
            if item.get('desc') == 'Medical Supply/Service':
                code_obj = HCPCSCode.query.filter_by(code=item['code']).first()
                if code_obj:
                    item['desc'] = code_obj.description

    if 'diagnosis' in data and (not data.get('diagnosis_desc') or data.get('diagnosis_desc') == 'N/A'):
        code_obj = ICDCode.query.filter_by(code=data['diagnosis']).first()
        if code_obj:
            data['diagnosis_desc'] = code_obj.description
            
    if 'icd10' in data:
        code_obj = ICDCode.query.filter_by(code=data['icd10']).first()
        if code_obj:
            data['icd10_desc'] = code_obj.description

def save_extracted_data_to_db(data, type_label, filename):
    """Helper to save extracted bill/report info to database."""
    patient_id_ext = data.get('patient_id')
    if not patient_id_ext or patient_id_ext == 'N/A':
        return
    
    patient = Patient.query.filter_by(patient_external_id=patient_id_ext).first()
    if not patient:
        return

    from datetime import datetime
    if type_label == 'Bill':
        bill_date = None
        if data.get('date') and data.get('date') != 'N/A':
            try:
                bill_date = datetime.strptime(data.get('date'), '%Y-%m-%d').date()
            except: pass
        
        amount = 0.0
        try:
            amount_str = str(data.get('total_charges', '0')).replace('$', '').replace(',', '')
            amount = float(amount_str)
        except: pass
        
        bill = Bill(
            patient_id=patient.id,
            invoice_number=data.get('inv'),
            date=bill_date,
            amount=amount,
            status=BillStatus.PENDING, # Default to pending
            file_path=filename
        )
        db.session.add(bill)
        db.session.commit()
    elif type_label == 'Clinical Report':
        report_date = None
        if data.get('date') and data.get('date') != 'N/A':
            try:
                report_date = datetime.strptime(data.get('date'), '%Y-%m-%d').date()
            except: pass
            
        record = ClinicalRecord(
            patient_id=patient.id,
            record_type=type_label,
            date=report_date,
            summary=data.get('chief_complaint', 'N/A'),
            file_path=filename
        )
        db.session.add(record)
        db.session.commit()

def encrypt_data(data: str) -> str:
    if not data or data == 'N/A':
        return data
    return fernet.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    if not encrypted_data or encrypted_data == 'N/A':
        return encrypted_data
    try:
        return fernet.decrypt(encrypted_data.encode()).decode()
    except Exception:
        return encrypted_data

# Manual Patient Entry Form
class ManualPatientForm(FlaskForm):
    name = StringField('Patient Name', validators=[DataRequired()])
    dob = DateField('Date of Birth', validators=[DataRequired()], format='%Y-%m-%d')
    insurance_policy_id = StringField('Insurance Policy ID', validators=[DataRequired()])
    email = StringField('Email ID', validators=[Email()])
    refund_bank_account_id = StringField('Refund Bank Account ID')
    submit = SubmitField('Register Patient')

    def validate_dob(self, dob):
        if dob.data > date.today():
            raise ValidationError('Date of Birth cannot be in the future.')

# User loaders and forms
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

def allowed_file(filename: str) -> bool:
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/logout')
def logout():
    if current_user.is_authenticated:
        log_audit('LOGOUT')
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
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            log_audit('LOGIN', details=f"User {user.email} logged in")
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            log_audit('LOGIN_FAILED', details=f"Failed login attempt for {form.email.data}")
            flash('Login Unsuccessful. Please check email and password', 'warning')
    
    return render_template('login.html', form=form)

@app.route('/')
@login_required
def dashboard():
    if current_user.role == UserRole.PROVIDER:
        return redirect(url_for('provider_dashboard'))
    elif current_user.role == UserRole.PATIENT:
        return redirect(url_for('patient_dashboard'))
    elif current_user.role == UserRole.PAYER:
        return redirect(url_for('payer_dashboard'))
    return redirect(url_for('logout'))

@app.route('/provider', methods=['GET', 'POST'])
@login_required
def provider_dashboard():
    if current_user.role != UserRole.PROVIDER:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    
    # Handle auto-filling if data was extracted in the session
    autofill_data = {}
    if 'extracted_results' in session:
        for result in session['extracted_results']:
            if result.get('record_type') == 'Personal Record':
                # Convert DOB string to date object for DateField
                dob_str = result.get('dob')
                dob_obj = None
                if dob_str and dob_str != 'N/A':
                    try:
                        from datetime import datetime
                        dob_obj = datetime.strptime(dob_str, '%Y-%m-%d').date()
                    except ValueError:
                        pass
                
                autofill_data.update({
                    'name': result.get('name'),
                    'dob': dob_obj,
                    'insurance_policy_id': result.get('policy_id'),
                    'email': result.get('email')
                })
                break
    
    form = ManualPatientForm(data=autofill_data) if autofill_data else ManualPatientForm()
    if form.validate_on_submit():
        # Assign a random patient ID
        import random
        patient_id = f"P{random.randint(5000, 9999)}"
        
        # Create new User for patient if not exists
        patient_email = form.email.data
        existing_user = User.query.filter_by(email=patient_email).first()
        if not existing_user:
            new_user = User(
                email=patient_email,
                password_hash=generate_password_hash("temporary-password"), # Should be handled better in prod
                role=UserRole.PATIENT,
                name=form.name.data
            )
            db.session.add(new_user)
            db.session.flush() # Get user id
            
            patient = Patient(
                user_id=new_user.id,
                patient_external_id=patient_id,
                dob_encrypted=encrypt_data(form.dob.data.strftime('%Y-%m-%d')),
                insurance_policy_id=form.insurance_policy_id.data,
                refund_bank_account_encrypted=encrypt_data(form.refund_bank_account_id.data)
            )
            db.session.add(patient)
            db.session.commit()
            log_audit('REGISTER_PATIENT', 'PATIENT', patient_id, details=f"Registered patient {form.name.data}")
        else:
            flash('A user with this email already exists', 'warning')
            return redirect(url_for('provider_dashboard'))

        patient_data = {
            'patient_id': patient_id,
            'name': encrypt_data(form.name.data),
            'dob': encrypt_data(form.dob.data.strftime('%Y-%m-%d')),
            'insurance_policy_id': form.insurance_policy_id.data,
            'email': encrypt_data(form.email.data),
            'refund_bank_account_id': encrypt_data(form.refund_bank_account_id.data),
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
    
    # Fetch only a few patients for the dashboard summary if needed, or just remove
    # patients = Patient.query.limit(5).all()
    return render_template('index.html', form=form)

@app.route('/provider/patients')
@login_required
def provider_patients_list():
    if current_user.role != UserRole.PROVIDER:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    
    patients = Patient.query.all()
    log_audit('VIEW_PATIENT_LIST')
    return render_template('patients_list.html', patients=patients)

@app.route('/provider/patient/<patient_id>')
@login_required
def provider_patient_detail(patient_id):
    if current_user.role != UserRole.PROVIDER:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    
    patient = Patient.query.filter_by(patient_external_id=patient_id).first_or_404()
    
    log_audit('VIEW_PATIENT_DETAIL', 'PATIENT', patient_id)
    
    return render_template('patient_detail.html', patient=patient, decrypt_data=decrypt_data, is_patient_view=False)

@app.route('/patient')
@login_required
def patient_dashboard():
    if current_user.role != UserRole.PATIENT:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    
    patient = current_user.patient_profile
    patient_data = {
        'name': current_user.name,
        'dob': decrypt_data(patient.dob_encrypted) if patient else 'N/A',
        'patient_id': patient.patient_external_id if patient else 'N/A',
        'insurance_status': 'Verified' if patient and patient.insurance_policy_id else 'Pending',
        'email': current_user.email
    }
    
    log_audit('VIEW_DASHBOARD', 'PATIENT_PROFILE', patient_data['patient_id'])

    notifications = [
        {'title': 'Welcome', 'message': f'Welcome to EmilY, {patient_data["name"]}.'},
        {'title': 'Profile Complete', 'message': 'Your personal record has been successfully processed.'}
    ]
    
    return render_template('patient_dashboard.html', patient=patient_data, notifications=notifications)

@app.route('/patient/history')
@login_required
def patient_history():
    if current_user.role != UserRole.PATIENT:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    
    patient = current_user.patient_profile
    if not patient:
        flash('Patient profile not found', 'warning')
        return redirect(url_for('patient_dashboard'))
    
    log_audit('VIEW_MY_HISTORY', 'PATIENT', patient.patient_external_id)
    
    return render_template('patient_detail.html', patient=patient, decrypt_data=decrypt_data, is_patient_view=True)

@app.route('/payer')
@login_required
def payer_dashboard():
    if current_user.role != UserRole.PAYER:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    
    log_audit('VIEW_DASHBOARD', 'PAYER_PORTAL')

    # Fetch all patients for payer
    patients = Patient.query.all()
    records = []
    for p in patients:
        records.append({
            'id': p.patient_external_id,
            'name': p.user.name,
            'status': 'verified' if p.insurance_policy_id else 'pending',
            'records_count': 0 # Would normally count related bills/reports
        })

    # Mock fallback if empty
    if not records:
        records = [
            {'id': 'P2002', 'name': 'John Doe', 'status': 'partial', 'records_count': 5},
            {'id': 'P3005', 'name': 'Jane Smith', 'status': 'complete', 'records_count': 3}
        ]
    return render_template('payer_dashboard.html', records=records)

@app.route('/provider/upload', methods=['POST'])
@login_required
def upload_file():
    if current_user.role != UserRole.PROVIDER:
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
                            enrich_medical_codes(data)
                            log_audit('UPLOAD_FILE', type_label, filename)
                            # Save to Database
                            save_extracted_data_to_db(data, type_label, filename)
                            
                            # Store only necessary info to session to avoid large cookie warnings
                            minimal_data = {
                                'patient': encrypt_data(data.get('patient') or data.get('name')),
                                'patient_id': data.get('patient_id'),
                                'insurance_id': encrypt_data(data.get('insurance_id') or data.get('policy_id')),
                                'record_type': type_label,
                                'date': data.get('date') or data.get('dob') or 'N/A'
                            }
                            # Include other key fields but limit text length if needed
                            for key in ['inv', 'total_charges', 'amount_due', 'icd10', 'chief_complaint']:
                                if key in data:
                                    val = data[key]
                                    if isinstance(val, str) and len(val) > 100:
                                        val = val[:97] + "..."
                                    minimal_data[key] = val
                            
                            new_results.append(minimal_data)
        
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
                        enrich_medical_codes(data)
                        # Save to Database
                        save_extracted_data_to_db(data, 'Bill', filename)
                        
                        # Store only necessary info to session to avoid large cookie warnings
                        minimal_data = {
                            'patient': encrypt_data(data.get('patient')),
                            'patient_id': data.get('patient_id'),
                            'insurance_id': encrypt_data(data.get('insurance_id')),
                            'record_type': 'Bill',
                            'date': data.get('date', 'N/A'),
                            'inv': data.get('inv', 'N/A'),
                            'total_charges': data.get('total_charges', '0.00'),
                            'amount_due': data.get('amount_due', '0.00')
                        }
                        new_results.append(minimal_data)
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
        dec_res['patient'] = decrypt_data(res.get('patient'))
        dec_res['insurance_id'] = decrypt_data(res.get('insurance_id'))
        decrypted_results.append(dec_res)
        
    return render_template('results.html', results=decrypted_results)

@app.route('/timeline/<patient_id>')
@login_required
def timeline(patient_id):
    # RBAC: Patients can only see their own timeline, Providers can see all
    if current_user.role == UserRole.PATIENT:
        if not current_user.patient_profile or current_user.patient_profile.patient_external_id != patient_id:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('dashboard'))
    elif current_user.role != UserRole.PROVIDER:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))

    patient = Patient.query.filter_by(patient_external_id=patient_id).first_or_404()
    timeline_events = []
    
    # Use database to find relevant files instead of scanning whole directories
    # This is more efficient and secure
    
    # Process Bills
    for bill in patient.bills:
        if bill.file_path:
            # Check multiple possible locations for the file
            filepath = None
            for folder in [app.config['BILLINGS_FOLDER'], app.config['UPLOAD_FOLDER']]:
                possible_path = os.path.join(folder, bill.file_path)
                if os.path.exists(possible_path):
                    filepath = possible_path
                    break
            
            if filepath:
                data, error = bill_extractor.process_pdf(filepath)
                if data:
                    data['event_type'] = 'Billing'
                    timeline_events.append(data)
                
    # Process Clinical Records
    for record in patient.clinical_records:
        if record.file_path:
            filepath = None
            for folder in [app.config['REPORTS_FOLDER'], app.config['UPLOAD_FOLDER']]:
                possible_path = os.path.join(folder, record.file_path)
                if os.path.exists(possible_path):
                    filepath = possible_path
                    break
                    
            if filepath:
                data, error = report_extractor.process_pdf(filepath)
                if data:
                    data['event_type'] = 'Clinical Report'
                    timeline_events.append(data)
                
    # Sort by date
    timeline_events.sort(key=lambda x: x.get('date', '0000-00-00'))
    
    # Decrypt sensitive data for display
    for event in timeline_events:
        event['patient'] = decrypt_data(event.get('patient'))
        event['insurance_id'] = decrypt_data(event.get('insurance_id'))
        
    log_audit('VIEW_TIMELINE', 'PATIENT', patient_id)
    is_patient_view = (current_user.role == UserRole.PATIENT)
    return render_template('timeline.html', patient_id=patient_id, patient_name=patient.user.name, events=timeline_events, is_patient_view=is_patient_view)

if __name__ == '__main__':
    # Never run with debug=True in production. 
    # Use environment variable to determine debug mode.
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug_mode, port=8124)