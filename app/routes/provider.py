import os
import random
import json
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from app.models import db, User, Patient, UserRole, Bill, BillStatus, ClinicalRecord
from app.forms import ManualPatientForm
from app.services.audit import log_audit
from app.utils.crypto import encrypt_data, decrypt_data
from app.utils.azure import AzureStorageHelper
from app.services.extraction import BillExtractor, ReportExtractor, PersonalExtractor
from app.routes.main import enrich_medical_codes, get_cpt_descriptions

provider_bp = Blueprint('provider', __name__)

def allowed_file(filename: str):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def save_extracted_data_to_db(data, type_label, filename):
    """Helper to save extracted bill/report info to database."""
    patient_id_ext = data.get('patient_id')
    if not patient_id_ext or patient_id_ext == 'N/A':
        return
    
    patient = Patient.query.filter_by(patient_external_id=patient_id_ext).first()
    if not patient:
        return

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
            status=BillStatus.PENDING,
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

@provider_bp.route('/provider', methods=['GET', 'POST'])
@login_required
def provider_dashboard():
    if current_user.role != UserRole.PROVIDER:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.dashboard'))
    
    autofill_data = {}
    if 'extracted_results' in session:
        for result in session['extracted_results']:
            if result.get('record_type') == 'Personal Record':
                dob_str = result.get('date') # in session it was saved as 'date'
                dob_obj = None
                if dob_str and dob_str != 'N/A':
                    try:
                        dob_obj = datetime.strptime(dob_str, '%Y-%m-%d').date()
                    except ValueError:
                        pass
                
                autofill_data.update({
                    'name': decrypt_data(result.get('patient')),
                    'dob': dob_obj,
                    'insurance_policy_id': decrypt_data(result.get('insurance_id')),
                    'email': result.get('email')
                })
                break
    
    form = ManualPatientForm(data=autofill_data) if autofill_data else ManualPatientForm()
    if form.validate_on_submit():
        patient_id = f"P{random.randint(5000, 9999)}"
        patient_email = form.email.data
        existing_user = User.query.filter_by(email=patient_email).first()
        if not existing_user:
            new_user = User(
                email=patient_email,
                password_hash=generate_password_hash("temporary-password"),
                role=UserRole.PATIENT,
                name=form.name.data
            )
            db.session.add(new_user)
            db.session.flush()
            
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
            return redirect(url_for('provider.provider_dashboard'))

        patient_data = {
            'patient_id': patient_id,
            'name': encrypt_data(form.name.data),
            'dob': encrypt_data(form.dob.data.strftime('%Y-%m-%d')),
            'insurance_policy_id': form.insurance_policy_id.data,
            'email': encrypt_data(form.email.data),
            'refund_bank_account_id': encrypt_data(form.refund_bank_account_id.data),
            'registration_date': datetime.now().strftime('%Y-%m-%d')
        }
        
        filename = f"{patient_id}_info.json"
        filepath = os.path.join(current_app.config['PERSONAL_FOLDER'], filename)
        with open(filepath, 'w') as f:
            json.dump(patient_data, f)
        
        storage_helper = AzureStorageHelper()
        with open(filepath, 'rb') as f:
            storage_helper.upload_blob('personal-data', filename, f.read())

        flash(f'Patient {form.name.data} registered successfully with ID: {patient_id}.', 'success')
        session.pop('extracted_results', None)
        return redirect(url_for('provider.provider_dashboard'))
    
    return render_template('index.html', form=form)

@provider_bp.route('/provider/patients')
@login_required
def provider_patients_list():
    if current_user.role != UserRole.PROVIDER:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.dashboard'))
    
    patients = Patient.query.all()
    log_audit('VIEW_PATIENT_LIST')
    return render_template('patients_list.html', patients=patients)

@provider_bp.route('/provider/patient/<patient_id>')
@login_required
def provider_patient_detail(patient_id):
    if current_user.role != UserRole.PROVIDER:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.dashboard'))
    
    patient = Patient.query.filter_by(patient_external_id=patient_id).first_or_404()
    log_audit('VIEW_PATIENT_DETAIL', 'PATIENT', patient_id)
    return render_template('patient_detail.html', patient=patient, decrypt_data=decrypt_data)

