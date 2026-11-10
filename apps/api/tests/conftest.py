import os
import sys
import tempfile
from pathlib import Path

API_ROOT = str(Path(__file__).resolve().parents[1])
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)

# Use an isolated SQLite database for integration tests.
TEST_DB = Path(tempfile.gettempdir()) / "aiqms_pytest.db"
try:
    TEST_DB.unlink()
except FileNotFoundError:
    pass
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["DEV_AUTH_ENABLED"] = "true"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"
