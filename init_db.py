from run import app
from app.models import db, User, UserRole, Patient, Provider, Payer, Bill, BillStatus, ClinicalRecord, CPTCode, HCPCSCode, ICDCode
from werkzeug.security import generate_password_hash
from datetime import date
import os

def init_db():
    with app.app_context():
        # Create tables
        db.create_all()
        
        # Check if users already exist
        if User.query.first() is None:
            print("Seeding initial users...")
            # Create a Provider
            provider_user = User(
                email="provider@example.com",
                password_hash=generate_password_hash("password123"),
                role=UserRole.PROVIDER,
                name="Dr. Smith"
            )
            db.session.add(provider_user)
            db.session.flush()
            
            provider_profile = Provider(
                user_id=provider_user.id,
                npi="1234567890",
                specialty="General Medicine"
            )
            db.session.add(provider_profile)
            
            # Create a Patient
            patient_user = User(
                email="patient@example.com",
                password_hash=generate_password_hash("password123"),
                role=UserRole.PATIENT,
                name="John Doe"
            )
            db.session.add(patient_user)
            db.session.flush()
            
            patient_profile = Patient(
                user_id=patient_user.id,
                patient_external_id="P2002",
                dob_encrypted="encrypted_dob", # In real seed, we should use the encrypt_data util
                insurance_policy_id="POL-10001"
            )
            db.session.add(patient_profile)
            db.session.flush() # Ensure patient_profile has an ID
            
            # Add some seed bills for P2002
            bill1 = Bill(
                patient_id=patient_profile.id,
                invoice_number="INV-100010",
                date=date(2025, 10, 15),
                amount=250.00,
                status=BillStatus.PAID,
                file_path="bill_INV-100010_John_Doe_History_Initial.pdf"
            )
            bill2 = Bill(
                patient_id=patient_profile.id,
                invoice_number="INV-100045",
                date=date(2025, 11, 20),
                amount=1200.00,
                status=BillStatus.PENDING,
                file_path="bill_INV-100045_John_Doe_History_ER.pdf"
            )
            db.session.add_all([bill1, bill2])
            
            # Add some seed clinical records for P2002
            record1 = ClinicalRecord(
                patient_id=patient_profile.id,
                record_type="Clinical Report",
                date=date(2025, 10, 15),
                summary="Initial Diagnosis: Asthma",
                file_path="P2002_History_1_Initial_Diagnosis.pdf"
            )
            db.session.add(record1)

            # Create a Payer
            payer_user = User(
                email="payer@example.com",
                password_hash=generate_password_hash("password123"),
                role=UserRole.PAYER,
                name="Aetna Claims"
            )
            db.session.add(payer_user)
            db.session.flush()
            
            db.session.commit()
            print("Initial users and related data seeded.")

        # Seed Medical Codes (always check if they exist)
        print("Checking for medical codes to seed...")
        cpt_samples = {
            '32853': 'Lung transplant, bilateral',
            '99202': 'Office/outpatient visit, new patient, 15-29 min',
            '99203': 'Office/outpatient visit, new patient, 30-44 min',
            '99204': 'Office/outpatient visit, new patient, 45-59 min',
            '99205': 'Office/outpatient visit, new patient, 60-74 min',
            '99211': 'Office/outpatient visit, established patient, minimal',
            '99212': 'Office/outpatient visit, established patient, 10-19 min',
            '99213': 'Office/outpatient visit, established patient, 20-29 min',
            '99214': 'Office/outpatient visit, established patient, 30-39 min',
            '99215': 'Office/outpatient visit, established patient, 40-54 min',
            '90630': 'Influenza virus vaccine, quadrivalent (IIV4), split virus, preservative free, for intradermal use',
            '90651': 'Human Papillomavirus vaccine types 6, 11, 16, 18, 31, 33, 45, 52, 58, nonavalent (9vHPV), 2 or 3 dose schedule, for intramuscular use',
            '80053': 'Comprehensive metabolic panel',
            '85025': 'Complete blood count (CBC), automated',
            '81001': 'Urinalysis, by dip stick or tablet reagent; automated, with microscopy',
            '93000': 'Electrocardiogram, routine ECG with at least 12 leads; with interpretation and report',
            '99283': 'Emergency department visit, moderate severity',
            '71045': 'Radiologic examination, chest; single view',
            '82947': 'Glucose; quantitative, blood (except reagent strip)',
            '83036': 'Hemoglobin; glycosylated (A1c)',
            '29405': 'Application of short leg cast (below knee to toes)',
            '99282': 'Emergency department visit, low to moderate severity',
            '11102': 'Tangential biopsy of skin (eg, shave, scoop, saucerize, curette); single lesion',
            '43235': 'Esophagogastroduodenoscopy, flexible, transoral; diagnostic, including collection of specimen(s) by brushing or washing, when performed (separate procedure)',
            '95810': 'Polysomnography; age 6 years or older, sleep staging with 4 or more additional parameters of sleep, attended by a technologist',
        }
        for code, desc in cpt_samples.items():
            if not CPTCode.query.filter_by(code=code).first():
                db.session.add(CPTCode(code=code, description=desc))

        hcpcs_samples = {
            'A0425': 'Ground ambulance transport, mileage, per statute mile',
            'A0427': 'Ambulance service, advanced life support, emergency transport, level 1 (ALS1-emergency)',
            'E0431': 'Portable gaseous oxygen system, rental; includes container, regulator, flowmeter, humidifier, cannula or mask, and tubing',
            'G0008': 'Administration of influenza virus vaccine',
            'J0171': 'Injection, adrenalin, epinephrine, 0.1 mg',
            'J1100': 'Injection, dexamethasone sodium phosphate, up to 1 mg',
        }
        for code, desc in hcpcs_samples.items():
            if not HCPCSCode.query.filter_by(code=code).first():
                db.session.add(HCPCSCode(code=code, description=desc))

        icd_samples = {
            'J45.909': 'Unspecified asthma, uncomplicated',
            'I10': 'Essential (primary) hypertension',
            'E11.9': 'Type 2 diabetes mellitus without complications',
            'Z00.00': 'Encounter for general adult medical examination without abnormal findings',
            'M54.5': 'Low back pain',
            'R05': 'Cough',
            'J06.9': 'Acute upper respiratory infection, unspecified',
        }
        for code, desc in icd_samples.items():
            if not ICDCode.query.filter_by(code=code).first():
                db.session.add(ICDCode(code=code, description=desc))

        db.session.commit()
        print("Medical codes seeded successfully.")

if __name__ == "__main__":
    init_db()
