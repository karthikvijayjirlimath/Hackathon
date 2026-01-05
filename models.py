from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import enum

db = SQLAlchemy()

class UserRole(enum.Enum):
    PATIENT = "Patient"
    PROVIDER = "Provider"
    PAYER = "Payer"
    ADMIN = "Admin"

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.Enum(UserRole), nullable=False)
    name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    patient_profile = db.relationship('Patient', backref='user', uselist=False)
    provider_profile = db.relationship('Provider', backref='user', uselist=False)
    payer_profile = db.relationship('Payer', backref='user', uselist=False)

class Patient(db.Model):
    __tablename__ = 'patients'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    patient_external_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    dob_encrypted = db.Column(db.String(256))  # Encrypted
    insurance_policy_id = db.Column(db.String(100))
    refund_bank_account_encrypted = db.Column(db.String(256)) # Encrypted
    
class Provider(db.Model):
    __tablename__ = 'providers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    npi = db.Column(db.String(20), unique=True, index=True)
    specialty = db.Column(db.String(100))

class Payer(db.Model):
    __tablename__ = 'payers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    organization_name = db.Column(db.String(100))

class BillStatus(enum.Enum):
    PAID = "Paid"
    PENDING = "Pending"

class Bill(db.Model):
    __tablename__ = 'bills'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    invoice_number = db.Column(db.String(50), unique=True)
    date = db.Column(db.Date)
    amount = db.Column(db.Float)
    status = db.Column(db.Enum(BillStatus), default=BillStatus.PENDING)
    file_path = db.Column(db.String(255))
    
    patient = db.relationship('Patient', backref=db.backref('bills', lazy=True))

class ClinicalRecord(db.Model):
    __tablename__ = 'clinical_records'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    record_type = db.Column(db.String(50)) # e.g. "Clinical Report"
    date = db.Column(db.Date)
    summary = db.Column(db.Text) # Stored as JSON or text
    file_path = db.Column(db.String(255))
    
    patient = db.relationship('Patient', backref=db.backref('clinical_records', lazy=True))

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False) # e.g., 'LOGIN', 'VIEW_PATIENT', 'UPLOAD_FILE'
    resource_type = db.Column(db.String(50)) # e.g., 'BILL', 'REPORT', 'PATIENT'
    resource_id = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(256))
    details = db.Column(db.Text) # JSON or descriptive text

class CPTCode(db.Model):
    __tablename__ = 'cpt_codes'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    long_description = db.Column(db.Text)
    category = db.Column(db.String(50)) # e.g. "Category I", "Category II", etc.
    is_active = db.Column(db.Boolean, default=True)

class HCPCSCode(db.Model):
    __tablename__ = 'hcpcs_codes'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    long_description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)

class ICDCode(db.Model):
    __tablename__ = 'icd_codes'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(15), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    long_description = db.Column(db.Text)
    code_type = db.Column(db.String(10), default="ICD-10-CM") # ICD-9, ICD-10-CM, ICD-10-PCS
    is_active = db.Column(db.Boolean, default=True)
