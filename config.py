import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Auth
COOKIES_FILE = Path(os.getenv("COOKIES_FILE", DATA_DIR / "myheritage_cookies.json"))
SESSION_FILE = Path(os.getenv("SESSION_FILE", DATA_DIR / "myheritage_session.json"))

# Decision thresholds
CONFIDENCE_THRESHOLD = int(os.getenv("CONFIDENCE_THRESHOLD", "80"))

# Rate limiting (seconds)
# Inter-action (within wizard): generous to avoid Angular race conditions
ACTION_DELAY_MIN = 3.0
ACTION_DELAY_MAX = 9.0
# Inter-match: short enough that macOS doesn't kill the headless Chromium process
MATCH_DELAY_MIN = 8.0
MATCH_DELAY_MAX = 18.0
# Inter-person: short enough to keep Chromium alive between people
PERSON_DELAY_MIN = 15.0
PERSON_DELAY_MAX = 30.0

# Session cap. 100 is the efficiency optimum: the discovery-hub list only surfaces
# ~100 confirmable matches per pass, so larger caps add error volume, not confirmed
# saves (2026-06-26 postmortem: MAX=300 bought +3 confirmed for +400 errors).
# 500 remains the hard safety ceiling in CLAUDE.md. See wiki/concepts/session-economics.md.
MAX_MATCHES_PER_SESSION = int(os.getenv("MAX_MATCHES_PER_SESSION", "100"))

# Browser config — viewport slight randomization happens at runtime
VIEWPORT = {"width": 1440, "height": 900}
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.7103.114 Safari/537.36"
)

# MyHeritage URLs
BASE_URL = "https://www.myheritage.com"
SMART_MATCHES_URL = f"{BASE_URL}/smart-matches"
RECORD_MATCHES_URL = f"{BASE_URL}/record-matches"
DISCOVERIES_URL = f"{BASE_URL}/discoveries"

# Database
DB_FILE = DATA_DIR / "agent.db"
GRAPH_UPDATES_FILE = DATA_DIR / "graph_updates.jsonl"

# Extraction priority order (what to save when enriching)
EXTRACTION_PRIORITY = [
    "birth_date",
    "birth_place",
    "death_date",
    "death_place",
    "photos",
    "relatives",
    "sources",
    "newspapers",
    "obituaries",
]

# What triggers a manual review flag instead of auto-save
CONFLICT_FLAGS = [
    "name_mismatch",
    "date_conflict",
    "relationship_restructure",
]
