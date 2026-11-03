"""A small window for tools/blender_cleanup.py: pick .glb models, pick a triangle target, press Start.

Run it with tools\\model_reducer.bat (or `py -3 tools\\model_reducer_gui.py`). Tkinter only, nothing to install.
It runs Blender headless, one file at a time, and never changes an input file: each result is written to the
"Save to" folder under the input's own name (a partial file is written first and only renamed when Blender succeeds).
"""
import glob
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(HERE, "blender_cleanup.py")
DEFAULT_OUT = os.path.join(ROOT, "assets", "meshy", "Meshy Buildings")
SOURCE_DIR = os.path.join(os.path.dirname(ROOT), "Otto Assests Before Blender")
PRESETS = [("Small prop", 15000), ("House", 30000), ("Big building", 50000)]
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PORT = os.environ.get("SPROCKET_PORT", "8765")
KILL_FILE = os.path.join(ROOT, "KILL")                  # the server's own stop file (sprocket/config.py): it notices it, stops cleanly and deletes it
STARTERS = ("start-otto-pc.bat", "run.bat")


def find_blender():
    """The newest C:\\Program Files\\Blender Foundation\\Blender *\\blender.exe, or ''."""
    found = []
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), r"C:\Program Files"):
        for exe in glob.glob(os.path.join(base, "Blender Foundation", "Blender *", "blender.exe")):
            m = re.search(r"Blender (\d+(?:\.\d+)*)", exe)
            found.append((tuple(int(x) for x in m.group(1).split(".")) if m else (0,), exe))
    return max(found)[1] if found else ""


def server_running():
    """True if something is listening on Otto's port (asks Windows; no extra packages)."""
    cmd = f"if (Get-NetTCPConnection -LocalPort {PORT} -State Listen -ErrorAction SilentlyContinue) {{ 'yes' }}"
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=20, creationflags=NO_WINDOW)
        return "yes" in r.stdout
    except (OSError, subprocess.SubprocessError):
        return False


def restart_server(log):
    """Stop Otto's server the normal way (the KILL file), wait for it to let go of the port, then start it again in its own window.
    Only restarts a server that is running; returns a sentence saying what happened."""
    if not server_running():
        return "Otto's server was not running. Start it (start-otto-pc.bat) and it will pick up the new files."
    starter = next((os.path.join(ROOT, n) for n in STARTERS if os.path.isfile(os.path.join(ROOT, n))), None)
    if not starter:
        return "Could not find start-otto-pc.bat to restart the server. Restart it yourself to pick up the new files."
    log("Stopping Otto's server (KILL file)...")
    try:
        open(KILL_FILE, "w").close()
    except OSError as e:
        return f"Could not ask the server to stop ({e}). Restart it yourself to pick up the new files."
    for _ in range(40):
        time.sleep(1)
        if not server_running():
            break
    else:
        try:
            os.remove(KILL_FILE)
        except OSError:
            pass
        return "The server did not stop within 40 seconds, so it was left running. Restart it yourself to pick up the new files."
    time.sleep(1)
    log("Starting Otto's server again...")
    try:
        subprocess.Popen(["cmd", "/c", "start", "Otto Pilot server", starter], cwd=ROOT)
    except OSError as e:
        return f"The server stopped but could not be started again ({e}). Start it with start-otto-pc.bat."
    return "Otto's server was restarted (it opens in its own window) and will pick up the new files in a minute."


