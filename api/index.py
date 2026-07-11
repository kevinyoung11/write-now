import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

if "DATABASE_URL" not in os.environ and os.environ.get("SUPABASE_DB_URL"):
    os.environ["DATABASE_URL"] = os.environ["SUPABASE_DB_URL"]
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/write_agent.db")
os.environ.setdefault("COVER_STORAGE_DIR", "/tmp/write_agent_covers")
os.environ.setdefault("OBS_LOG_DIR", "/tmp/write_agent_observability")
os.environ.setdefault("CHROMA_DIR", "/tmp/write_agent_chroma")
os.environ.setdefault("XHS_TRENDS_CACHE_FILE", "/tmp/write_agent_xhs_trends_cache.json")
os.environ.setdefault("ENABLE_SCHEDULERS", "false")
os.environ.setdefault("BOOTSTRAP_DEFAULT_DATA", "false")

from write_agent.main import app
