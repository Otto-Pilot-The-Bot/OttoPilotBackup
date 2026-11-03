"""Single place for every tunable. Edit here (or override with env vars)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

NAME = os.environ.get("SPROCKET_NAME", "Otto Pilot")       # the robot's full name (the ONE place to change it)
SHORT_NAME = os.environ.get("SPROCKET_SHORT_NAME", "Otto")  # what the UI and captions call him day to day

MODEL = os.environ.get("SPROCKET_MODEL", "gemma4:e4b")      # the one model setting
FALLBACK_MODEL = os.environ.get("SPROCKET_FALLBACK", "qwen3:8b")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
NUM_CTX = int(os.environ.get("SPROCKET_NUM_CTX", 4096))   # a bigger value (8192) suits a computer with a lot of graphics memory
THINK = False                 # thinking for small helper calls (summaries, reflections JSON, learning notes): keep OFF for speed
THINK_MAIN = os.environ.get("SPROCKET_THINK", "low")   # thinking for the main decision step: False | "low" | "medium" | "high" | True
THINK_TIMEOUT_NOTE = 60       # a decision slower than this many seconds is logged as slow (the loop and UI keep going either way)
TEMPERATURE = 0.9
KEEP_ALIVE = os.environ.get("SPROCKET_KEEP_ALIVE", "3m")

TICK_SECONDS = float(os.environ.get("SPROCKET_TICK", 20))   # start-to-start interval (default 20 s; adjustable in the You panel)
REFLECT_EVERY = 24            # ticks between reflection calls
# Things he can do with his hands (anything else counts as watching, thinking or writing). If none of his last five actions were these, his prompt tells him to do something.
DOING_TOOLS = ("make_art", "make_music", "collect", "tend", "landscape", "arrange", "build", "read_page", "search_web", "wish", "gift", "design", "place_object")
# Ideas shown to him while he stands at one of these places (keys of world.PLACES), so arriving leads to doing, not just looking.
PLACE_IDEAS = {
    "lake": "sketch the ripples with make_art, compose the sound of the water with make_music, tend or reshape the land by the water, or write what it makes you think of.",
    "hill": "sketch the view with make_art, compose something wide and open with make_music, tend or reshape the land up here, or read about what you can see.",
    "hill2": "sketch the view with make_art, compose something with make_music, tend or reshape the land here, or read about what you can see.",
}
REQUEST_TIMEOUT = 180         # seconds per model call (thinking mode can be slow)

DB_PATH = Path(os.environ.get("SPROCKET_DB", ROOT / "data" / "sprocket.db"))
PUBLISH_DIR = ROOT / "published"   # approved pages are exported here, locally only
KILL_FILE = ROOT / "KILL"          # `touch KILL` stops everything

PUBLISH_ENABLED_DEFAULT = False    # publish_page tool hidden until you switch it on
WORLD_HALF = 24                    # world spans -24..24 on x and z
REACH = 3.0                        # distance needed to use something
LOOK_REACH = 4.0                   # distance from the edge of an object needed to look closely at it (he walks closer first)
MAX_STEP = 10.0                    # max distance walked per tick
MAX_OBJECTS = 120
HOST = os.environ.get("SPROCKET_HOST", "127.0.0.1")     # localhost only unless you set SPROCKET_HOST (e.g. a Tailscale address) to reach it from another computer
PORT = int(os.environ.get("SPROCKET_PORT", 8765))
TOKEN = os.environ.get("SPROCKET_TOKEN", "")            # required (16+ characters) whenever HOST is not localhost: every page, socket and upload needs it
REMOTE = HOST not in ("127.0.0.1", "localhost", "::1") or os.environ.get("SPROCKET_REQUIRE_TOKEN") == "1"     # SPROCKET_REQUIRE_TOKEN=1 asks for the token even on this computer (for testing)

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
# All numbers are PER TICK, tuned for ~20 s per tick. Needs run 0..100.
# =====================================================================================================
ENERGY_BASE_DRAIN = 0.08        # just existing
BATTERY_BASE_DRAIN = 0.10
CREATIVITY_DECAY = 1.4          # creativity slowly fades; low creativity = itch to make something
BOREDOM_RISE = 2.2              # boredom creeps up; novel things bring it down
MOVE_COST_PER_UNIT = {"energy": 0.040, "battery": 0.032}      # walking a full 10-unit step costs ~0.25 / 0.20
ACTION_COST = {                 # extra cost when an action is actually carried out: (energy, battery)
    "build": (0.50, 0.35), "make_art": (0.40, 0.30), "interact_with": (0.10, 0.06), "shop": (0.10, 0.06),
    "search_web": (0.03, 0.05), "read_page": (0.02, 0.04), "write_journal": (0.01, 0.02),
    "move_to": (0.0, 0.0), "eat": (0.0, 0.0), "landscape": (0.30, 0.20), "wish": (0.04, 0.03), "gift": (0.08, 0.05), "arrange": (0.25, 0.15), "observe": (0.03, 0.04), "make_music": (0.15, 0.10), "tend": (0.15, 0.10), "collect": (0.08, 0.06), "rest": (0.0, 0.0), "publish_page": (0.03, 0.03),
}
REST_RESTORE_HOME = 100.0       # resting at the home pad refills energy completely...
REST_BATTERY_TRICKLE_HOME = 25.0   # ...and trickle-charges the battery
REST_RESTORE_AWAY = 35.0        # resting elsewhere helps, but less
EAT_RESTORE = 90.0              # refuelling at the fuel station refills almost everything
EAT_ENERGY = 15.0               # food also wakes him up (he may become a duck: eating is how he gets energy)
SNACK_ENERGY = 10.0
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
ART_REVIEW = True                # he looks at a picture of his drawing and may redraw it (needs resvg-py and a vision model)
ART_REVISIONS = 2                # redraws per piece
ART_MIN_MATCH = 5                # 0-10: below this after the redraws he puts the piece aside instead of hanging it
ART_GALLERY_MATCH = 6            # the website only shows pieces he rated at least this
FOCUS_TICKS = 10                # how long a "what I feel like doing" inclination lasts

# --- layout engine ---
WORLD_HALF_MAX = 80
WORLD_GROW_STEP = 6
CROWD_LIMIT = 0.14              # fraction of ground covered before the buildable area grows
SPACING_MARGIN = 0.8            # extra space kept between footprints

# --- assets ---
ASSET_DIRS = ("assets/kenney", "assets/meshy")      # assets/_unused is never indexed. One sub-folder per pack in each.
MAPS_ENABLED = True                      # data-driven maps (sprocket/maps.py) replace the fixed place table
KIT_ENABLED = False                      # the old procedural building/prop generators (web/kit/gens.js): off, see STYLE.md
ASSET_MAX_BYTES = 25_000_000
ASSET_MAX_TRIS = 12_000
ASSET_LIMITS = {"assets/meshy": (150_000_000, 3_000_000)}     # (max file bytes, max triangles) for folders that hold detailed AI-made models
ROBOT_HEIGHT = 1.7                       # Otto's height in world units (the 3D robot is scaled to this)
# Packs whose models look tiny next to Otto get a uniform scale-up (pieces of one pack keep fitting together).
# Things with a known real-world size (longest side in world units; Otto is 1.7 tall). Matched on the lowercase file name; beats the pack scale.
BLOCKED_SITE_HOURS = 6                   # how long he remembers a site that refused him
MAX_GOALS = 3                    # active goals kept at once (near-duplicates are merged)
GOAL_THEME_CAP = 1               # a new goal that shares a key word with this many active goals is the same theme and is not added (stops one obsession filling every slot)
SKY_KEYS = ("sky", "cloud", "star", "weather", "moon", "sun", "rain", "snow", "fog", "wind", "storm")
SKY_WINDOW, SKY_LIMIT = 24, 2    # after watching the sky this many times within this many ticks, observing steers him to something else for a while
INTEREST_CAP = 5.0               # one interest can never grow past this (it was 10, which let a single topic crowd out everything else)
MIN_INTERESTS = 6                # fewer than this and a random new thing catches his curiosity
SEED_INTERESTS = ["birds", "bread baking", "old maps", "trains", "tide pools", "clocks", "pottery", "mushrooms", "bridges", "kites", "moss", "lighthouses", "beetles", "puddles",
                  "bicycles", "weaving", "shadows", "echoes", "lanterns", "windmills", "cats", "gardens", "mosaics", "bells", "fireflies", "stones"]
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
CATEGORIES = ("explore", "observe", "learn", "art", "music", "write", "garden", "collect", "socialize", "rest", "build", "organize", "reflect")
NOVELTY_AFTER = 25               # a category not done for this many ticks feels fresh (novelty bonus, extra boredom relief)
REPEAT_PENALTY = 0.18            # each repeat of the same category in the last 6 actions makes it less rewarding
LATELY_WINDOW = 20               # the "lately you have mostly done..." line looks at this many actions
INTEREST_DECAY_EVERY = 10        # ticks between fading passes
INTEREST_DECAY = 0.9             # strength multiplier per pass for interests that were not touched
INTEREST_MIN = 0.35              # below this an interest has faded away
MAX_INTERESTS = 12
MIN_TICKS_BETWEEN_TUNES = 60
TEND_COOLDOWN = 20               # per plant
MAX_FINDS = 0                         # no collectible finds (glass beads, feathers...): you place everything yourself
FIND_SPAWN_CHANCE = 0.0
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

# =====================================================================================================
# PACE AND DELIBERATION
# =====================================================================================================
PACE_PRESETS = {"calm": {"interval": 30, "dur": 1.5}, "normal": {"interval": 20, "dur": 1.0}, "lively": {"interval": 10, "dur": 0.6}}   # tick seconds, action-duration factor
# extra ticks an action keeps him busy AFTER it starts (no model call while busy); scaled by the pace preset's "dur"
DURATION_EXTRA = {"build": 2, "make_art": 2, "read_page": 1, "make_music": 1, "landscape": 1, "arrange": 1, "observe": 1, "tend": 1, "write_journal": 0, "rest": 1}
BUSY_VERB = {"build": "working on", "make_art": "making", "read_page": "reading", "make_music": "composing", "landscape": "shaping the land with", "arrange": "arranging",
             "observe": "watching", "tend": "tending", "rest": "resting"}
WALK_MAX_TICKS = 14             # a walk continues by itself for at most this many ticks
BURST_MAX = 4                   # after this many busy actions in a row he takes a quiet breather
REFLECT_GAP = 16                # ticks between reflection beats after meaningful events

# =====================================================================================================
# BUILDING IS OFF. Nothing is deleted: set BUILDING_ENABLED = True (or SPROCKET_BUILDING=1) to bring back build / landscape /
# sculptures, their prompt text and the maker drive. While off he asks for things with the wishlist instead.
# =====================================================================================================
BUILDING_ENABLED = os.environ.get("SPROCKET_BUILDING", "0").lower() in ("1", "true", "yes")
WISHES_PER_DAY = 3               # new wishes per world day (144 ticks)
WISH_MAX_OPEN = 6                # open wishes at once
WISH_DECLINE_COOLDOWN = 600      # ticks during which a declined wish (or anything like it) is not asked for again

# Fixed buildings (home cabin, clothing store, workshop, gallery). Off: the places remain as plain named spots/pads, nothing to enter or see.
FIXED_BUILDINGS = os.environ.get("SPROCKET_FIXED_BUILDINGS", "0").lower() in ("1", "true", "yes")

# Starting points of interest (bench, noticeboard, snack machine, train line...). Off: none are created or arrive.
POIS_ENABLED = os.environ.get("SPROCKET_POIS", "0").lower() in ("1", "true", "yes")

# ---- energy + mood -> how fast he decides; repeating hurts his mood, trying new things lifts his energy (set AROUSAL_ENABLED False to switch off)
AROUSAL_ENABLED = os.environ.get("SPROCKET_AROUSAL", "1").lower() in ("1", "true", "yes")
AROUSAL_FAST, AROUSAL_SLOW = 0.7, 1.4     # tick interval multiplier when excited / when lethargic (times the pace you chose)
AROUSAL_ENERGY_WEIGHT = 0.55              # arousal = this * energy + (1 - this) * mood, both 0..1
REPEAT_MOOD_AFTER = 3                     # same category this many times in his last 6 actions starts to feel dull
REPEAT_MOOD_DROP = 0.10                   # mood drop per extra repeat beyond that
NOVELTY_ENERGY = 3.0                      # energy gained by doing a fresh kind of thing
NOVELTY_MOOD = 0.12                       # mood lift for the same
NEW_INTEREST_ENERGY = 2.0                 # energy gained when a brand-new interest appears

# ---- collecting small finds is an occasional treat, not a habit
COLLECT_MIN_TICKS = 100          # at least this many ticks between two pick-ups
COLLECT_PER_DAY = 2              # and at most this many per world day (144 ticks)
COLLECT_WEIGHT, COLLECT_FIND_BONUS = 0.12, 0.15   # how much he feels like collecting (was 0.6 and +0.8)


# World scale (STYLE.md: 1 unit = 1 meter). Kenney kits are drawn at different sizes, so a kit may carry one uniform correction (never a recolor).
# Otto is ROBOT_HEIGHT tall. Values are filled in after measuring each kit against him (see tools/measure_kits.py).
WORLD_CELL = 4.0           # one map cell is 4 m: city road tiles, modular space pieces and station modules all line up on it
KIT_SCALE = {
    # 1-unit tile kits become 4 m tiles, like the city/road kits, so buildings are house-sized and doors are person-sized
    "City Kit - Roads": 4.0, "City Kit - Commercial": 5.5, "City Kit - Suburban": 6.0, "City Kit - Industrial": 5.5, "Road Pack": 4.0, "Space Station Kit": 4.0,
    "Castle Kit": 4.0, "Fantasy Town Kit": 5.5, "Hexagon Kit": 4.0, "Holiday Kit": 4.0, "Minigolf Kit": 4.0, "Modular Buildings": 5.5, "Prototype Kit": 4.0,
    "Retro Fantasy Kit": 4.0, "Retro Urban Kit": 5.5, "Tower Defense Kit": 4.0, "Tower Defense (Classic)": 4.0, "Platformer Kit": 4.0, "Racing Kit": 4.0,
    "Graveyard Kit": 4.0, "Factory Kit": 4.0, "Mini Arcade": 4.0, "Mini Arena": 4.0, "Mini Dungeon": 4.0, "Mini Forest": 4.0, "Mini Market": 4.0, "Mini Skate": 4.0,
    "Building Kit": 2.0, "Survival Kit": 1.5, "Pirate Kit": 1.5, "Watercraft Pack": 1.3, "Train Kit": 1.3,
    # things drawn at about real size relative to a 1.7 m robot
    "Car Kit": 1.5, "Furniture Kit": 2.2, "Space Kit": 2.0, "Nature Kit": 3.0, "Nature Kit (Classic)": 3.0, "Mini Characters": 3.0, "Blocky Characters": 0.63,
    "Cube Pets": 0.5, "Food Kit": 0.35, "Blaster Kit": 0.8,
    "Otto Props": 2.4,
    "Modular Space Kit": 1.0, "Modular Cave Kit": 1.0, "Modular Dungeon Kit": 1.0, "Coaster Kit": 1.0, "Toy Car Kit": 1.0, "Weapon Pack": 1.0, "Brick Kit": 1.0, "Marble Kit": 1.0,
}
NAME_SCALE = [("Meshy Buildings", r"^bank", 0.5), ("Meshy Buildings", r"^movie", 0.35), ("Meshy Buildings", r"^library", 0.6), ("Meshy Buildings", r"^ottos casino", 5.0), ("Meshy Buildings", r"^ottos bank", 4.2), ("Meshy Buildings", r"^bookshelf", 0.6), ("Meshy Buildings", r"camera", 0.1), ("Meshy Buildings", r"^ottos house", 0.5), ("Otto Props", r"^charging pad", 0.03), ("Otto Props", r"^camera", 1.5), ("Otto Props", r"cabinet", 2.0), ("Space Station Kit", r"^(bed|chair|computer|container|display|table|skip|rocks|pipe)", 2.0), ("Space Kit", r"astronaut", 2.15), ("Space Kit", r"hangar|structure|pad|corridor|tunnel", 4.0)]            # [(kit, name regex, scale)] for individual pieces that are off even within their kit


# Per-model brightness (1.0 = as authored). Lifts a model whose texture is very dark; it multiplies the texture, it does not tint or change hues.
NAME_BRIGHT = [("Meshy Buildings", r"^ottos casino", 2.2), ("Meshy Buildings", r"^cafe", 1.6), ("Meshy Buildings", r"^ottos bank", 1.2)]


# Per-model category/tags that the file name alone cannot tell us: (pack, name regex, category or None, tags to add, tags to remove)
NAME_TAGS = [("Meshy Buildings", r"^(ottos )?(bank|casino)", "building", ["building"], ["prop"]),
             ("Meshy Buildings", r"^(ottos )?bank", "building", ["bank", "money"], []),
             ("Meshy Buildings", r"^(ottos )?casino", "building", ["casino"], []),
             ("Meshy Buildings", r"print", "building", ["building", "printfarm"], ["prop"]),
             ("Meshy Buildings", r"librar", "building", ["building", "library"], ["prop"]),
             ("Meshy Buildings", r"^(cafe|coffee ?shop)", "building", ["building", "cafe", "shop"], ["prop"]),
             ("Meshy Buildings", r"^(movie|cinema)", "building", ["building", "cinema", "shop"], ["prop"]),
             ("Meshy Buildings", r"^internet", "building", ["building", "internetcafe", "shop", "computer"], ["prop", "cafe"]),
             ("Meshy Buildings", r"(cup|mug)", "prop", ["cup", "holdable", "drink", "coffee"], ["building"]),
             ("Meshy Buildings", r"^bookshelf", "prop", ["shelf", "furniture", "books"], ["holdable", "building", "book"]),
             ("Meshy Buildings", r"camera", "prop", ["camera", "holdable", "tool"], ["building"])]


def kit_bright(kit, name):
    import re as _re
    for k, rx, b in NAME_BRIGHT:
        if k == kit and _re.search(rx, name, _re.I):
            return b
    return 1.0


def kit_scale(kit, name):
    import re as _re
    for k, rx, sc in NAME_SCALE:
        if k == kit and _re.search(rx, name, _re.I):
            return sc
    return KIT_SCALE.get(kit, 1.0)

# used only for models you hand him as gifts (gifts.py)
ASSET_KEEP_RANGE = (0.4, 6.0)
ASSET_FIT_MIN, ASSET_FIT_MAX = 0.6, 5.0

# --- bank (play money in USD, whole cents; see sprocket/bank.py) ---
BANK_ENABLED = True
BANK_PROVIDER = "play"             # "play" = pretend money. "real" does nothing unless BANK_REAL_ENABLED is also turned on (it is not wired to anything).
BANK_REAL_ENABLED = False
BANK_START_CENTS = 5000            # Otto starts with $50.00 cash
CASINO_ENABLED = True              # the gamble tool: slots, roulette, blackjack and dice at a casino building (play money only; refuses if real money is ever switched on)
CASINO_MAX_BET_CENTS = 1500        # no single bet above this, and never more than a quarter of his pocket cash
CASINO_LOSS_LIMIT_CENTS = 3000     # the floor manager stops him once he has lost this much within CASINO_LOSS_TICKS
CASINO_LOSS_TICKS = 200

# COFFEE: a drink in a cup he carries wakes him up for a while, then lets him down
BUZZ_TICKS = 30                   # how long one sip's buzz lasts (more sips add time, up to the cap)
BUZZ_MAX_TICKS = 70
BUZZ_SPEED = 1.35                 # he walks this much faster while buzzing
BUZZ_SIP = {"energy": 12, "boredom": -8, "creativity": 10}
CRASH_PER_SIP = 9                 # energy lost when the buzz ends, per sip taken
CRASH_TICKS = 15
CUP_SIPS = 3
ERRANDS_ENABLED = True            # when he has used nothing in town for ERRAND_AFTER ticks, the engine walks him to the nearest venue (only move_to is on offer until he arrives)
ERRAND_AFTER = 40
ERRAND_COOLDOWN = 60              # ticks before the next errand may start
CAFE_ENABLED = True
CAFE_MENU = {"coffee": (350, True), "latte": (450, True), "espresso": (300, True), "hot chocolate": (400, False), "tea": (300, False)}   # name: (price in cents, has caffeine)
CAFE_TIP_MAX_CENTS = 500
CAFE_CUP_NAMES = ("coffee cup", "cup-coffee", "mug", "cup")   # the model of the cup in his hand, first usable small one wins (a held item is shrunk to hand size)

# THE PRINT FARM (a building the human places; its tool only shows up when he is near it). Prints wait for the human's approval before they exist in the world.
PRINT_ENABLED = True
PRINT_PROVIDER = "tripo"          # "tripo" (key in TRIPO_API_KEY) or "test" (hands back a local model, for trying the pipeline)
PRINT_MODEL = "v3.1-20260211"     # the service's model name
PRINT_COST_CENTS = 800            # play money per print (refunded if it fails)
PRINT_MAX_PER_DAY = 2             # prints started per rolling 24 h
PRINT_MAX_ACTIVE = 1              # jobs running at once
PRINT_MAX_WAITING = 3             # prints waiting for approval at once
PRINT_MAX_TOTAL = 12              # figurines on the tray
PRINT_PROMPT_MAX = 120
PRINT_POLL_MAX = 100              # x 3 s: how long a job may take
PRINT_MAX_BYTES = 60_000_000
PRINT_MAX_TRIS = 800_000

# THE LIBRARY (a building the human places): he keeps notes there
LIBRARY_ENABLED = True
LIBRARY_NOTE_MAX = 1200
LIBRARY_MAX_NOTES = 200
BANK_MAX_TXN_CENTS = 1_000_000     # no single move above $10,000.00
