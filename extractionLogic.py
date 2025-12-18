import os
import re
from PyPDF2 import PdfReader

class BillExtractor:
    """
    A class to handle medical bill PDF security verification and information extraction.
    """
    def __init__(self, upload_folder):
        self.upload_folder = upload_folder
        self.allowed_extensions = {'pdf'}
        # Dictionary of common CPT codes and their descriptions
        self.cpt_descriptions = {
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

    def is_pdf_safe(self, filepath):
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

    def extract_text(self, filepath):
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

    def parse_bill_info(self, text):
        """Extract structured info from bill text using regex."""
        data = {
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
        
        total_match = re.search(r'TOTAL CHARGES:\s*\n?\s*(\d+\.\d{2})', text)
        if total_match: data['total_charges'] = total_match.group(1).strip()
        
        due_match = re.search(r'AMOUNT DUE:\s*\n?\s*(\d+\.\d{2})', text)
        if due_match: data['amount_due'] = due_match.group(1).strip()
        
        return data

    def process_pdf(self, filepath):
        """High-level method to validate and extract info from a PDF file."""
        if not self.is_pdf_safe(filepath):
            return None, "File was rejected due to security concerns or corruption."
        
        try:
            text = self.extract_text(filepath)
            bill_data = self.parse_bill_info(text)
            return bill_data, None
        except Exception as e:
            return None, str(e)
