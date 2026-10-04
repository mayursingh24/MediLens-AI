import pymysql
from flask import current_app
from app.utils.logger import get_logger

logger = get_logger()


def sync_database_schema():
    """
    Non-destructively synchronize database schema with existing MySQL database.
    - Inspects existing tables ('users', 'prescriptions', 'medicines').
    - Only adds missing columns to existing tables using ALTER TABLE.
    - Creates missing feature tables ('profiles', 'schedules', 'medication_logs', 'notifications', 'audit_logs') with proper FKs and indexes.
    - Never drops database or deletes any data.
    """
    import urllib.parse
    db_url = current_app.config.get("DATABASE_URL")
    if db_url:
        parsed = urllib.parse.urlparse(db_url.replace("mysql+pymysql://", "mysql://"))
        host = parsed.hostname or "localhost"
        port = parsed.port or 3306
        user = urllib.parse.unquote(parsed.username or "root")
        password = urllib.parse.unquote(parsed.password or "")
        database = parsed.path.lstrip("/") or "medilens"
    else:
        host = current_app.config.get("MYSQL_HOST", "localhost")
        port = int(current_app.config.get("MYSQL_PORT", 3306))
        user = current_app.config.get("MYSQL_USER", "root")
        password = current_app.config.get("MYSQL_PASSWORD", "")
        database = current_app.config.get("MYSQL_DATABASE", "medilens")

    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset="utf8mb4",
        autocommit=True
    )
    cur = conn.cursor()

    try:
        # Get existing tables
        cur.execute("SHOW TABLES")
        existing_tables = {row[0] for row in cur.fetchall()}
        logger.info(f"Existing tables in '{database}': {existing_tables}")

        # Helper to get existing columns of a table
        def get_columns(table_name):
            cur.execute(f"DESCRIBE {table_name}")
            return {row[0] for row in cur.fetchall()}

        # 1. Sync 'users' table
        if "users" in existing_tables:
            user_cols = get_columns("users")
            if "name" not in user_cols and "full_name" in user_cols:
                pass  # already has full_name
            elif "full_name" not in user_cols and "name" in user_cols:
                # Add full_name or allow name
                pass
            if "is_active" not in user_cols:
                cur.execute("ALTER TABLE users ADD COLUMN is_active TINYINT(1) DEFAULT 1 NOT NULL")
            if "preferred_language" not in user_cols:
                cur.execute("ALTER TABLE users ADD COLUMN preferred_language VARCHAR(10) DEFAULT 'en' NOT NULL")
            if "updated_at" not in user_cols:
                cur.execute("ALTER TABLE users ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(120) NOT NULL,
                    email VARCHAR(191) NOT NULL UNIQUE,
                    password VARCHAR(255) NOT NULL,
                    is_active TINYINT(1) DEFAULT 1 NOT NULL,
                    preferred_language VARCHAR(10) DEFAULT 'en' NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP NOT NULL,
                    INDEX idx_user_email (email)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

        # 2. Create 'profiles' table if missing (needed for family profiles & prescription association)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                name VARCHAR(100) NOT NULL,
                relationship VARCHAR(50) DEFAULT 'Me' NOT NULL,
                age INT NULL,
                gender VARCHAR(20) NULL,
                weight_kg FLOAT NULL,
                allergies_json TEXT NULL,
                existing_conditions_json TEXT NULL,
                existing_medications_json TEXT NULL,
                pregnancy_status VARCHAR(50) NULL,
                notes TEXT NULL,
                is_default TINYINT(1) DEFAULT 0 NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP NOT NULL,
                INDEX idx_profiles_user_id (user_id),
                CONSTRAINT fk_profiles_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Sync existing profiles columns if already created
        if "profiles" in existing_tables:
            prof_cols = get_columns("profiles")
            if "weight_kg" not in prof_cols:
                cur.execute("ALTER TABLE profiles ADD COLUMN weight_kg FLOAT NULL")
            if "allergies_json" not in prof_cols:
                cur.execute("ALTER TABLE profiles ADD COLUMN allergies_json TEXT NULL")
            if "existing_conditions_json" not in prof_cols:
                cur.execute("ALTER TABLE profiles ADD COLUMN existing_conditions_json TEXT NULL")
            if "existing_medications_json" not in prof_cols:
                cur.execute("ALTER TABLE profiles ADD COLUMN existing_medications_json TEXT NULL")
            if "pregnancy_status" not in prof_cols:
                cur.execute("ALTER TABLE profiles ADD COLUMN pregnancy_status VARCHAR(50) NULL")

        # 3. Sync 'prescriptions' table
        if "prescriptions" in existing_tables:
            p_cols = get_columns("prescriptions")
            if "profile_id" not in p_cols:
                cur.execute("ALTER TABLE prescriptions ADD COLUMN profile_id INT NULL")
                try:
                    cur.execute("ALTER TABLE prescriptions ADD CONSTRAINT fk_prescriptions_profile FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE SET NULL")
                except Exception:
                    pass
            if "original_filename" not in p_cols:
                cur.execute("ALTER TABLE prescriptions ADD COLUMN original_filename VARCHAR(255) DEFAULT 'prescription.jpg' NOT NULL")
            if "image_path" not in p_cols and "stored_filename" in p_cols:
                pass
            elif "stored_filename" not in p_cols and "image_path" in p_cols:
                pass
            if "file_type" not in p_cols:
                cur.execute("ALTER TABLE prescriptions ADD COLUMN file_type VARCHAR(50) DEFAULT 'image' NOT NULL")
            if "file_size" not in p_cols:
                cur.execute("ALTER TABLE prescriptions ADD COLUMN file_size INT DEFAULT 0 NOT NULL")
            if "page_count" not in p_cols:
                cur.execute("ALTER TABLE prescriptions ADD COLUMN page_count INT DEFAULT 1 NOT NULL")
            if "patient_name" not in p_cols:
                cur.execute("ALTER TABLE prescriptions ADD COLUMN patient_name VARCHAR(150) NULL")
            if "status" not in p_cols:
                cur.execute("ALTER TABLE prescriptions ADD COLUMN status VARCHAR(30) DEFAULT 'completed' NOT NULL")
            if "ocr_quality" not in p_cols:
                cur.execute("ALTER TABLE prescriptions ADD COLUMN ocr_quality VARCHAR(20) DEFAULT 'fair' NOT NULL")
            if "has_unclear_fields" not in p_cols:
                cur.execute("ALTER TABLE prescriptions ADD COLUMN has_unclear_fields TINYINT(1) DEFAULT 0 NOT NULL")
            if "error_message" not in p_cols:
                cur.execute("ALTER TABLE prescriptions ADD COLUMN error_message TEXT NULL")
            if "raw_ocr_text" not in p_cols:
                cur.execute("ALTER TABLE prescriptions ADD COLUMN raw_ocr_text MEDIUMTEXT NULL")
            if "gemini_raw_response" not in p_cols:
                cur.execute("ALTER TABLE prescriptions ADD COLUMN gemini_raw_response MEDIUMTEXT NULL")
            if "general_instructions_json" not in p_cols:
                cur.execute("ALTER TABLE prescriptions ADD COLUMN general_instructions_json TEXT NULL")
            if "unclear_items_json" not in p_cols:
                cur.execute("ALTER TABLE prescriptions ADD COLUMN unclear_items_json TEXT NULL")
            if "comparison_data_json" not in p_cols:
                cur.execute("ALTER TABLE prescriptions ADD COLUMN comparison_data_json MEDIUMTEXT NULL")
            if "clinical_safety_json" not in p_cols:
                cur.execute("ALTER TABLE prescriptions ADD COLUMN clinical_safety_json MEDIUMTEXT NULL")
            if "updated_at" not in p_cols:
                cur.execute("ALTER TABLE prescriptions ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP NOT NULL")

        # 4. Sync 'medicines' table
        if "medicines" in existing_tables:
            m_cols = get_columns("medicines")
            if "profile_id" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN profile_id INT NULL")
                try:
                    cur.execute("ALTER TABLE medicines ADD CONSTRAINT fk_medicines_profile FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE SET NULL")
                except Exception:
                    pass
            if "strength" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN strength VARCHAR(100) NULL")
            if "form" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN form VARCHAR(100) DEFAULT 'Tablet' NULL")
            if "morning" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN morning FLOAT DEFAULT 0.0 NOT NULL")
            if "afternoon" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN afternoon FLOAT DEFAULT 0.0 NOT NULL")
            if "evening" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN evening FLOAT DEFAULT 0.0 NOT NULL")
            if "night" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN night FLOAT DEFAULT 0.0 NOT NULL")
            if "duration_days" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN duration_days INT NULL")
            if "food_instruction" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN food_instruction VARCHAR(255) NULL")
            if "special_instruction" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN special_instruction TEXT NULL")
            if "quantity" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN quantity INT DEFAULT 1 NULL")
            if "is_in_shopping_list" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN is_in_shopping_list TINYINT(1) DEFAULT 1 NOT NULL")
            if "is_purchased" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN is_purchased TINYINT(1) DEFAULT 0 NOT NULL")
            if "confidence" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN confidence FLOAT DEFAULT 0.0 NOT NULL")
            if "verification_status" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN verification_status VARCHAR(50) DEFAULT 'review_required' NOT NULL")
            if "ocr_extracted_text" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN ocr_extracted_text TEXT NULL")
            if "gemini_extracted_text" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN gemini_extracted_text TEXT NULL")
            if "conflict_details" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN conflict_details TEXT NULL")
            if "source_page" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN source_page INT DEFAULT 1 NOT NULL")
            if "is_user_verified" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN is_user_verified TINYINT(1) DEFAULT 0 NOT NULL")
            if "verified_name" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN verified_name VARCHAR(255) NULL")
            if "verified_strength" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN verified_strength VARCHAR(100) NULL")
            if "verified_form" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN verified_form VARCHAR(100) NULL")
            if "verified_dosage" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN verified_dosage VARCHAR(100) NULL")
            if "verified_frequency" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN verified_frequency VARCHAR(100) NULL")
            if "verified_morning" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN verified_morning FLOAT NULL")
            if "verified_afternoon" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN verified_afternoon FLOAT NULL")
            if "verified_evening" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN verified_evening FLOAT NULL")
            if "verified_night" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN verified_night FLOAT NULL")
            if "verified_duration_days" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN verified_duration_days INT NULL")
            if "verified_food_instruction" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN verified_food_instruction VARCHAR(255) NULL")
            if "verification_notes" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN verification_notes TEXT NULL")
            if "verified_at" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN verified_at DATETIME NULL")
            if "created_at" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL")
            if "generic_name" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN generic_name VARCHAR(255) NULL")
            if "brand_name" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN brand_name VARCHAR(255) NULL")
            if "confidence_breakdown_json" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN confidence_breakdown_json TEXT NULL")
            if "external_intelligence_json" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN external_intelligence_json MEDIUMTEXT NULL")
            if "why_taking_this" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN why_taking_this TEXT NULL")
            if "estimated_price_json" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN estimated_price_json TEXT NULL")
            if "updated_at" not in m_cols:
                cur.execute("ALTER TABLE medicines ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP NOT NULL")

        # 5. Create 'schedules' table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id INT AUTO_INCREMENT PRIMARY KEY,
                medicine_id INT NOT NULL,
                prescription_id INT NOT NULL,
                profile_id INT NOT NULL,
                user_id INT NOT NULL,
                time_slot VARCHAR(50) NOT NULL,
                reminder_time VARCHAR(10) NOT NULL,
                dose_amount VARCHAR(100) DEFAULT '1 tablet' NOT NULL,
                food_instruction VARCHAR(255) NULL,
                start_date DATE NOT NULL,
                end_date DATE NULL,
                is_active TINYINT(1) DEFAULT 1 NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP NOT NULL,
                INDEX idx_sched_user (user_id),
                INDEX idx_sched_profile (profile_id),
                INDEX idx_sched_medicine (medicine_id),
                CONSTRAINT fk_sched_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT fk_sched_prescription FOREIGN KEY (prescription_id) REFERENCES prescriptions(id) ON DELETE CASCADE,
                CONSTRAINT fk_sched_medicine FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE,
                CONSTRAINT fk_sched_profile FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # 6. Create 'medication_logs' table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS medication_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                schedule_id INT NOT NULL,
                medicine_id INT NOT NULL,
                profile_id INT NOT NULL,
                user_id INT NOT NULL,
                scheduled_date DATE NOT NULL,
                scheduled_time VARCHAR(10) NOT NULL,
                action VARCHAR(20) NOT NULL,
                logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                notes TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP NOT NULL,
                INDEX idx_log_user_date (user_id, scheduled_date),
                INDEX idx_log_schedule (schedule_id),
                CONSTRAINT fk_log_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT fk_log_sched FOREIGN KEY (schedule_id) REFERENCES schedules(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # 7. Create 'notifications' table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                profile_id INT NULL,
                prescription_id INT NULL,
                schedule_id INT NULL,
                title VARCHAR(200) NOT NULL,
                message TEXT NOT NULL,
                notification_type VARCHAR(50) DEFAULT 'medicine_reminder' NOT NULL,
                status VARCHAR(20) DEFAULT 'unread' NOT NULL,
                scheduled_for DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP NOT NULL,
                INDEX idx_notif_user_status (user_id, status),
                CONSTRAINT fk_notif_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # 8. Create 'audit_logs' table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                action VARCHAR(100) NOT NULL,
                resource_type VARCHAR(50) NOT NULL,
                resource_id INT NULL,
                details_json TEXT NULL,
                ip_address VARCHAR(45) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                INDEX idx_audit_user (user_id),
                INDEX idx_audit_action (action)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        logger.info("Database schema synchronized successfully with 'medilens'.")
        print("Database schema synchronized successfully with 'medilens'.")

    except Exception as e:
        logger.error(f"Schema synchronization error: {e}")
        raise e
    finally:
        conn.close()
