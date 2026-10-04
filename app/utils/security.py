import time
from functools import wraps
from flask import session, redirect, url_for, request, jsonify, flash, g
from app.models.audit_log import AuditLog
from app.extensions import db


# In-memory sliding window rate limiter for critical endpoints (AI & Auth)
_RATE_LIMITS = {}


def rate_limit(limit_count: int = 15, per_seconds: int = 60):
    """Rate limiter decorator for sensitive routes (e.g. AI analysis, login)."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()
            key = f"{f.__name__}:{client_ip}"
            current_time = time.time()

            window_start = current_time - per_seconds
            timestamps = [t for t in _RATE_LIMITS.get(key, []) if t > window_start]
            
            if len(timestamps) >= limit_count:
                retry_after = int(per_seconds - (current_time - timestamps[0]))
                if request.is_json or request.path.startswith("/api/"):
                    return jsonify({
                        "error": "Too many requests. Please slow down.",
                        "retry_after_seconds": max(1, retry_after)
                    }), 429
                flash(f"Too many requests. Please wait {max(1, retry_after)} seconds.", "danger")
                return redirect(request.referrer or url_for("dashboard.index"))

            timestamps.append(current_time)
            _RATE_LIMITS[key] = timestamps

            return f(*args, **kwargs)
        return wrapped
    return decorator


def login_required(f):
    """Decorator to require login for web and API routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required", "status": "unauthorized"}), 401
            session["next_url"] = request.url
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function


def record_audit(action: str, resource_type: str, resource_id: int = None, details: dict = None):
    """Safely log security-relevant actions to the audit_logs table."""
    try:
        user_id = session.get("user_id")
        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
        log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=client_ip[:45],
        )
        log.details = details or {}
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()
