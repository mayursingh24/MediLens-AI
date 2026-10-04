import os
from pathlib import Path
from flask import Flask, render_template, session, jsonify, request
from config import Config
from app.extensions import db, migrate, cors
from app.utils.logger import setup_logger
from app.routes import register_blueprints
from app.models.user import User
from app.models.notification import Notification


def create_app(config_class=Config):
    """Application factory for MediLens AI."""
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parent.parent / "templates"),
        static_folder=str(Path(__file__).resolve().parent.parent / "static")
    )
    app.config.from_object(config_class)

    # Initialize Logger
    setup_logger(app)

    # Ensure vital directories exist
    for folder in [app.config["UPLOAD_FOLDER"], app.config["PROCESSED_FOLDER"], app.config["LOG_DIR"]]:
        Path(folder).mkdir(parents=True, exist_ok=True)

    # Initialize Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app)

    # Register Blueprints
    register_blueprints(app)

    # Automatically create missing database tables on boot
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            app.logger.warning(f"Startup db.create_all() deferred: {e}")

    # Register CLI commands
    @app.cli.command("init-db")
    def init_db_command():
        """CLI helper to non-destructively initialize and sync database tables."""
        from app.utils.db_sync import sync_database_schema
        with app.app_context():
            sync_database_schema()
            print("Database tables initialized successfully.")

    # Context Processors for Templates
    @app.context_processor
    def inject_global_variables():
        current_user = None
        unread_notifications = 0
        if "user_id" in session:
            try:
                current_user = User.query.get(session["user_id"])
                unread_notifications = Notification.query.filter_by(
                    user_id=session["user_id"],
                    status="unread"
                ).count()
            except Exception:
                pass

        return {
            "current_user": current_user,
            "active_user_name": session.get("user_name"),
            "active_profile_id": session.get("active_profile_id"),
            "preferred_language": session.get("preferred_language", "en"),
            "unread_notifications_count": unread_notifications,
        }

    # Safe Error Handlers (Never expose stack traces)
    @app.errorhandler(404)
    def page_not_found(e):
        if request.is_json or request.path.startswith("/api/"):
            return jsonify({"error": "Resource not found", "status": 404}), 404
        return render_template("base.html", error_title="Page Not Found", error_message="The requested page could not be located."), 404

    @app.errorhandler(413)
    def file_too_large(e):
        msg = "File upload size exceeds the allowed limit (16 MB)."
        if request.is_json or request.path.startswith("/api/"):
            return jsonify({"error": msg, "status": 413}), 413
        return render_template("base.html", error_title="Upload Too Large", error_message=msg), 413

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.error(f"Internal server error encountered: {e}")
        db.session.rollback()
        msg = "An unexpected error occurred. Our engineering team has logged this issue."
        if request.is_json or request.path.startswith("/api/"):
            return jsonify({"error": msg, "status": 500}), 500
        return render_template("base.html", error_title="Server Error", error_message=msg), 500

    return app
