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
