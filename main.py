import os
import re
from flask import Flask, render_template, request, flash, redirect, url_for, session
from werkzeug.utils import secure_filename
from extractionLogic import BillExtractor, ReportExtractor, PersonalExtractor

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Needed for flash messages and sessions

# Configure folders
UPLOAD_FOLDER = 'uploads'
REPORTS_FOLDER = 'reports'
BILLINGS_FOLDER = 'billings'
PERSONAL_FOLDER = 'personal_data'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB limit

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
bill_extractor = BillExtractor(UPLOAD_FOLDER)
report_extractor = ReportExtractor()
personal_extractor = PersonalExtractor()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def upload_file():
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

                        # Process the PDF using appropriate extractor
                        data, error = extractor.process_pdf(filepath)
                        
                        if error:
                            if os.path.exists(filepath):
                                os.remove(filepath)
                            flash(f"Error processing {filename}: {error}")
                            continue

                        if data:
                            data['record_type'] = type_label
                            new_results.append(data)
        
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

                    # For "Upload More", we try to detect or default to Bill
                    data, error = bill_extractor.process_pdf(filepath)
                    if data:
                        data['record_type'] = 'Bill'
                        new_results.append(data)
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
            
        return redirect(url_for('display_results'))

    # Clear all data when the index page is reloaded (GET request)
    session.pop('extracted_results', None)
    session.modified = True
    return render_template('index.html')

@app.route('/results')
def display_results():
    if 'extracted_results' not in session:
        return redirect(url_for('upload_file'))
    return render_template('results.html', results=session['extracted_results'])

@app.route('/timeline/<patient_id>')
def timeline(patient_id):
    timeline_events = []
    
    # Scan billings
    if os.path.exists(app.config['BILLINGS_FOLDER']):
        for filename in os.listdir(app.config['BILLINGS_FOLDER']):
            if filename.endswith('.pdf'):
                filepath = os.path.join(app.config['BILLINGS_FOLDER'], filename)
                data, error = bill_extractor.process_pdf(filepath)
                if data and data.get('patient_id') == patient_id:
                    data['event_type'] = 'Billing'
                    timeline_events.append(data)
                
    # Scan reports
    if os.path.exists(app.config['REPORTS_FOLDER']):
        for filename in os.listdir(app.config['REPORTS_FOLDER']):
            if filename.endswith('.pdf'):
                filepath = os.path.join(app.config['REPORTS_FOLDER'], filename)
                data, error = report_extractor.process_pdf(filepath)
                if data and data.get('patient_id') == patient_id:
                    data['event_type'] = 'Clinical Report'
                    timeline_events.append(data)
                
    # Sort by date
    timeline_events.sort(key=lambda x: x.get('date', '0000-00-00'))
    
    return render_template('timeline.html', patient_id=patient_id, events=timeline_events)

if __name__ == '__main__':
    app.run(debug=True, port=8124)