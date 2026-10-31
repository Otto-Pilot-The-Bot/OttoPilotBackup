"""Single place for every tunable. Edit here (or override with env vars)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

NAME = os.environ.get("SPROCKET_NAME", "Otto Pilot")       # the robot's full name (the ONE place to change it)
SHORT_NAME = os.environ.get("SPROCKET_SHORT_NAME", "Otto")  # what the UI and captions call him day to day

MODEL = os.environ.get("SPROCKET_MODEL", "gemma4:e4b")      # the one model setting
FALLBACK_MODEL = os.environ.get("SPROCKET_FALLBACK", "qwen3:8b")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
NUM_CTX = 8192
THINK = False                 # thinking off for the tick loop (speed)
TEMPERATURE = 0.9
KEEP_ALIVE = "30m"

TICK_SECONDS = float(os.environ.get("SPROCKET_TICK", 12))   # start-to-start interval
REFLECT_EVERY = 10            # ticks between reflection calls
REQUEST_TIMEOUT = 90          # seconds per model call

DB_PATH = Path(os.environ.get("SPROCKET_DB", ROOT / "data" / "sprocket.db"))
PUBLISH_DIR = ROOT / "published"   # approved pages are exported here, locally only
KILL_FILE = ROOT / "KILL"          # `touch KILL` stops everything

PUBLISH_ENABLED_DEFAULT = False    # publish_page tool hidden until you switch it on
WORLD_HALF = 24                    # world spans -24..24 on x and z
REACH = 3.0                        # distance needed to use something
MAX_STEP = 10.0                    # max distance walked per tick
MAX_OBJECTS = 120
HOST, PORT = "127.0.0.1", 8765     # localhost only

# --- web reading (read_page) ---
FETCH_TIMEOUT = 10             # seconds, total
FETCH_MAX_BYTES = 600_000      # never download more than this
PAGE_CHARS = 4000              # cleaned text cap
FETCH_PORTS = (80, 443)
# --- making ---
ART_MAX_CHARS = 6000
MAX_PROJECTS = 2


# =====================================================================================================
# BALANCE: every rate and threshold lives here (and is shown in the page under "More").
# All numbers are PER TICK, tuned for ~12 s per tick. Needs run 0..100.
# =====================================================================================================
ENERGY_BASE_DRAIN = 0.05        # just existing
BATTERY_BASE_DRAIN = 0.06
CREATIVITY_DECAY = 0.9          # creativity slowly fades; low creativity = itch to make something
BOREDOM_RISE = 1.4              # boredom creeps up; novel things bring it down
MOVE_COST_PER_UNIT = {"energy": 0.025, "battery": 0.020}      # walking a full 10-unit step costs ~0.25 / 0.20
ACTION_COST = {                 # extra cost when an action is actually carried out: (energy, battery)
    "build": (0.50, 0.35), "make_art": (0.40, 0.30), "interact_with": (0.10, 0.06), "shop": (0.10, 0.06),
    "search_web": (0.03, 0.05), "read_page": (0.02, 0.04), "write_journal": (0.01, 0.02),
    "move_to": (0.0, 0.0), "eat": (0.0, 0.0), "landscape": (0.30, 0.20), "arrange": (0.25, 0.15), "observe": (0.03, 0.04), "make_music": (0.15, 0.10), "tend": (0.15, 0.10), "collect": (0.08, 0.06), "rest": (0.0, 0.0), "publish_page": (0.03, 0.03),
}
REST_RESTORE_HOME = 100.0       # resting at the home pad refills energy completely...
REST_BATTERY_TRICKLE_HOME = 25.0   # ...and trickle-charges the battery
REST_RESTORE_AWAY = 35.0        # resting elsewhere helps, but less
EAT_RESTORE = 90.0              # refuelling at the fuel station refills almost everything
FULL_THRESHOLD = 90.0           # above this, eating/resting does nothing ("already full")
LOW_HINT = 30.0                 # below this the prompt gently suggests looking after the need
VERY_LOW = 12.0                 # below this the hint becomes more direct
COLLAPSE_RECOVER = 45.0         # if a need hits 0 he shuts down briefly and wakes at this level
NEG_MOOD_MAX_TICKS = 4          # a bad mood with no new bad event fades after this many ticks
# Typical mix of what he does in a tick (used only to ESTIMATE run time in the settings panel)
ASSUMED_MIX = {"move_units": 2.4, "build": 0.10, "make_art": 0.05, "light": 0.45}   # avg units walked/tick, share of ticks

# --- pacing: so he doesn't only build ---
MIN_TICKS_BETWEEN_NEW_PROJECTS = 80
MIN_TICKS_BETWEEN_ART = 14
FOCUS_TICKS = 10                # how long a "what I feel like doing" inclination lasts

# --- layout engine ---
WORLD_HALF_MAX = 48
WORLD_GROW_STEP = 6
CROWD_LIMIT = 0.14              # fraction of ground covered before the buildable area grows
SPACING_MARGIN = 0.8            # extra space kept between footprints

# --- assets ---
ASSET_DIRS = ("assets", "assests")      # (the second spelling is accepted because that is how the folder was created)
ASSET_MAX_BYTES = 25_000_000
ASSET_MAX_TRIS = 12_000
ASSET_KEEP_RANGE = (0.4, 6.0)            # models whose longest side is in this range keep their native scale (kit pieces still fit together)
ASSET_TARGET_BY_TAG = {"animal": 1.6, "celestial": 3.0}   # oversized models with these tags are scaled to this size instead
ASSET_FIT_MIN, ASSET_FIT_MAX = 0.6, 5.0   # models outside that range are rescaled into this many world units
BLOCKED_SITE_HOURS = 6                   # how long he remembers a site that refused him
MAX_GOALS = 5                    # active goals kept at once (near-duplicates are merged)
BUILD_WINDOW = (30, 3)           # at most 3 build actions (any stage) in any 30 ticks: builds are an occasional thing
MAKER_PREF_CAP = 1.5             # building/creating/art tastes can never snowball above this

# =====================================================================================================
# PUBLISHING (GitHub Pages). The model only ever queues pages; publisher/publish.py is the ONLY code that reads the token.
# =====================================================================================================
SITE_OWNER = "Otto-Pilot-The-Bot"
SITE_REPO = "Otto-Pilot-The-Bot.github.io"
SITE_BRANCH = "main"
SITE_URL = "https://otto-pilot-the-bot.github.io"
GIT_AUTHOR_NAME = "Otto-Pilot-The-Bot"
GIT_AUTHOR_EMAIL = "350582770+Otto-Pilot-The-Bot@users.noreply.github.com"      # GitHub noreply address of the robot's own account
PUBLISH_MODE_DEFAULT = "dry_run"        # "dry_run": write to ./site_dryrun and show what would be pushed; "live": really push
PUBLISH_MAX_PER_DAY = 3                 # pages that may go out per rolling 24 h
PUBLISH_MAX_PENDING = 5                 # pages waiting for approval at once
PUBLISH_MAX_SUBMISSIONS_PER_DAY = 6     # pages the robot may submit per rolling 24 h
PUBLISH_RETRY_COOLDOWN = 90             # seconds before a failed page may be tried again (never an automatic retry)
PUBLISH_TIMEOUT = 120                   # seconds for the whole publish script
PAGE_MIN_CHARS, PAGE_MAX_CHARS, TITLE_MAX = 40, 8000, 90
DRYRUN_DIR = ROOT / "site_dryrun"
SITE_CLONE_DIR = ROOT / "site"
PRIVATE_TERMS_FILE = ROOT / "data" / "private_terms.txt"   # optional: one word/phrase per line that must never appear on his site (e.g. your real name)
LANDSCAPE_PER_DAY = 8              # landscaping actions per world day (144 ticks)
MAX_GROUND_PATCHES = 14

# --- a full life (Stage 3): activity categories, variety pressure, interests, hobbies ---
CATEGORIES = ("explore", "observe", "learn", "art", "music", "write", "garden", "collect", "socialize", "rest", "build", "organize")
NOVELTY_AFTER = 25               # a category not done for this many ticks feels fresh (novelty bonus, extra boredom relief)
REPEAT_PENALTY = 0.18            # each repeat of the same category in the last 6 actions makes it less rewarding
LATELY_WINDOW = 20               # the "lately you have mostly done..." line looks at this many actions
INTEREST_DECAY_EVERY = 10        # ticks between fading passes
INTEREST_DECAY = 0.95            # strength multiplier per pass for interests that were not touched
INTEREST_MIN = 0.35              # below this an interest has faded away
MAX_INTERESTS = 12
MIN_TICKS_BETWEEN_TUNES = 10
TEND_COOLDOWN = 20               # per plant
MAX_FINDS = 5                    # small found objects lying around at once
FIND_SPAWN_CHANCE = 0.2          # per tick
BUILD_REASON_MIN = 12            # characters

# --- memory recall (local embeddings via Ollama; no cloud) ---
EMBED_MODEL = os.environ.get("SPROCKET_EMBED_MODEL", "nomic-embed-text")
RECALL_K = 4                    # memories shown in the prompt each tick
RECALL_POOL = 800               # most recent memories considered (plus all important ones)
EMBED_BATCH = 16
SNACK_RESTORE = 45.0              # a snack machine refuels less than the fuel station
BENCH_RESTORE = 15.0
ARRANGE_PER_DAY = 6                # arrange jobs per world day (144 ticks)
ARRANGE_MAX_OBJECTS = 8
ATTRACT_DECAY = 0.96             # per tick; things placed in his world pull on him, fading unless he goes to them
