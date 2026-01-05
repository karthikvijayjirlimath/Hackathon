import os
import logging
from flask import Flask
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
from flask_login import LoginManager
from dotenv import load_dotenv
from cryptography.fernet import Fernet
from app.models import db, User
from app.utils.azure import AzureStorageHelper, AzureKeyVaultHelper

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize extensions
csrf = CSRFProtect()
talisman = Talisman()
login_manager = LoginManager()
login_manager.login_view = 'main.login'

def create_app():
    load_dotenv()
    
    app = Flask(__name__, 
                template_folder='../templates', 
                static_folder='../static')
    
    # Initialize Azure Helpers
    kv_helper = AzureKeyVaultHelper()
    storage_helper = AzureStorageHelper()
    
    SECRET_KEY = kv_helper.get_secret("SECRET-KEY") or os.environ.get("SECRET_KEY", "fallback-secret-key-for-dev")
    ENCRYPTION_KEY = kv_helper.get_secret("ENCRYPTION-KEY") or os.environ.get("ENCRYPTION_KEY")
    
    if not ENCRYPTION_KEY:
        ENCRYPTION_KEY = Fernet.generate_key().decode()
        logger.warning("ENCRYPTION_KEY not found. Generated a temporary key.")
    
    app.secret_key = SECRET_KEY
    app.config['ENCRYPTION_KEY'] = ENCRYPTION_KEY
    
    DB_URL = os.environ.get('DATABASE_URL') or "sqlite:///instance/app.db"
    app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Folders
    app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'uploads')
    app.config['REPORTS_FOLDER'] = os.environ.get('REPORTS_FOLDER', 'reports')
    app.config['BILLINGS_FOLDER'] = os.environ.get('BILLINGS_FOLDER', 'billings')
    app.config['PERSONAL_FOLDER'] = os.environ.get('PERSONAL_FOLDER', 'personal_data')
    app.config['ALLOWED_EXTENSIONS'] = {'pdf'}
    app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))

    for folder in [app.config['UPLOAD_FOLDER'], app.config['REPORTS_FOLDER'], 
                   app.config['BILLINGS_FOLDER'], app.config['PERSONAL_FOLDER']]:
        if not os.path.exists(folder):
            os.makedirs(folder)

    # Initialize extensions with app
    db.init_app(app)
    csrf.init_app(app)
    talisman.init_app(app, content_security_policy=None, force_https=False)
    login_manager.init_app(app)
    
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Register Blueprints
    from app.routes.main import main_bp
    from app.routes.provider import provider_bp
    from app.routes.patient import patient_bp
    from app.routes.payer import payer_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(provider_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(payer_bp)
    
    return app
