from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from app.models import db, User, UserRole, CPTCode, HCPCSCode, ICDCode
from app.forms import LoginForm
from app.services.audit import log_audit
from app.services.extraction import BillExtractor, ReportExtractor, PersonalExtractor

main_bp = Blueprint('main', __name__)

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if request.headers.get('Accept') == 'application/json':
            return jsonify({'authenticated': True, 'user': {'email': current_user.email, 'name': current_user.name, 'role': current_user.role.value}})
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            log_audit('LOGIN', details=f"User {user.email} logged in")
            
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'success': True, 'user': {'email': user.email, 'name': user.name, 'role': user.role.value}})
                
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))
        else:
            log_audit('LOGIN_FAILED', details=f"Failed login attempt for {form.email.data}")
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'success': False, 'message': 'Login Unsuccessful'}), 401
            flash('Login Unsuccessful. Please check email and password', 'warning')
    
    if request.headers.get('Accept') == 'application/json':
        return jsonify({'authenticated': False}), 401
        
    return render_template('login.html', form=form)

@main_bp.route('/logout')
def logout():
    if current_user.is_authenticated:
        log_audit('LOGOUT')
    logout_user()
    return redirect(url_for('main.login'))

@main_bp.route('/')
@login_required
def dashboard():
    if request.headers.get('Accept') == 'application/json':
        user_data = {
            'email': current_user.email,
            'name': current_user.name,
            'role': current_user.role.value
        }
        return jsonify({'user': user_data})
        
    if current_user.role == UserRole.PROVIDER:
        return redirect(url_for('provider.provider_dashboard'))
    elif current_user.role == UserRole.PATIENT:
        return redirect(url_for('patient.patient_dashboard'))
    elif current_user.role == UserRole.PAYER:
        return redirect(url_for('payer.payer_dashboard'))
    return redirect(url_for('main.logout'))

@main_bp.app_errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@main_bp.app_errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

# Helper functions that were in main.py
def get_cpt_descriptions():
    try:
        return {c.code: c.description for c in CPTCode.query.all()}
    except:
        return None

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
