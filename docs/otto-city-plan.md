> **CANCELLED for now.** The isometric city view is parked in `unused/city/` (not served, not loaded).

# Otto in the city: Stage 1 plan (robot from TheFollowerCity)

Source (read-only, `reference/city`, commit 302c013 "Add robot character to People assets"): `src/assets/people.js` `robot()`, registered in `src/registry.js` as People "Robot", "Robot 2", "Robot 3" (`{scale 4.2, oy 120, dirs: true, anim: true}`).

## What exists
- Canvas 2D, code-drawn, no image files. Signature `robot(ctx, r, {dir, frame})`, feet at (0,0), screen space (not the iso `box` kit), about 28 px tall before scale.
- `dir` 0 down-right, 1 down-left (front), 2 up-left, 3 up-right (back). Front = dir < 2; left/right is a mirror (`sx`).
- `frame` 0 idle, 1 and 2 walk steps (viewer cycles 0,1,0,2 every 200 ms). Walk = leg swing +-1.8 and body bob -0.6.
- Colors: seeded `r.pick` of body (5 colors: grey, gold, blue, red, green) and glow (4); fixed joint `#4a5058`, dark `#2d3136`; `shade()` for panels. Visor with two glow dot eyes; antenna with glow tip; chest panel light; back view has vent slats.
- Not placed on the world map yet (mapview draws buildings and `SPR` sprites only); only the Asset Lab shows it.

## What is missing for Otto
| Need | Status |
|---|---|
| idle, walk in 4 directions | have (frames 0/1/2 x 4 dirs) |
| wave | missing |
| sit | missing |
| sleep/rest | missing |
| ride a vehicle | missing (needs rider pose + anchor on `Rig` vehicles) |
| happy / sad / surprised faces | missing (visor eyes are fixed dots) |
| Otto's own look | needs a fixed look (seeded body/glow today; Otto's colors come from his outfit) |

## Plan (new files only; nothing in reference/city is edited)
1. **Load**: copy nothing. Import the original at runtime from a thin wrapper, e.g. `web/city/otto.js`: `import { robot } from '../../reference/city/src/assets/people.js'` (served as static files; `shade`, `PAL`, `rng` come along via its own imports). Server keeps a static route for `reference/city/src` read-only.
2. **Otto = `robot` with a fixed seed** so the colors never change (pick a seed whose body/glow matches Otto: orange body per his current look, or `rng` stub that returns chosen colors). Do not use the old 3D robot in this view.
3. **Extra poses in the same style** in `otto.js`, drawn by *composing* `robot()` plus overlays/offset copies in the same helpers (round rects, dots, same palette, 1 px-scale units):
   - `wave`: redraw with right arm raised (rect rotated about shoulder), 2 frames alternating angle.
   - `sit`: legs forward short rects, torso lowered by 4, 1 frame.
   - `sleep`: sit pose plus visor line (closed eyes), glow dimmed, floating "z".
   - `ride`: sit pose clipped at the waist, drawn on the vehicle's seat anchor after the vehicle layer.
   - Because `robot()` hardcodes its face, faces need either a small upstream parameter or an overlay: **overlay** the visor area with a dark rect then draw the mood face on top (keeps the city file untouched).
4. **Moods (visor faces)**, each a few dots and strokes in glow color: happy (arc eyes ^ ^ and small smile), sad (down-slanted eyes, chest light dim), surprised (large round eyes, antenna tip bright), plus tired (half-height bars) and neutral (current dots). Mood comes from `snapshot.mood` / his feeling.
5. **Wiring**: `OttoCity.draw(ctx, {dir, frame, pose, mood})`. Map his heading to `dir` (0..3), alternate frames 0,1,0,2 only while moving, pose from the current action (rest -> sit/sleep, greet -> wave, move_to -> walk). Anchor feet to the iso tile (`P(x,y)`), draw order by depth.
6. **Test**: an Asset-Lab style sheet (4 dirs x poses x moods) screenshot, then place on the world view.

## Decisions I need from you before building
- Is "the city view" a new canvas page in Sprocket (iso map like `map.html`), or should Otto replace the Three.js view? Today Sprocket has no city view.
- Which body/glow colors should Otto have?
- OK to import straight from `reference/city/src` (path coupling), or copy `robot()` into Sprocket with attribution?
