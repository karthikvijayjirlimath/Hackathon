from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import UserRole
from app.services.audit import log_audit
from app.utils.crypto import decrypt_data

patient_bp = Blueprint('patient', __name__)

@patient_bp.route('/patient')
@login_required
def patient_dashboard():
    if current_user.role != UserRole.PATIENT:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.dashboard'))
    
    patient = current_user.patient_profile
    if not patient:
        flash('Patient profile not found', 'warning')
        return redirect(url_for('main.dashboard'))

    # Mock data for demonstration if no actual data
    patient_data = {
        'name': current_user.name,
        'patient_id': patient.patient_external_id,
        'dob': decrypt_data(patient.dob_encrypted),
        'insurance_id': patient.insurance_policy_id
    }
    
    log_audit('VIEW_DASHBOARD', 'PATIENT_PROFILE', patient_data['patient_id'])

    notifications = [
        {'title': 'Welcome', 'message': f'Welcome to EmilY, {patient_data["name"]}.'},
        {'title': 'Profile Complete', 'message': 'Your personal record has been successfully processed.'}
    ]
    
    return render_template('patient_dashboard.html', patient=patient_data, notifications=notifications)

@patient_bp.route('/patient/history')
@login_required
def patient_history():
    if current_user.role != UserRole.PATIENT:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.dashboard'))
    
    patient = current_user.patient_profile
    if not patient:
        flash('Patient profile not found', 'warning')
        return redirect(url_for('patient.patient_dashboard'))
    
    log_audit('VIEW_MY_HISTORY', 'PATIENT', patient.patient_external_id)
    
    return render_template('patient_detail.html', patient=patient, decrypt_data=decrypt_data, is_patient_view=True)
