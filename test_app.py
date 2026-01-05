import unittest
import os
from main import app, db
from models import User, UserRole, Provider, Patient, Bill, BillStatus, ClinicalRecord
from werkzeug.security import generate_password_hash
from datetime import date

class EmilyAppTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = app.test_client()
        with app.app_context():
            db.drop_all()
            db.create_all()
            # Seed a test provider
            provider_user = User(
                email="provider@example.com",
                password_hash=generate_password_hash("password123"),
                role=UserRole.PROVIDER,
                name="Dr. Smith"
            )
            db.session.add(provider_user)
            db.session.commit()
            
            provider_profile = Provider(
                user_id=provider_user.id,
                npi="1234567890",
                specialty="General Medicine"
            )
            db.session.add(provider_profile)
            db.session.commit()

    def login(self, email, password):
        return self.client.post('/login', data=dict(
            email=email,
            password=password
        ), follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    def test_login_page_loads(self):
        """Test that the login page loads successfully."""
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Provider Portal', response.data)

    def test_successful_login(self):
        """Test login with correct credentials."""
        response = self.login('provider@example.com', 'password123')
        self.assertIn(b'Provider Portal', response.data)
        self.assertIn(b'Logout', response.data)

    def test_failed_login(self):
        """Test login with incorrect credentials."""
        response = self.login('provider@example.com', 'wrongpassword')
        self.assertIn(b'Login Unsuccessful', response.data)

    def test_protected_index(self):
        """Test that index page redirects to login when not authenticated."""
        response = self.client.get('/', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)

    def test_authenticated_index(self):
        """Test that index page loads for authenticated user."""
        self.login('provider@example.com', 'password123')
        response = self.client.get('/', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Medical Bills', response.data)

    def test_logout(self):
        """Test logout functionality."""
        self.login('provider@example.com', 'password123')
        response = self.logout()
        self.assertIn(b'Please sign in', response.data)
        
        # Verify index is protected again
        response = self.client.get('/', follow_redirects=False)
        self.assertEqual(response.status_code, 302)

    def test_404_page(self):
        """Test that a non-existent page returns a 404 error."""
        response = self.client.get('/non-existent-page')
        self.assertEqual(response.status_code, 404)
        self.assertIn(b'404', response.data)

    def test_provider_patient_list(self):
        """Test that the provider patients list page shows the list of patients."""
        with app.app_context():
            patient_user = User(
                email="patient_test@example.com",
                password_hash=generate_password_hash("password123"),
                role=UserRole.PATIENT,
                name="John Doe Test"
            )
            db.session.add(patient_user)
            db.session.commit()
            
            patient = Patient(
                user_id=patient_user.id,
                patient_external_id="P_TEST_2025",
                insurance_policy_id="POL-TEST-1"
            )
            db.session.add(patient)
            db.session.commit()

        self.login('provider@example.com', 'password123')
        response = self.client.get('/provider/patients', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Registered Patients', response.data)
        self.assertIn(b'P_TEST_2025', response.data)
        self.assertIn(b'John Doe Test', response.data)

    def test_patient_can_view_own_history(self):
        """Test that a patient can view their own medical history."""
        with app.app_context():
            patient_user = User(
                email="patient_history@example.com",
                password_hash=generate_password_hash("password123"),
                role=UserRole.PATIENT,
                name="Harry History"
            )
            db.session.add(patient_user)
            db.session.commit()
            
            patient = Patient(
                user_id=patient_user.id,
                patient_external_id="P_HIST_001",
                insurance_policy_id="POL-HIST-1",
                dob_encrypted="encrypted_dob"
            )
            db.session.add(patient)
            db.session.flush()
            
            record = ClinicalRecord(
                patient_id=patient.id,
                record_type="Clinical Report",
                summary="Patient private history summary",
                date=date(2025, 12, 25)
            )
            db.session.add(record)
            db.session.commit()

        self.login('patient_history@example.com', 'password123')
        # Check dashboard first
        response = self.client.get('/patient', follow_redirects=True)
        self.assertIn(b'View My Records', response.data)
        
        # Check history page
        response = self.client.get('/patient/history', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Patient Intelligence', response.data)
        self.assertIn(b'Patient private history summary', response.data)
        self.assertIn(b'Harry History', response.data)

    def test_provider_patient_detail(self):
        """Test that the patient detail page loads with correct data."""
        with app.app_context():
            patient_user = User(
                email="detail_test@example.com",
                password_hash=generate_password_hash("password123"),
                role=UserRole.PATIENT,
                name="Jane Detail"
            )
            db.session.add(patient_user)
            db.session.commit()
            
            patient = Patient(
                user_id=patient_user.id,
                patient_external_id="P_DETAIL_001",
                insurance_policy_id="POL-DETAIL-1"
            )
            db.session.add(patient)
            db.session.flush()
            
            bill = Bill(
                patient_id=patient.id,
                invoice_number="INV-DETAIL-1",
                amount=500.0,
                status=BillStatus.PENDING,
                date=date(2025, 12, 25)
            )
            record = ClinicalRecord(
                patient_id=patient.id,
                record_type="Clinical Report",
                summary="Detail test record summary",
                date=date(2025, 12, 25)
            )
            db.session.add_all([bill, record])
            db.session.commit()

        self.login('provider@example.com', 'password123')
        response = self.client.get('/provider/patient/P_DETAIL_001', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Patient Intelligence', response.data)
        self.assertIn(b'INV-DETAIL-1', response.data)
        self.assertIn(b'Detail test record summary', response.data)
        self.assertIn(b'Pending', response.data)

    def test_upload_saves_to_db(self):
        """Test that uploading a file saves its data to the Bill/Record tables."""
        from io import BytesIO
        
        with app.app_context():
            patient_user = User(
                email="upload_test@example.com",
                password_hash=generate_password_hash("password123"),
                role=UserRole.PATIENT,
                name="John Upload"
            )
            db.session.add(patient_user)
            db.session.commit()
            patient = Patient(
                user_id=patient_user.id,
                patient_external_id="P2002", # Matches the ID in the seed PDF
                insurance_policy_id="POL-10001"
            )
            db.session.add(patient)
            db.session.commit()
            patient_db_id = patient.id

        self.login('provider@example.com', 'password123')
        
        # Use an existing PDF file
        test_file_path = os.path.join('billings', 'bill_INV-100010_John_Doe_History_Initial.pdf')
        if not os.path.exists(test_file_path):
            # Fallback if path is different
            test_file_path = 'bill_INV-100010_John_Doe_History_Initial.pdf'
            
        with open(test_file_path, 'rb') as f:
            pdf_data = f.read()
            data = {
                'bill_files': (BytesIO(pdf_data), 'bill.pdf')
            }
            response = self.client.post('/provider/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
            
        self.assertEqual(response.status_code, 200)
        
        # Check if Bill was created in DB
        with app.app_context():
            # Filter by invoice number extracted from PDF
            bill = Bill.query.filter_by(invoice_number="INV-100010").first()
            self.assertIsNotNone(bill, "Bill should be saved to database after upload")
            self.assertEqual(bill.amount, 250.0)
            self.assertEqual(bill.patient_id, patient_db_id)

if __name__ == '__main__':
    unittest.main()
