import os
import uuid
from pathlib import Path
from werkzeug.utils import secure_filename
from PIL import Image
from flask import current_app


ALLOWED_MIME_TYPES = {
    "image/jpeg": "image",
    "image/png": "image",
    "image/jpg": "image",
    "application/pdf": "pdf",
}

# Magic bytes detection
MAGIC_NUMBERS = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"%PDF": "application/pdf",
}


def detect_mime_type_from_bytes(file_head: bytes) -> str:
    """Detect MIME type by inspecting leading magic bytes."""
    for magic, mime in MAGIC_NUMBERS.items():
        if file_head.startswith(magic):
            return mime
    return ""


def validate_file_integrity(file_path: Path, file_type: str) -> bool:
    """Verify file integrity using Pillow or PDF inspection."""
    try:
        if file_type == "image":
            with Image.open(file_path) as img:
                img.verify()
            return True
        elif file_type == "pdf":
            with open(file_path, "rb") as f:
                header = f.read(5)
                if not header.startswith(b"%PDF"):
                    return False
                # Check for standard EOF marker in last 1024 bytes
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - 1024))
                tail = f.read()
                return b"%%EOF" in tail or b"%PDF" in header
        return False
    except Exception:
        return False


def save_uploaded_file(file_storage, user_id: int):
    """
    Validate, sanitize, and securely store an uploaded file.
    Returns: dict(
        stored_path, original_filename, stored_filename, file_type, file_size
    )
    Raises: ValueError on validation failure.
    """
    if not file_storage or not file_storage.filename:
        raise ValueError("No file provided.")

    original_filename = secure_filename(file_storage.filename)
    if not original_filename:
        original_filename = f"prescription_{uuid.uuid4().hex[:8]}.jpg"

    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
    allowed_exts = current_app.config.get("ALLOWED_EXTENSIONS", {"png", "jpg", "jpeg", "pdf"})
    if ext not in allowed_exts:
        raise ValueError(f"Unsupported file format '.{ext}'. Supported formats: {', '.join(allowed_exts)}")

    # Read first 1024 bytes to check MIME type via magic bytes
    file_storage.seek(0)
    head = file_storage.read(1024)
    file_storage.seek(0)

    detected_mime = detect_mime_type_from_bytes(head)
    if detected_mime not in ALLOWED_MIME_TYPES:
        raise ValueError("Invalid file content. File header does not match expected image or PDF format.")

    file_type = ALLOWED_MIME_TYPES[detected_mime]

    # Generate isolated stored filename
    unique_prefix = f"u{user_id}_{uuid.uuid4().hex}"
    stored_filename = f"{unique_prefix}.{ext}"

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    upload_folder.mkdir(parents=True, exist_ok=True)

    dest_path = upload_folder / stored_filename
    file_storage.save(str(dest_path))

    file_size = dest_path.stat().st_size
    max_length = current_app.config.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024)
    if file_size > max_length:
        if dest_path.exists():
            dest_path.unlink()
        raise ValueError(f"File size exceeds the {max_length // (1024 * 1024)}MB limit.")

    # Integrity verification
    if not validate_file_integrity(dest_path, file_type):
        if dest_path.exists():
            dest_path.unlink()
        raise ValueError("File appears corrupted or unreadable.")

    return {
        "stored_path": str(dest_path),
        "original_filename": original_filename,
        "stored_filename": stored_filename,
        "file_type": file_type,
        "file_size": file_size,
    }


def get_safe_file_path(filename: str, folder_type: str = "prescriptions") -> Path:
    """Resolve file path ensuring no directory traversal."""
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        raise PermissionError("Illegal path traversal attempt detected.")

    if folder_type == "processed":
        base = Path(current_app.config["PROCESSED_FOLDER"])
    else:
        base = Path(current_app.config["UPLOAD_FOLDER"])
    
    target = (base / filename).resolve()
    if not str(target).startswith(str(base.resolve())):
        raise PermissionError("Illegal path traversal attempt detected.")
    return target
