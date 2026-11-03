# Otto Pilot: project handoff (read this first)

Written 3 Nov 2026 so a different Claude account/session can pick up exactly where this one stopped. README.md and STYLE.md cover the older foundations; this file covers the current state, how we work, and what is next. No secrets are in this file (never put any here).

## What this is
"Otto" (package/db still named `sprocket`) is an autonomous robot living in a 3D town. A local model (Ollama `gemma4:e4b`) decides what he does each tick. The human (Dru) never commands him; they only change his world (place buildings, give money, approve things). Server: Python (`sprocket/`). Page: Three.js (`web/`). Everything runs on Dru's Windows PC at `D:\Git-Projects\OTTO PILOT BOT\OTTO PILOT`, reached over Tailscale on port 8765.

## The rules Dru has set (follow them)
- **Otto decides for himself.** Never script what he says, draws or does. Give him information, consequences and feedback, not instructions. No copying another bot's (Pino's) drawings, no template designs.
- **Server runs on its own.** Start/stop only with `powershell -File tools\server.ps1 start|stop|restart` (WMI-detached). Never run it as a background task of a Claude session (it died overnight that way). Check afterwards that port 8765 answers (401 without a token is normal).
- **Secrets:** never read or print `.env`; the access token lives in the Windows user variable `SPROCKET_TOKEN`; `TRIPO_API_KEY` goes in `.env` (Dru adds it). Don't touch safety features (sanitisers, publish approval, kill switch).
- **Commits:** commit locally only when Dru says "commit it". The repo has **no remote**. Dru will create a backup GitHub repo ("tomorrow" relative to 3 Nov); connect and push only when told. `data/` and `assets/meshy/**/*.glb` are git-ignored, so back those up separately (use the sqlite3 backup API for the DB, not a file copy: WAL).
- **STYLE.md:** don't recolor/tint models; ask before changing ground, lighting mood or day/night look. Only Dru places objects; Otto can wish, never place.
- **Notion:** Dru keeps a page "Otto Pilot" (id `40d34248-8929-813b-b0bd-f237764190dc`) as the to-do/idea list. After finishing work, tick items and append to "Done recently". Fetch the page first (bold = `<b>`, code = `<code>`, `$` escaped).
- Publishing to the web or anything outward-facing needs explicit permission.
- Style of replies: terse (caveman mode was on in this session); code and commit messages normal.

## Run it
- Normal: `powershell -File tools\server.ps1 restart` (log: `data\server.log`, UTF-16, read with `Get-Content`). Needs `ollama serve` with `gemma4:e4b`, `nomic-embed-text`.
- Python env: `.venv\Scripts\python.exe` (has `resvg_py`, PIL; the system Python does not, so run tests with the venv).
- Config: `sprocket/config.py` (all tunables). Token: `SPROCKET_TOKEN` user variable.

## Architecture (files that matter)
| File | Role |
|---|---|
| `sprocket/agent.py` | The brain loop: builds the prompt, filters tools by situation, world step, errands, buzz/crash, needs |
| `sprocket/tools.py` | Every tool he can call (registry at bottom): move_to, eat, rest, use, make_art, make_music, order, drink, watch, work, library, print3d, bank, gamble, wish, etc. |
| `sprocket/config.py` | All settings, asset NAME_TAGS/NAME_SCALE/NAME_BRIGHT regex rules |
| `sprocket/maps.py` | Map docs (`data/maps/mine.json`), A* paths, clean/caps (MAX_CELLS 40, WORLD_HALF_MAX 80), places |
| `sprocket/affordances.py` | Tag-based object actions (`use`) |
| `sprocket/assets.py` | Model index (`INDEX_VERSION`, now 26) with tags/scale/limits |
| `sprocket/bank.py` | Append-only play-money ledger. MINT is the source of all money; only Dru grants/takes back. Kinds: grant, allowance, wage, sale, cafe, tip, cinema, print, bet, ... |
| `sprocket/artlook.py` | Art critique/redraw loop (vision), lessons, progress |
| `sprocket/sketchstyle.py` | Marker-style render of his SVG drawings (stored as data-URL image, original in `art.source`) |
| `sprocket/cinema.py` | Nine invented films, three shown per day (horror/comedy/action) |
| `sprocket/printfarm.py` | Tripo v3 3D-print adapter + quarantine/approval queue (unverified against the real service: no key yet) |
| `sprocket/db.py` | SQLite schema + migrations (add columns in the tuple list in `__init__`) |
| `sprocket/server.py`, `admin.py` | HTTP/WebSocket server, admin panels (bank, prints, wishes) |
| `web/*.js` | Page: `main.js`, `editor.js` (map editor, favourites, wall snap), `mapview.js`, `models.js`, `art.js`, `weather.js`, `camera.js` |
| `tools/server.ps1` | Detached server launcher |
| `tools/make_trees.py` | Generates leaf-card trees via Blender |
| `publisher/` | Otto's website publishing (dry-run by default) |

