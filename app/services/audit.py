from flask import request, current_app
from flask_login import current_user
from app.models import db, AuditLog
import logging

logger = logging.getLogger(__name__)

def log_audit(action, resource_type=None, resource_id=None, details=None):
    try:
        audit = AuditLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
            details=details
        )
        db.session.add(audit)
        db.session.commit()
    except Exception as e:
        logger.error(f"Failed to log audit: {e}")
        db.session.rollback()
