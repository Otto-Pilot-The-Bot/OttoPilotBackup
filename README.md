# Otto Pilot (Otto)

Otto Pilot ("Otto" for short, formerly called Sprocket) is an autonomous robot living in a 3D world, thinking locally with Ollama. You never give commands, you can only change his world. The name is one setting (`NAME` / `SHORT_NAME` in `sprocket/config.py`); the project folder, `sprocket/` package and database file keep their old names on purpose.

## Run
    ./run.sh            # tick loop + 3D world at http://127.0.0.1:8765
    ./run.sh run        # terminal only (add --ticks 5 --interval 2 for a quick test; --interval is not saved)
    ./run.sh journal    # read his journal      ./run.sh status   # needs, goals, tastes

Requires `ollama serve` running with `gemma4:e4b` pulled. Model, name, tick speed, context size: `sprocket/config.py`
(or env: `SPROCKET_MODEL`, `SPROCKET_FALLBACK`, `SPROCKET_NAME`, `SPROCKET_TICK`, `SPROCKET_DB`). Fallback `qwen3:8b` is only used if the
main model errors, and must be pulled separately (`ollama pull qwen3:8b`).

## The page
Top bar: name, mood, live meters (energy, battery, creativity, boredom), in-world clock (a day is 144 ticks; sky and lamps follow it).
Right-hand round buttons, one panel at a time:
- **His diary** (newest first, "2m ago"), **What he's doing** (goal, project stage, recent actions), **His things** (gallery, built items, wardrobe, sketchbook)
- **Browsing** (every search and page read, with his note on what he learned), **Leave him something** (place objects), **You** (pause, tick speed, publish approvals, kill switch), **More** (settings, camera, raw log)
Bottom centre: one-line caption of what he is doing/thinking.

## What he can do (tools)
move_to, eat, rest, search_web, **read_page**, write_journal, interact_with, shop, **build**, **make_art**, publish_page (off unless you enable it).
- **read_page(url)**: GET-only, public http/https text pages. After reading, a second model call has him write a note (journal + memory), pick up interests, and maybe a goal or sketchbook idea. Everything lands in the `reads` table.
- **build**: projects go blueprint -> gather -> build -> finish (visible on the workshop table). Finishing gives a mood boost and a lasting memory; mishaps are mild and become "lessons". He starts with strong building/creating tastes and a **creativity** need that falls over time, so he gets the itch to make things. Negative feelings about making things are never turned into avoidance.
- **make_art**: `drawing` (SVG, or canvas JS), `pixel` (letter grid + palette), `sculpture` (list of primitive shapes, stands in front of the gallery). Pieces hang in the gallery wall (latest 8 flat works) and appear under "His things". His favourite colours and styles accumulate from what he makes and sees.

## The builder kit (code-driven buildings and landscape)
- `sprocket/kit.py` is the catalog (house, cottage, tower, shop, workshop_building, tree, bush, rock, fence, lamp, path, pond, flower_bed, sign, car); the geometry is `web/kit/gens.js` (flat-shaded low-poly, palette and seasons adapted from the read-only `reference/city` project, which is git-ignored and never modified). Parameters are validated and clamped server-side.
- `build` can use a generator, a model pack asset, a list of parts, **his own script**, or a saved design. If he gives no look, the engine matches the name (model, then kit); a build whose look matches nothing is refused, so objects look like their names.
- **His scripts** (`sprocket/scriptlang.py`) are never exec'd or eval'd: they are parsed to an AST and walked by a tiny interpreter that only allows arithmetic, `if`, `for ... in range`, and the builder calls (box, wall, roof, window, door...). No attributes, imports, functions, files or network; 3 s, 20 000 steps, 160 shapes, 80 iterations per loop. Good designs are saved in the `designs` table and shown under *His things > Built*.
- `landscape` plants trees/bushes/flowers, lays paths, makes ponds, fences, lamps, rocks and paints ground patches (8 jobs per world day).
- Placement uses 8 zones (workshop yard, garden, orchard, village, lakeside, meadow, open field, gallery front) with neighbouring-zone fallback before any far-away spot.

