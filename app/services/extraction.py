import os
import re
from typing import List, Dict, Any, Tuple, Optional
from PyPDF2 import PdfReader

class BillExtractor:
    """
    A class to handle medical bill PDF security verification and information extraction.
    """
    def __init__(self, upload_folder: str, cpt_descriptions: Optional[Dict[str, str]] = None):
        self.upload_folder = upload_folder
        self.allowed_extensions = {'pdf'}
        # Default dictionary of common CPT codes and their descriptions if none provided
        self.cpt_descriptions = cpt_descriptions or {
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

    def is_pdf_safe(self, filepath: str) -> bool:
        """
        Perform basic security checks on the PDF.
        - Check if it can be opened and read by PyPDF2.
        - Check for common malicious indicators (like JavaScript).
        """
        try:
            reader = PdfReader(filepath)
            # Check if it has pages (valid PDF structure)
            if len(reader.pages) == 0:
                return False
            
            # Search for /JS or /JavaScript in the raw file content
            with open(filepath, 'rb') as f:
                content = f.read()
                if b'/JS' in content or b'/JavaScript' in content:
                    # Flagging Javascript in PDFs as potentially malicious
                    return False
                    
            return True
        except Exception:
            return False

    def extract_text(self, filepath: str) -> str:
        """Extract all text from the PDF file."""
        try:
            reader = PdfReader(filepath)
            full_text = ""
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
            return full_text
        except Exception as e:
            raise Exception(f"Failed to extract text from PDF: {str(e)}")

    def parse_bill_info(self, text: str) -> Dict[str, Any]:
        """Extract structured info from bill text using regex."""
        data: Dict[str, Any] = {
            'provider': 'N/A',
            'npi': 'N/A',
            'inv': 'N/A',
            'date': 'N/A',
            'patient': 'N/A',
            'patient_id': 'N/A',
            'insurance_id': 'N/A',
            'diagnosis': 'N/A',
            'diagnosis_desc': 'N/A',
            'cpt_codes': [],
            'total_charges': '0.00',
            'amount_due': '0.00'
        }
        
        # regex matches
        provider_match = re.search(r'Provider:\s*(.*)', text)
        if provider_match: data['provider'] = provider_match.group(1).strip()
        
        npi_match = re.search(r'NPI:\s*(\d+)', text)
        if npi_match: data['npi'] = npi_match.group(1).strip()
        
        inv_match = re.search(r'INV:\s*(INV-\d+)', text)
        if inv_match: data['inv'] = inv_match.group(1).strip()
        
        date_match = re.search(r'DATE:\s*(\d{4}-\d{2}-\d{2})', text)
        if date_match: data['date'] = date_match.group(1).strip()
        
        patient_match = re.search(r'PATIENT:\s*(.*)', text)
        if patient_match: data['patient'] = patient_match.group(1).strip()
        
        patient_id_match = re.search(r'ID:\s*(P\d+)', text)
        if patient_id_match: data['patient_id'] = patient_id_match.group(1).strip()
        
        ins_id_match = re.search(r'INS ID:\s*(INS\d+)', text)
        if ins_id_match: data['insurance_id'] = ins_id_match.group(1).strip()
        
        diag_match = re.search(r'DIAGNOSIS:\s*([A-Z]\d+\.?\d*)', text)
        if diag_match: data['diagnosis'] = diag_match.group(1).strip()
        
        desc_match = re.search(r'DESC:\s*(.*)', text)
        if desc_match: data['diagnosis_desc'] = desc_match.group(1).strip()
        
        # Extract CPT codes (5-digit numbers)
        cpt_matches = re.findall(r'\b(\d{5})\b', text)
        if cpt_matches:
            unique_codes = sorted(list(set(cpt_matches)))
            data['cpt_codes'] = [
                {'code': code, 'desc': self.cpt_descriptions.get(code, 'Medical Procedure')}
                for code in unique_codes
            ]
        
        # Extract HCPCS codes (Letter followed by 4 digits)
        hcpcs_matches = re.findall(r'\b([A-Z]\d{4})\b', text)
        if hcpcs_matches:
            unique_hcpcs = sorted(list(set(hcpcs_matches)))
            data['hcpcs_codes'] = [
                {'code': code, 'desc': 'Medical Supply/Service'}
                for code in unique_hcpcs
            ]
        
        total_match = re.search(r'TOTAL CHARGES:\s*\n?\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', text)
        if total_match: data['total_charges'] = total_match.group(1).replace(',', '').strip()
        
        due_match = re.search(r'AMOUNT DUE:\s*\n?\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', text)
        if due_match: data['amount_due'] = due_match.group(1).replace(',', '').strip()
        
        return data

    def process_pdf(self, filepath: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """High-level method to validate and extract info from a PDF file."""
        if not self.is_pdf_safe(filepath):
            return None, "File was rejected due to security concerns or corruption."
        
        try:
            text = self.extract_text(filepath)
            bill_data = self.parse_bill_info(text)
            return bill_data, None
        except Exception as e:
            return None, str(e)

class ReportExtractor:
    """
    A class to handle medical report PDF extraction.
    """
    def __init__(self):
        pass

    def extract_text(self, filepath: str) -> str:
        """Extract all text from the PDF file."""
        try:
            reader = PdfReader(filepath)
            full_text = ""
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
            return full_text
        except Exception as e:
            raise Exception(f"Failed to extract text from PDF: {str(e)}")

    def parse_report_info(self, text: str) -> Dict[str, Any]:
        """Extract structured info from report text using regex."""
        data: Dict[str, Any] = {
            'type': 'Clinical Report',
            'patient': 'N/A',
            'patient_id': 'N/A',
            'date': 'N/A',
            'chief_complaint': 'N/A',
            'assessment': 'N/A',
            'icd10': 'N/A',
            'plan': 'N/A'
        }

        patient_match = re.search(r'PATIENT NAME:\s*\n?(.*)', text, re.IGNORECASE)
        if patient_match: data['patient'] = patient_match.group(1).strip()

        id_match = re.search(r'PATIENT ID:\s*\n?(P\d+)', text, re.IGNORECASE)
        if id_match: data['patient_id'] = id_match.group(1).strip()

        date_match = re.search(r'DATE:\s*\n?(\d{4}-\d{2}-\d{2})', text, re.IGNORECASE)
        if date_match: data['date'] = date_match.group(1).strip()

        cc_match = re.search(r'CHIEF COMPLAINT:\s*\n?(.*?)\n\n?(?:HISTORY|ASSESSMENT|VITALS|PLAN|$)', text, re.DOTALL | re.IGNORECASE)
        if cc_match: data['chief_complaint'] = cc_match.group(1).strip()

        assessment_match = re.search(r'ASSESSMENT:\s*\n?(.*?)\n\n?(?:ICD|PLAN|PLAN:|ELECTRONICALLY|$)', text, re.DOTALL | re.IGNORECASE)
        if assessment_match: data['assessment'] = assessment_match.group(1).strip()

        icd_match = re.search(r'ICD-10(?:\s*Codes)?:\s*([A-Z]\d+\.?\d*)', text, re.IGNORECASE)
        if icd_match: data['icd10'] = icd_match.group(1).strip()

        plan_match = re.search(r'PLAN:\s*\n?(.*?)\n\n?(?:ELECTRONICALLY|$)', text, re.DOTALL | re.IGNORECASE)
        if plan_match: data['plan'] = plan_match.group(1).strip()

        # Fallback for historical reports (different format)
        if data['patient'] == 'N/A':
            patient_match = re.search(r'Patient Name:\s*(.*)', text)
            if patient_match: data['patient'] = patient_match.group(1).strip()

        if data['patient_id'] == 'N/A':
            id_match = re.search(r'Patient ID:\s*(P\d+)', text)
            if id_match: data['patient_id'] = id_match.group(1).strip()

        if data['date'] == 'N/A':
            date_match = re.search(r'Date:\s*(\d{4}-\d{2}-\d{2})', text)
            if date_match: data['date'] = date_match.group(1).strip()

        if data['chief_complaint'] == 'N/A':
            cc_match = re.search(r'Chief Complaint\n(.*?)\n', text, re.DOTALL)
            if cc_match: data['chief_complaint'] = cc_match.group(1).strip()

        if data['assessment'] == 'N/A':
            assessment_match = re.search(r'Assessment\n(.*?)\n', text, re.DOTALL)
            if assessment_match: data['assessment'] = assessment_match.group(1).strip()

        if data['plan'] == 'N/A':
            plan_match = re.search(r'Plan\n(.*?)(?:\n\n|\nCity Memorial|$)', text, re.DOTALL)
            if plan_match: data['plan'] = plan_match.group(1).strip()

        return data

    def process_pdf(self, filepath: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """High-level method to validate and extract info from a PDF report file."""
        try:
            text = self.extract_text(filepath)
            report_data = self.parse_report_info(text)
            return report_data, None
        except Exception as e:
            return None, str(e)

class PersonalExtractor:
    """
    A class to handle personal records PDF extraction.
    """
    def __init__(self):
        pass

    def extract_text(self, filepath: str) -> str:
        """Extract all text from the PDF file."""
        try:
            reader = PdfReader(filepath)
            full_text = ""
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
            return full_text
        except Exception as e:
            raise Exception(f"Failed to extract text from PDF: {str(e)}")

    def parse_personal_info(self, text: str) -> Dict[str, Any]:
        """Extract structured info from personal record text using regex."""
        data: Dict[str, Any] = {
            'type': 'Personal Record',
            'name': 'N/A',
            'patient_id': 'N/A',
            'dob': 'N/A',
            'insurance_id': 'N/A',
            'address': 'N/A',
            'phone': 'N/A',
            'email': 'N/A'
        }

        name_match = re.search(r'Name:\s*(.*)', text, re.IGNORECASE)
        if name_match: data['name'] = name_match.group(1).strip()

        id_match = re.search(r'Patient ID:\s*(P\d+)', text, re.IGNORECASE)
        if id_match: data['patient_id'] = id_match.group(1).strip()

        dob_match = re.search(r'Date of Birth:\s*(\d{4}-\d{2}-\d{2})', text, re.IGNORECASE)
        if dob_match: data['dob'] = dob_match.group(1).strip()

        ins_match = re.search(r'Insurance ID:\s*(INS\d+)', text, re.IGNORECASE)
        if ins_match: data['insurance_id'] = ins_match.group(1).strip()

        addr_match = re.search(r'Address:\s*(.*)', text, re.IGNORECASE)
        if addr_match: data['address'] = addr_match.group(1).strip()

        phone_match = re.search(r'Phone:\s*(.*)', text, re.IGNORECASE)
        if phone_match: data['phone'] = phone_match.group(1).strip()

        email_match = re.search(r'Email:\s*(.*)', text, re.IGNORECASE)
        if email_match: data['email'] = email_match.group(1).strip()

        return data

    def process_pdf(self, filepath: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """High-level method to validate and extract info from a PDF personal record file."""
        try:
            text = self.extract_text(filepath)
            personal_data = self.parse_personal_info(text)
            return personal_data, None
        except Exception as e:
            return None, str(e)
