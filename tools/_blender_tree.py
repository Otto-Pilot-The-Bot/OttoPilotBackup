"""Blender half of tools/make_trees.py: builds the branched trunks, leaf cards and apples and exports one .glb per tree. Not meant to be run by hand."""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

TMP, OUT = sys.argv[sys.argv.index("--") + 1:][:2]

KINDS = {  # name: (leaf sprite, bark, apples)
    "Tree Green": ("green", "bark.png", 0),
    "Apple Tree": ("apple", "bark_dark.png", 26),
    "Pink Blossom Tree": ("pink", "bark_dark.png", 0),
}
# per variant: trunk height, trunk radius, branch count, branch reach, crown width factor
SHAPES = {"A": (3.0, 0.21, 6, 2.6, 1.0), "B": (4.2, 0.18, 7, 2.1, 0.8), "C": (2.2, 0.25, 6, 3.0, 1.25)}


def new_mat(name, img_path, alpha=False, color=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.85
    if img_path:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(img_path)
        t.image.colorspace_settings.name = "sRGB"
        nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
        if alpha:
            nt.links.new(t.outputs["Alpha"], bsdf.inputs["Alpha"])
    if color:
        bsdf.inputs["Base Color"].default_value = color
    return m


def basis(d):
    ref = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    a = d.cross(ref).normalized()
    return a, d.cross(a).normalized()


def add_tube(bm, uv, pts, radii, sides=6, vstart=0.0):
    rings = []
    for i, p in enumerate(pts):
        d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        a, b = basis(d)
        rings.append([bm.verts.new(p + (a * math.cos(2 * math.pi * k / sides) + b * math.sin(2 * math.pi * k / sides)) * radii[i]) for k in range(sides)])
    v = vstart
    vs = [vstart]
    for i in range(1, len(pts)):
        v += (pts[i] - pts[i - 1]).length * 1.2
        vs.append(v)
    for i in range(len(pts) - 1):
        for k in range(sides):
            f = bm.faces.new((rings[i][k], rings[i][(k + 1) % sides], rings[i + 1][(k + 1) % sides], rings[i + 1][k]))
            for loop, (uu, vv) in zip(f.loops, ((k / sides, vs[i]), ((k + 1) / sides, vs[i]), ((k + 1) / sides, vs[i + 1]), (k / sides, vs[i + 1]))):
                loop[uv].uv = (uu * 2.0, vv)


def build(kind, letter, seed):
    sprite, bark_img, napples = KINDS[kind]
    th, tr, nbr, reach, cw = SHAPES[letter]
    rng = random.Random(seed)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    wood = bmesh.new(); wuv = wood.loops.layers.uv.new("UVMap")
    leaves = bmesh.new(); luv = leaves.loops.layers.uv.new("UVMap")
    apples = []
    tips = []                                                              # (position, direction) where leaf cards go

    def grow(start, direction, length, r0, r1, depth):
        n = 7 if depth == 0 else 5
        pts, radii, p, d = [start], [r0], start.copy(), direction.normalized()
        for i in range(1, n + 1):
            d = (d + Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.2, 0.5))) * (0.16 if depth else 0.1) + Vector((0, 0, 0.06 if depth else 0.02))).normalized()
            p = p + d * (length / n)
            pts.append(p.copy()); radii.append(r0 + (r1 - r0) * i / n)
        add_tube(bm_wood, wuv, pts, radii, sides=7 if depth == 0 else 5)
        if depth >= 1:
            for i in range(2, n + 1):
                tips.append((pts[i], (pts[i] - pts[i - 1]).normalized()))
        if depth < 3:
            kids = nbr if depth == 0 else (3 if depth == 1 else 2)
            for k in range(kids):
                t = rng.uniform(0.5 if depth == 0 else 0.25, 0.95)
                i = max(1, min(n, int(t * n)))
                az = rng.uniform(0, 2 * math.pi) if depth else (k * 2 * math.pi / kids + rng.uniform(-0.4, 0.4))
                a, b = basis(d if depth else Vector((0, 0, 1)))
                out = (a * math.cos(az) + b * math.sin(az))
                cd = (out * rng.uniform(0.9, 1.3) + Vector((0, 0, rng.uniform(0.35, 0.8)))).normalized() if depth == 0 else (pts[i] - pts[i - 1]).normalized() * 0.45 + out * 0.8 + Vector((0, 0, 0.25))
                clen = (reach if depth == 0 else length * 0.62) * rng.uniform(0.8, 1.05)
                grow(pts[i], cd, clen, max(0.012, radii[i] * 0.62), max(0.006, radii[i] * 0.2), depth + 1)

    bm_wood = wood
    lean = Vector((rng.uniform(-0.12, 0.12), rng.uniform(-0.12, 0.12), 1))
    grow(Vector((0, 0, 0)), lean, th, tr, tr * 0.42, 0)
    # leaf cards: each is a quad standing on a twig, pointing the way the twig grows, rolled at random
    cards = 0
    cands = []
    for p, d in tips:
        for _ in range(3 if sprite != "pink" else 4):
            s = rng.uniform(0.95, 1.4) * (1.0 if sprite != "pink" else 0.95)
            dd = (d * 0.6 + Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.3, 0.9))) * 0.6).normalized()
            a, _b = basis(dd)
            a = a * math.cos(rng.uniform(0, math.pi)) + dd.cross(a) * math.sin(rng.uniform(0, math.pi))
            a = a.normalized() * s * 0.55
            base = p + Vector((rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1), rng.uniform(-0.05, 0.1)))
            vs = [base - a, base + a, base + a + dd * s, base - a + dd * s]
            f = leaves.faces.new([leaves.verts.new(v) for v in vs])
            for loop, uvc in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
                loop[luv].uv = uvc
            cards += 1
            if napples:
                q = base + dd * s * 0.8
                cands.append((math.hypot(q.x, q.y) + 0.3 * q.z, q + Vector((0, 0, -0.12))))
    cands.sort(key=lambda c: -c[0])                                          # apples hang on the outside of the crown where they can be seen
    outer = [c[1] for c in cands[:max(napples * 3, 1)]]
    rng.shuffle(outer)
    apples = outer[:napples]
    mw = bpy.data.meshes.new("wood"); wood.to_mesh(mw); wood.free()
    ml = bpy.data.meshes.new("leaves"); leaves.to_mesh(ml); leaves.free()
    ow, ol = bpy.data.objects.new("wood", mw), bpy.data.objects.new("leaves", ml)
    for o in (ow, ol):
        bpy.context.scene.collection.objects.link(o)
    mw.materials.append(new_mat("Bark", os.path.join(TMP, bark_img)))
    ml.materials.append(new_mat("Leaf", os.path.join(TMP, f"leaf_{sprite}.png"), alpha=True))
    objs = [ow, ol]
    if apples:
        red = new_mat("Apple", None, color=(0.62, 0.05, 0.03, 1))
        for p in apples:
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=rng.uniform(0.095, 0.12), location=p)
            o = bpy.context.active_object; o.data.materials.append(red); objs.append(o)
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = ow
    bpy.ops.object.join()
    t = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    path = os.path.join(OUT, f"{kind} {letter}.glb")
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True, export_image_format="AUTO")
    tri = sum(max(0, len(p.vertices) - 2) for p in t.data.polygons)
    print(f"WROTE {kind} {letter}: {tri} tris, {cards} cards, {len(apples)} apples, {[round(x, 1) for x in t.dimensions]} m, {os.path.getsize(path) // 1024} KB")


for ki, kind in enumerate(KINDS):
    for li, letter in enumerate(SHAPES):
        try:
            build(kind, letter, 4000 + ki * 10 + li)
        except Exception as e:
            print("ERROR", kind, letter, repr(e))
