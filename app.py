import os
from app import create_app
from app.extensions import db

from app.utils.db_sync import sync_database_schema

app = create_app()


@app.cli.command("init-db")
def init_db_command():
    """CLI helper to non-destructively initialize and sync database tables."""
    with app.app_context():
        sync_database_schema()
        print("Database tables initialized successfully.")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
