import os
import re
from flask import Flask, render_template, request, flash, redirect, url_for
from werkzeug.utils import secure_filename
from extractionLogic import BillExtractor

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Needed for flash messages

# Configure the upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB limit

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Create the directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Initialize BillExtractor
extractor = BillExtractor(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'files' not in request.files:
            flash("No file part")
            return redirect(request.url)

        files = request.files.getlist('files')
        extracted_results = []

        for file in files:
            if file.filename == '':
                continue
            
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                # Process the PDF using BillExtractor
                bill_data, error = extractor.process_pdf(filepath)
                
                if error:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    flash(f"Error processing {filename}: {error}")
                    continue

                if bill_data:
                    extracted_results.append(bill_data)

        return render_template('results.html', results=extracted_results)

    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True, port=8124)