@provider_bp.route('/provider/upload', methods=['POST'])
@login_required
def upload_file():
    if current_user.role != UserRole.PROVIDER:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.dashboard'))
    
    bill_extractor = BillExtractor(current_app.config['UPLOAD_FOLDER'], cpt_descriptions=get_cpt_descriptions())
    report_extractor = ReportExtractor()
    personal_extractor = PersonalExtractor()
    
    upload_types = {
        'bill_files': (bill_extractor, 'Bill'),
        'report_files': (report_extractor, 'Clinical Report'),
        'personal_files': (personal_extractor, 'Personal Record')
    }
    
    if 'extracted_results' not in session:
        session['extracted_results'] = []
        
    new_results = []
    files_found = False
    storage_helper = AzureStorageHelper()

    for field_name, (extractor, type_label) in upload_types.items():
        if field_name in request.files:
            files = request.files.getlist(field_name)
            for file in files:
                if file.filename == '': continue
                files_found = True
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    
                    with open(filepath, 'rb') as f:
                        storage_helper.upload_blob('uploads', filename, f.read())

                    data, error = extractor.process_pdf(filepath)
                    if data:
                        enrich_medical_codes(data)
                        log_audit('UPLOAD_FILE', type_label, filename)
                        save_extracted_data_to_db(data, type_label, filename)
                        
                        minimal_data = {
                            'patient': encrypt_data(data.get('patient') or data.get('name')),
                            'patient_id': data.get('patient_id'),
                            'insurance_id': encrypt_data(data.get('insurance_id') or data.get('policy_id')),
                            'record_type': type_label,
                            'date': data.get('date') or data.get('dob') or 'N/A'
                        }
                        for key in ['inv', 'total_charges', 'amount_due', 'icd10', 'chief_complaint', 'email']:
                            if key in data:
                                minimal_data[key] = data[key]
                        new_results.append(minimal_data)
    
    if not files_found and 'files' in request.files:
        files = request.files.getlist('files')
        for file in files:
            if file.filename == '' or not allowed_file(file.filename): continue
            filename = secure_filename(file.filename)
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            with open(filepath, 'rb') as f:
                storage_helper.upload_blob('uploads', filename, f.read())

            data, error = bill_extractor.process_pdf(filepath)
            if data:
                enrich_medical_codes(data)
                save_extracted_data_to_db(data, 'Bill', filename)
                minimal_data = {
                    'patient': encrypt_data(data.get('patient')),
                    'patient_id': data.get('patient_id'),
                    'insurance_id': encrypt_data(data.get('insurance_id')),
                    'record_type': 'Bill',
                    'date': data.get('date') or 'N/A'
                }
                new_results.append(minimal_data)

    session['extracted_results'] = new_results
    session.modified = True
    return redirect(url_for('provider.display_results'))

@provider_bp.route('/provider/results')
@login_required
def display_results():
    if current_user.role != UserRole.PROVIDER:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.dashboard'))
    
    results = session.get('extracted_results', [])
    return render_template('results.html', results=results, decrypt_data=decrypt_data)

@provider_bp.route('/provider/timeline/<patient_id>')
@login_required
def timeline(patient_id):
    if current_user.role != UserRole.PROVIDER:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.dashboard'))
    
    patient = Patient.query.filter_by(patient_external_id=patient_id).first_or_404()
    events = []
    for bill in patient.bills:
        events.append({
            'date': bill.date,
            'type': 'Bill',
            'title': f"Medical Bill - {bill.invoice_number}",
            'description': f"Amount: ${bill.amount:.2f} | Status: {bill.status.value}",
            'file': bill.file_path
        })
    for record in patient.clinical_records:
        events.append({
            'date': record.date,
            'type': 'Clinical',
            'title': record.record_type,
            'description': record.summary,
            'file': record.file_path
        })
    events.sort(key=lambda x: x['date'] if x['date'] else datetime.min.date(), reverse=True)
    return render_template('timeline.html', patient=patient, events=events)