## The world and economy (current state)
- Map `mine` (36x36 cells, 4 m each). Placed: Ottos House (home), Cafe, Bank, Casino, Movie Theatre, Library, Internet Cafe, Hotel, charging pad, gallery, trees, lake/hills (terrain-derived places). 3D Print Farm model is indexed but **not placed yet**.
- Buildings get behaviour from **tags** (set by NAME_TAGS from the model's name): cafe, cinema, library, printfarm, bank, home... The tools of a special building only exist for him within ~14-16 m of it (`tools.near_building`).
- **Errands:** if he uses nothing in town for 40 ticks the engine restricts him to `move_to` and sends him to the nearest unused venue.
- **Money:** starts $50. Spends: cafe drinks/bagel, tips, cinema $1.50, prints, casino. Earns: art sales ($10 for score 5-7, $20 for 8-10, paid when the drawing is saved), `work` shifts ($2, -15 energy, 20-tick cooldown, only at cafe/cinema/library/bank), $2 daily allowance from his human (world day = 144 ticks). The prompt warns him when money is low/zero.
- **Cafe:** drinks have caffeine -> buzz (faster, restless) then sugar crash; bagel is carried food eaten in bites.
- **Cinema:** each watch, the model writes his own review/rating/topics (never scripted); saved to journal, memory, interests.

## Drawing: how he learns (built 3 Nov, just deployed, not yet observed live)
Goal from Dru: he must actually learn to draw better without being told how.
1. He draws; his vision pass describes the picture blind and compares to the intent (`critique`), redraws up to `ART_REVISIONS` times.
2. `artlook.reflect` runs after a drawing: if a redraw jumped the score by 2+, if it failed, if it worked first time at 8+, or if an earlier drawing of the same subject exists (title words in common), he compares the two pictures (order randomised) and writes ONE short note to his future self **in his own words**. Stored in table `art_lessons`.
3. The best and newest notes come back as "Things you have noticed about your own drawing" in his main prompt (`YOUR DRAWING:`), in the redraw prompt, and when he asks for the starting sketch.
4. Tracking: `art.first_score`, `art.rounds`; `artlook.progress(db)` gives average score of last 10 vs previous 10. **Check it after a day or two** to see whether scores climb.
5. Later (Dru said "we will do 3 after"): a practice/study mode where he draws a real render of the scene and gets an objective comparison score, still with no "do X" advice.
Config: `ART_LEARN`, `ART_REVIEW`, `ART_REVISIONS`, `ART_MIN_MATCH`, `ART_MARKER_STYLE`.

## Open items / backlog
- Dru creates a backup GitHub repo; then add remote and push when told. Back up `data/` and the large model files separately.
- Place the 3D Print Farm model in the map editor; Dru adds `TRIPO_API_KEY` to `.env`; test the Tripo adapter for real.
- Notion: the "Movie Theatre works" line is stale (says eight films / three showing; now nine films, one each of horror/comedy/action) and recent work is not all recorded (hotel shrink, work/allowance, art-learning). Dru once rejected a Notion edit attempt: offer before editing.
- He is "focused on the hills" per Dru: stats showed hills ~13% of arrivals; likely cause is that lake/hills are the only scenery he is handed for drawing, plus prompt nudges naming the hill. Waiting for Dru to say what they see before changing prompts.
- Observed oddities: he sometimes calls a non-existent `browse` tool at shops; Otto's battery was nearly empty at one check; Casino/House have see-through BLEND materials (offered to patch).
- Backlog (on Notion): clock tower and sense of time, venue system for more food places, duck conversion, night routine/sleeping (interiors much later), real Internet Cafe function (web search only there), Sketchbook as a real sketchbook, automatic daily DB backup (sqlite3 backup API), Mac mirroring.

## Gotchas learned the hard way
- Editor raycasts need `updateMatrixWorld(true)` first. Map padding must use `maps.H_ZERO` chars, not ints.
- Model URLs use `/asset/{id}?v=2` and the server sends `no-cache`; if a model looks stale, bump `?v=`.
- In Python heredocs, `\n` inside f-strings can turn into real newlines when text is generated through a non-raw string: always `py_compile` after editing.
- Building exports from Blender: the whole scene can get exported instead of one object; check triangle counts. Heavy models: ASSET_LIMITS 150 MB / 3M tris; textures were shrunk to 1K for the hotel.
- `art` rows for marker-style drawings have `mode='image'` (JPEG data URL); the original SVG is in `source`.
- Commits end with the Claude co-author line given by the harness; the current commit chain is local only (latest known: `ad6a2b3` income; art-learning work after it may be uncommitted: run `git status`).

## Memory files (Claude auto-memory, per account)
`C:\Users\Dru\.claude\projects\D--Git-Projects-OTTO-PILOT-BOT-OTTO-PILOT\memory\` holds the Notion and server preferences. A different account will not have them; this file replaces them.