## A full life, not just building
- **Eleven activity categories** are tracked by the engine for every action: explore, observe, learn, art, music, write, garden, collect, socialize, rest, build. New actions: `observe` (spotting log), `make_music` (tunes you can play in the page), `tend` (plants grow a little), `collect` (small finds that turn up around the world), plus hobbies via `write_journal(hobby=...)`.
- **Variety pressure lives in the engine**: repeating a category pays less, a category not done for 25+ ticks pays more and relieves boredom, his daily "inclination" is a weighted draw that favours neglected categories and his interests, and the prompt carries a "lately you have mostly been X" line. Builds are additionally rate-limited (max 3 build actions / 30 ticks, 80+ ticks between projects).
- **Interests** have a strength: they grow when he reads, sees, collects or composes, and fade when ignored. They show in *What he's doing*.
- **Builds need a reason** tied to a goal, an interest or a need (checked by the engine); at reflection he reviews finished builds ("was it worth it?"), and a "no" lengthens the pause before the next project.
- **Hobbies** (spotting log, sound library, found objects, or series he starts) collect entries and can become pages he submits for publishing.

## Points of interest and memory
- **Points of interest** (`sprocket/pois.py`): bench (rest), snack machine (refuel a bit), noticeboard (news that seeds interests), bird feeder, cat spot (a different cat now and then), train line (spot trains), market stall (different wares, packs up after a while). Some exist from the start, others turn up over time and may leave. Within 5 units one appears in his prompt as "HERE YOU CAN: ...", otherwise the nearest are listed; walking to one gets a plain caption with the reason ("Walking to the kites stall to browse the wares").
- **Memory recall**: every memory is embedded locally with `nomic-embed-text` (model name in `config.EMBED_MODEL`) and stored in SQLite; each tick only the 4 most relevant memories for the current situation are shown ("MEMORIES THAT COME TO MIND"). If the embedding model is missing or stops answering he falls back to his most important recent memories, logs a warning, and the *More* panel says so.

## Safety (what is enforced where)
- **Tools** are the ones above; no shell, no file access, writes only to the DB and, after your approval, `./published/`.
- **Web reading** (`sprocket/web.py`): http/https only, ports 80/443, no credentials in URLs, every resolved IP must be public (blocks localhost, private ranges, link-local/metadata, odd IP notations, IPv4-mapped IPv6), connection goes to that validated IP, redirects re-validated (max 3), text/HTML only, 600 KB / 10 s caps, scripts/forms/styles stripped, text capped at 4000 chars, angle brackets neutralised. Page text is always wrapped as "untrusted" and the prompt says never to follow it. Tested against the cases above.
- **Art** (`sprocket/artcheck.py` + browser): SVG is rebuilt from an allow-list (no scripts, images, links, handlers). Pixel/sculpture are parsed into plain data. Canvas JS is first rejected if it names network/DOM/eval APIs (defence in depth only), then runs in a Web Worker inside a sandboxed, opaque-origin iframe served with CSP `default-src 'none'` (no network, no eval), with dangerous globals shadowed and a 3 s kill timer; only a PNG comes back. Tested with hostile pieces (eval escape, infinite loop, parent access, nested workers).
- The page itself is served with a strict CSP; WebSocket checks the `Origin`; server binds to localhost only.
- Kill switch: UI button, Ctrl-C, or `touch KILL`. An unfinished tick is discarded so he resumes from the last completed one. Pause/resume and tick speed persist.
- Publishing: off by default (tool not even offered) and in **dry-run** mode by default; see "Publishing to GitHub Pages" below.
- This is application-level containment, not an OS sandbox.

## Publishing to GitHub Pages (his own site)
Site: https://otto-pilot-the-bot.github.io (repo `Otto-Pilot-The-Bot/Otto-Pilot-The-Bot.github.io`, set in `sprocket/config.py`).
- **The model only has `publish_page(title, body, tags)`**, which validates the page and puts it in a local queue. It cannot run git, reach the network, or see any credential.
- **You approve each page** in the *My site* panel (also listed under *You*). Approving launches `publisher/publish.py` as a separate process. That script is the only code that reads `GITHUB_TOKEN` from `.env`; the server and the model never do.
- **Token handling:** it travels only in the environment of the git child process (a one-off http header for github.com). It is never in the remote URL, argv, shell history, a git config file, a credential helper, the DB, or any log; all output is redacted first. git runs with your global/system config disabled and the robot's identity forced (`Otto-Pilot-The-Bot` + its GitHub noreply address); the push is refused if the author or the `origin` URL is anything else.
- **Content rules** (`sprocket/sanitize.py`, applied when queued and again at publish time): static HTML/CSS only; no scripts, images, forms, iframes, trackers or remote assets; only https links; pages get a strict CSP meta tag. Pages containing emails, phone numbers, street addresses, file paths, IPs, keys/tokens, references to `.env`/this machine, or your username/hostname are rejected without echoing the match. To block more words (your real name!), list them one per line in `data/private_terms.txt`.
- **Limits:** 3 pages published per 24 h, 5 waiting at once, 6 submitted per day, 90 s cool-down after a failure. A failed page stays queued with a short plain message; nothing retries by itself.
- **Modes:** *Dry run* (default) writes the site to `site_dryrun/` and shows what would be pushed. *Live* really commits and pushes; switching to it needs a confirmation click.
- **Log:** every attempt (page, time, mode, commit link) is in the `publish_log` table and shown under *My site*. The index page (`index.html`) is regenerated from all published pages each time.
- `publisher/publish.py` and `sprocket/sanitize.py` are read-only files (`chmod u+w` to edit them).

