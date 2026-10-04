import pytest
from app.utils.file_handler import get_safe_file_path
from app import create_app
from config import TestingConfig


def test_directory_traversal_prevention():
    """Verify get_safe_file_path blocks path traversal attempts."""
    app = create_app(TestingConfig)
    with app.app_context():
        # Valid safe filename
        safe_path = get_safe_file_path("test_image.jpg")
        assert "uploads" in str(safe_path)

        # Directory traversal attempt
        with pytest.raises(PermissionError):
            get_safe_file_path("../../Windows/System32/cmd.exe")


def test_no_stack_traces_on_error(client=None):
    """Ensure error handlers return clean user-facing pages without raw stack traces."""
    app = create_app(TestingConfig)
    client = app.test_client()

    response = client.get("/non-existent-endpoint-404")
    assert response.status_code == 404
    assert b"Page Not Found" in response.data
    assert b"Traceback" not in response.data
