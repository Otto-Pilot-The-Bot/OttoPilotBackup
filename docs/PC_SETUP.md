# Running Otto on the PC (RTX 5070 Ti) and using it from the Mac

The PC runs everything: Ollama (the brain), the server, and the database. The Mac just opens the page in a browser, so you can
watch Otto, edit maps in the Plan editor and use the panels from the couch. Only ONE computer should run Otto at a time.

Note: the 3D picture is drawn by the computer whose browser shows the page. Heavy models still draw on the Mac's graphics chip when you
watch from the Mac. For the smoothest view, watch on the PC itself (or screen-share it, e.g. RustDesk).

## One-time setup on the PC (Windows steps; the Mac/Linux equivalents are `run.sh`)
1. Install Python 3.12+ (python.org), Ollama (ollama.com) and Tailscale (tailscale.com). Sign in to the SAME Tailscale account on the Mac.
2. In a terminal: `ollama pull gemma4:e4b` and `ollama pull nomic-embed-text`.
3. Copy the project folder from the Mac to the PC (USB drive or a network share). Copy `data/` and `assets/` too (they are not in git),
   but NOT `.venv/`. Do not run Otto on the Mac while the PC has the copy.
4. Make a secret token (16+ characters), for example: `py -c "import secrets; print(secrets.token_urlsafe(24))"`
5. Find the PC's Tailscale address (the `100.x.y.z` number in the Tailscale app).

## Starting it
In a terminal in the project folder (PowerShell uses `$env:NAME="value"`; cmd uses `set NAME=value`):
```
set SPROCKET_HOST=100.x.y.z          (the PC's Tailscale address; only reachable from your own Tailscale devices)
set SPROCKET_TOKEN=<your secret token>
set SPROCKET_NUM_CTX=8192            (optional: a bigger prompt, now that there is plenty of graphics memory)
set SPROCKET_KEEP_ALIVE=30m          (optional: keep the model loaded)
run.bat
```
If SPROCKET_HOST is anything but localhost the server REFUSES to start without a token.

## Opening it from the Mac
Open `http://100.x.y.z:8765/?token=<your secret token>` once. The page remembers you (a cookie) and removes the token from the address.
Bookmark `http://100.x.y.z:8765/`. Without the cookie every page, asset, socket and upload answers 401.

## Stopping and the kill switch
Create an empty file called `KILL` in the project folder on the PC (`type nul > KILL`) to stop everything. Or press the kill button on the page.

## Going back to the Mac
Stop the PC server, copy `data/` back to the Mac (the database and maps are the only things that change), and start the Mac as before.
Never run both at once: the database has to have a single writer.

## Game mode (gaming or recording with OBS)
Press the **🎮 Game mode** button (bottom left of the page, next to Plan; also in the You panel). It pauses Otto, lets any thought already
running finish, then tells Ollama to unload his models so the graphics memory is free. While it is on, nothing in the program can call the model.
Press it again (or **Resume**) to wake him; the model reloads on his next thought. The server and page stay up (they use almost nothing).
To stop the server completely too, create an empty file named `KILL` in the project folder (`type nul > KILL`); start it again with `run.bat`.
