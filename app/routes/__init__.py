from app.routes.auth_routes import auth_bp
from app.routes.dashboard_routes import dashboard_bp
from app.routes.prescription_routes import prescription_bp
from app.routes.medicine_routes import medicine_bp
from app.routes.schedule_routes import schedule_bp
from app.routes.pharmacy_routes import pharmacy_bp
from app.routes.profile_routes import profile_bp
from app.routes.assistant_routes import assistant_bp

def register_blueprints(app):
    """Register all Flask blueprints onto application instance."""
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(prescription_bp)
    app.register_blueprint(medicine_bp)
    app.register_blueprint(schedule_bp)
    app.register_blueprint(pharmacy_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(assistant_bp)
