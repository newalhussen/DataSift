import os
import tempfile
from pathlib import Path

MAX_UPLOAD_BYTES = int(float(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024)
MAX_ROWS = int(os.getenv("MAX_ROWS", "200000"))
MAX_COLUMNS = int(os.getenv("MAX_COLUMNS", "200"))
TTL_SECONDS = int(os.getenv("DATASET_TTL_MINUTES", "60")) * 60
MAX_DATASETS = int(os.getenv("MAX_DATASETS", "50"))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(Path(tempfile.gettempdir()) / "datasift")))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
