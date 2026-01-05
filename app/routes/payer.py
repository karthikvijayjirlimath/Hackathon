from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import Patient, UserRole
from app.services.audit import log_audit

payer_bp = Blueprint('payer', __name__)

@payer_bp.route('/payer')
@login_required
def payer_dashboard():
    if current_user.role != UserRole.PAYER:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('main.dashboard'))
    
    log_audit('VIEW_DASHBOARD', 'PAYER_PORTAL')

    # Fetch all patients for payer
    patients = Patient.query.all()
    records = []
    for p in patients:
        records.append({
            'id': p.patient_external_id,
            'name': p.user.name,
            'status': 'verified' if p.insurance_policy_id else 'pending',
            'records_count': len(p.bills) + len(p.clinical_records)
        })

    # Mock fallback if empty
    if not records:
        records = [
            {'id': 'P2002', 'name': 'John Doe', 'status': 'partial', 'records_count': 5},
            {'id': 'P3005', 'name': 'Jane Smith', 'status': 'complete', 'records_count': 3}
        ]
    return render_template('payer_dashboard.html', records=records)