def size_text(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


class App:
    def __init__(self, root):
        self.root = root
        root.title("Otto Pilot · Model reducer")
        root.minsize(760, 640)
        self.files, self.rows = [], {}
        self.q = queue.Queue()
        self.proc = None
        self.cancel = threading.Event()
        self.running = False
        self.blender = tk.StringVar(value=find_blender())
        self.outdir = tk.StringVar(value=DEFAULT_OUT)
        self.target = tk.StringVar(value="30000")
        self.bake = tk.BooleanVar(value=False)
        self.restart = tk.BooleanVar(value=True)
        self.build()
        root.after(100, self.pump)

    # ---- layout
    def build(self):
        f = ttk.Frame(self.root, padding=10)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)
        r = 0
        ttk.Label(f, text="Blender").grid(row=r, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.blender).grid(row=r, column=1, sticky="ew", padx=6)
        ttk.Button(f, text="Browse…", command=self.pick_blender).grid(row=r, column=2)
        r += 1
        ttk.Label(f, text="Models").grid(row=r, column=0, sticky="w", pady=(8, 0))
        self.fileLabel = ttk.Label(f, text="none chosen")
        self.fileLabel.grid(row=r, column=1, sticky="w", padx=6, pady=(8, 0))
        ttk.Button(f, text="Choose model(s)…", command=self.pick_files).grid(row=r, column=2, pady=(8, 0))
        r += 1
        ttk.Label(f, text="Save to").grid(row=r, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(f, textvariable=self.outdir).grid(row=r, column=1, sticky="ew", padx=6, pady=(8, 0))
        ttk.Button(f, text="Browse…", command=self.pick_out).grid(row=r, column=2, pady=(8, 0))
        r += 1
        t = ttk.Frame(f)
        t.grid(row=r, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(t, text="Triangle target").pack(side="left")
        ttk.Entry(t, textvariable=self.target, width=9).pack(side="left", padx=6)
        for name, n in PRESETS:
            ttk.Button(t, text=f"{name} {n:,}", command=lambda n=n: self.target.set(str(n))).pack(side="left", padx=2)
        r += 1
        ttk.Checkbutton(f, text="Bake detail into a normal map (slow)", variable=self.bake).grid(row=r, column=0, columnspan=3, sticky="w", pady=(6, 0))
        r += 1
        ttk.Checkbutton(f, text="Restart Otto's server when finished (so he picks up the new models)", variable=self.restart).grid(row=r, column=0, columnspan=3, sticky="w")
        r += 1
        b = ttk.Frame(f)
        b.grid(row=r, column=0, columnspan=3, sticky="w", pady=8)
        self.startBtn = ttk.Button(b, text="Start", command=self.start)
        self.startBtn.pack(side="left")
        self.cancelBtn = ttk.Button(b, text="Cancel", command=self.do_cancel, state="disabled")
        self.cancelBtn.pack(side="left", padx=6)
        r += 1
        self.tree = ttk.Treeview(f, columns=("status", "detail"), height=5)
        self.tree.heading("#0", text="Model")
        self.tree.heading("status", text="Status")
        self.tree.heading("detail", text="Result")
        self.tree.column("#0", width=200)
        self.tree.column("status", width=80, stretch=False)
        self.tree.column("detail", width=420)
        self.tree.grid(row=r, column=0, columnspan=3, sticky="ew")
        r += 1
        self.log = scrolledtext.ScrolledText(f, height=14, state="disabled", font=("Consolas", 9))
        self.log.grid(row=r, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        f.rowconfigure(r, weight=1)

    # ---- pickers
    def pick_blender(self):
        p = filedialog.askopenfilename(title="Find blender.exe", filetypes=[("Blender", "blender.exe"), ("All files", "*.*")])
        if p:
            self.blender.set(os.path.normpath(p))

    def pick_files(self):
        start = SOURCE_DIR if os.path.isdir(SOURCE_DIR) else ROOT
        ps = filedialog.askopenfilenames(title="Choose model(s)", initialdir=start, filetypes=[("GLB models", "*.glb"), ("All files", "*.*")])
        if ps:
            self.files = [os.path.normpath(p) for p in ps]
            self.fileLabel.config(text=f"{len(self.files)} chosen: " + ", ".join(os.path.basename(p) for p in self.files[:3]) + (" …" if len(self.files) > 3 else ""))

    def pick_out(self):
        d = filedialog.askdirectory(title="Save reduced models to", initialdir=self.outdir.get() if os.path.isdir(self.outdir.get()) else ROOT, mustexist=False)
        if d:
            self.outdir.set(os.path.normpath(d))

    # ---- start / cancel
    def start(self):
        exe, out = self.blender.get().strip(), os.path.normpath(self.outdir.get().strip())
        if not os.path.isfile(exe):
            return messagebox.showerror("Blender", "Pick blender.exe first.")
        if not self.files:
            return messagebox.showerror("Models", "Choose at least one .glb model.")
        try:
            target = int(self.target.get().replace(",", "").strip())
            assert target >= 100
        except Exception:
            return messagebox.showerror("Triangle target", "Enter a whole number of triangles (100 or more).")
        if not out:
            return messagebox.showerror("Save to", "Pick an output folder.")
        jobs = []
        for src in self.files:
            dst = os.path.normpath(os.path.join(out, os.path.basename(src)))
            if os.path.dirname(dst) != out:                              # the name must stay inside the chosen folder
                messagebox.showerror("Save to", f"Refusing to write outside the chosen folder: {dst}")
                continue
            if os.path.normcase(os.path.abspath(dst)) == os.path.normcase(os.path.abspath(src)):
                messagebox.showerror("Save to", f"{os.path.basename(src)} would overwrite its own original. Choose a different 'Save to' folder.")
                continue
            if os.path.exists(dst) and not messagebox.askyesno("Replace file?", f"{dst}\nalready exists. Replace it?", default="no", icon="warning"):
                continue
            jobs.append((src, dst))
        if not jobs:
            return
        try:
            os.makedirs(out, exist_ok=True)
        except OSError as e:
            return messagebox.showerror("Save to", f"Can't create the folder: {e}")
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for src, dst in jobs:
            self.rows[src] = self.tree.insert("", "end", text=os.path.basename(src), values=("queued", ""))
        self.set_log("")
        self.running = True
        self.cancel.clear()
        self.startBtn.config(state="disabled")
        self.cancelBtn.config(state="normal")
        threading.Thread(target=self.work, args=(exe, jobs, target, self.bake.get(), self.restart.get()), daemon=True).start()

    def do_cancel(self):
        self.cancel.set()
        p = self.proc
        if p and p.poll() is None:
            p.terminate()
        self.q.put(("log", "-- cancel requested --"))

    # ---- worker thread (talks to the window only through the queue)
    def work(self, exe, jobs, target, bake, restart):
        ok = fail = 0
        for src, dst in jobs:
            if self.cancel.is_set():
                self.q.put(("row", src, "cancelled", ""))
                continue
            self.q.put(("row", src, "working", ""))
            part = dst[:-4] + ".part.glb" if dst.lower().endswith(".glb") else dst + ".part"
            cmd = [exe, "--background", "--python", SCRIPT, "--", src, part, "--target", str(target)] + (["--bake-normals"] if bake else [])
            self.q.put(("log", "\n=== " + os.path.basename(src) + " ===\n" + " ".join(cmd)))
            tail, before, after, already = [], None, None, False
            try:
                self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                             errors="replace", creationflags=NO_WINDOW, env={**os.environ, "PYTHONUTF8": "1"})
                for line in self.proc.stdout:
                    line = line.rstrip()
                    self.q.put(("log", line))
                    if line.strip():
                        tail.append(line)
                        tail = tail[-6:]
                    m = re.search(r"mesh object\(s\), (\d+) triangles", line)
                    if m:
                        before = int(m.group(1))
                    m = re.search(r"after reduction: (\d+) triangles", line)
                    if m:
                        after = int(m.group(1))
                    if "nothing to reduce" in line:
                        already = True
                code = self.proc.wait()
            except OSError as e:
                code, tail = -1, [str(e)]
            if self.cancel.is_set() or code != 0 or not os.path.isfile(part):
                self.drop(part)
                if self.cancel.is_set():
                    self.q.put(("row", src, "cancelled", ""))
                else:
                    fail += 1
                    self.q.put(("row", src, "failed", " | ".join(tail[-3:]) or f"Blender exit code {code}"))
                continue
            try:
                os.replace(part, dst)
            except OSError as e:
                self.drop(part)
                fail += 1
                self.q.put(("row", src, "failed", f"could not save: {e}"))
                continue
            ok += 1
            sizes = f"{size_text(os.path.getsize(src))} -> {size_text(os.path.getsize(dst))}"
            tris = f"{before:,} -> {after:,} triangles" if before is not None and after is not None else "triangles: see log"
            note = " (already under the target, not reduced)" if already else ""
            self.q.put(("row", src, "done", f"{tris}; {sizes}{note}"))
        self.proc = None
        note = ""
        if ok and not self.cancel.is_set():
            note = restart_server(lambda t: self.q.put(("log", t))) if restart else "Now restart Otto's server (or use rescan) so it picks up the new files."
            self.q.put(("log", note))
        self.q.put(("end", ok, fail, note))

    @staticmethod
    def drop(path):
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

    # ---- window side
    def set_log(self, text):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.insert("end", text)
        self.log.config(state="disabled")

    def pump(self):
        try:
            while True:
                m = self.q.get_nowait()
                if m[0] == "log":
                    self.log.config(state="normal")
                    self.log.insert("end", m[1] + "\n")
                    self.log.see("end")
                    self.log.config(state="disabled")
                elif m[0] == "row":
                    self.tree.item(self.rows[m[1]], values=(m[2], m[3]))
                elif m[0] == "end":
                    self.running = False
                    self.startBtn.config(state="normal")
                    self.cancelBtn.config(state="disabled")
                    if m[1] and not self.cancel.is_set():
                        messagebox.showinfo("Finished", f"{m[1]} done, {m[2]} failed.\n\n{m[3]}")
                    elif m[2]:
                        messagebox.showwarning("Finished", f"{m[1]} done, {m[2]} failed. See the log.")
        except queue.Empty:
            pass
        self.root.after(100, self.pump)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
