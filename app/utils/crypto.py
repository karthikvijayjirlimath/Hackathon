from cryptography.fernet import Fernet
from flask import current_app

def get_fernet():
    key = current_app.config.get('ENCRYPTION_KEY')
    return Fernet(key.encode())

def encrypt_data(data: str) -> str:
    if not data or data == 'N/A':
        return data
    fernet = get_fernet()
    return fernet.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    if not encrypted_data or encrypted_data == 'N/A':
        return encrypted_data
    try:
        fernet = get_fernet()
        return fernet.decrypt(encrypted_data.encode()).decode()
    except Exception:
        return encrypted_data