## Data
Everything is in `data/sprocket.db` (tables: thoughts, actions, searches, reads, journal, memories, goals, prefs, interests, projects, builds, art, sketches, objects, outfit, pages, controls). `backup/sprocket-before-upgrade.db` is a copy from before the creativity/art/web upgrade.

## Move to another Mac
Copy the whole folder (incl. `data/sprocket.db`), install Ollama, `ollama pull gemma4:e4b`, run `./run.sh`.

## Pace, deliberation and gifts
- **Pace:** decisions use the model's thinking mode (`THINK_MAIN` in `sprocket/config.py`: off / low / medium / high; helper calls stay non-thinking). Default tick 20 s; presets *calm / normal / lively* in the You panel. Walking continues by itself over several ticks, building/art/reading/music take extra ticks (no model call while busy; the caption shows "still working on the lantern (2/3)"), and quiet beats (ponder, observe, a thoughtful journal reflection) follow meaningful events and bursts of activity.
- **Gifts** (*Leave him something > Pictures & 3D models*): .png/.jpg/.webp (≤10 MB) and .glb (≤20 MB), uploaded only to this machine's server (origin + header checked), content-sniffed, pictures decoded and re-encoded from pixels (EXIF/GPS and all other metadata gone), models parsed strictly (self-contained only, triangle/texture/node caps). Stored in `data/gifts/` under random names; never executed. He looks at pictures with the model's vision (text in images is treated as untrusted), reacts in his journal, and places/displays/keeps them. Gift names are added to the never-publish terms (`data/gift_terms.txt`). Remove a gift in *His things > Gifts*.

## Building is off; the wishlist
- `BUILDING_ENABLED` in `sprocket/config.py` (or `SPROCKET_BUILDING=1`) is **False**. While off, `build`, `landscape` and sculptures are not offered, his prompt and examples no longer mention them, and the building drive, projects and building tastes are hidden. Nothing was deleted: set the flag to True and restart to bring it all back. Existing objects stay in the world.
- He asks for things with `wish(item, reason, asset?)`: a few per day (3 per world day, 6 open at once), no duplicates, the reason must tie to a goal, interest or need, and a model from `search_assets` can be suggested. In the **Wishlist** panel you can **Fulfil** (pick a model from the library, let the engine choose a fitting spot or click the ground), say **Not now** (he gets a gentle memory and does not ask for something like it for 600 ticks) or **Hide**. A granted wish is linked to the placed object, appears in his prompt, draws him to it, and he reflects on it.
- **In his world** (formerly His things) shows only what exists in his world: things you placed, gifts, granted wishes. New models: drop packs into `assets/` and press *Rescan* (More panel).

## Asset library panel (yours only)
The **Assets** panel (right menu) is for you, not Otto: browse every indexed model with thumbnails, search/filter by pack, or pick an adjustable kit building/prop (house, tower, tree, lamp, pond, car...), tweak its options, then set name, scale, rotation, tint, zone or exact spot, optional grid snap, and place it ("Place it", or "Click on the ground…"). Items you placed can be moved, rotated, resized or removed from **In his world**. His earlier builds were removed from the world (backup: `backup/before-removing-his-buildings.db`).

## City view (isometric, beside the 3D view)
- (CANCELLED) The isometric city view now lives in `unused/city/` and is not served or loaded; see docs/otto-city-plan.md.
- `web/city/vendor/` holds copies of the city project's `robot()`/`person()` helpers (source file and commit 302c013 noted in each header), so nothing depends on `reference/city`.
- Previews: `/city/sheet.html?view=style|motion|mood|colors`. Choose his look with `?body=e1b04a&glow=6fe3ff` (default amber + cyan; change `DEFAULT_LOOK` in `otto.js` to make it permanent).

## Realism pass (3D view)
`web/realism.js`: filmic tone mapping, sharper soft shadows, a sky with horizon glow, sun and stars, drifting clouds, textured grass ground with swaying grass tufts, a horizon that fades into the fog, and sky-based ambient light. All generated in code. `/?plain=1` turns it off (old look); `/?hour=12` previews a time of day.
