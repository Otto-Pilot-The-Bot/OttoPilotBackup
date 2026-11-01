"""Clean up and shrink a GLB model with Blender, without opening Blender's window.

Run it like this (Blender 3.6 or newer; adjust the path to your Blender):

  /Applications/Blender.app/Contents/MacOS/Blender --background --python tools/blender_cleanup.py -- \
      "assets/meshy/Meshy Buildings/Ottos Bank.glb"  /tmp/Ottos-Bank-small.glb  --target 250000

What it does, in order:
  1. Imports the GLB and applies every object's position/rotation/scale.
  2. Joins all the meshes into one (fewer draw calls for the page).
  3. Merges vertices that sit on top of each other, deletes loose bits (stray vertices and edges), removes degenerate faces.
  4. Reduces the triangle count to --target with a Collapse decimation. The UVs are kept, so the original texture still fits.
  5. Optional --bake-normals: bakes the fine detail of the original into a normal map for the reduced model (slow, needs Cycles).
  6. Removes unused materials/images and exports a GLB with the textures inside.

It never changes the file you give it; it writes to the output path. Check the result against the original before replacing anything.
NOT TESTED in this project (Blender is not installed here); the steps are standard Blender Python.
"""
import argparse
import sys

import bpy
import bmesh


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description="Clean up and reduce a GLB")
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--target", type=int, default=250_000, help="triangles to aim for (default 250000)")
    ap.add_argument("--merge", type=float, default=0.0001, help="merge vertices closer than this many units (default 0.0001)")
    ap.add_argument("--bake-normals", action="store_true", help="bake the original's detail into a normal map on the reduced model")
    ap.add_argument("--bake-size", type=int, default=2048, help="size of the baked normal map in pixels (default 2048)")
    ap.add_argument("--jpeg-quality", type=int, default=88, help="quality of exported textures (default 88)")
    return ap.parse_args(argv)


def meshes():
    return [o for o in bpy.context.scene.objects if o.type == "MESH"]


def tri_count(objs):
    total = 0
    for o in objs:
        me = o.data
        total += sum(max(0, len(p.vertices) - 2) for p in me.polygons)
    return total


def select_only(objs, active=None):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def import_glb(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    objs = meshes()
    if not objs:
        sys.exit("No meshes found in that file.")
    select_only(objs)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return objs


def join_all(objs):
    select_only(objs)
    if len(objs) > 1:
        bpy.ops.object.join()
    return bpy.context.view_layer.objects.active


def clean_mesh(obj, merge_dist):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    before = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_dist)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=merge_dist)
    loose_v = [v for v in bm.verts if not v.link_edges]
    loose_e = [e for e in bm.edges if not e.link_faces]
    if loose_e:
        bmesh.ops.delete(bm, geom=loose_e, context="EDGES")
    loose_v = [v for v in bm.verts if not v.link_edges]
    if loose_v:
        bmesh.ops.delete(bm, geom=loose_v, context="VERTS")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    print(f"  merged/cleaned: {before} -> {len(obj.data.vertices)} vertices")


def decimate(obj, target):
    now = tri_count([obj])
    if now <= target:
        print(f"  already at {now} triangles, nothing to reduce")
        return
    mod = obj.modifiers.new("Reduce", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = max(0.001, min(1.0, target / now))
    mod.use_collapse_triangulate = True
    mod.use_symmetry = False
    select_only([obj])
    bpy.ops.object.modifier_apply(modifier=mod.name)


def bake_normals(high, low, size):
    """Bake `high` (the original detail) onto `low` (the reduced copy) as a tangent-space normal map."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 8
    img = bpy.data.images.new("baked_normal", size, size)
    img.colorspace_settings.name = "Non-Color"
    for slot in low.material_slots:
        mat = slot.material
        if not mat or not mat.use_nodes:
            continue
        nt = mat.node_tree
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        tex.name = "bake_target"
        nt.nodes.active = tex                                  # Blender bakes into the active image node
    select_only([high, low], active=low)
    bpy.ops.object.bake(type="NORMAL", use_selected_to_active=True, cage_extrusion=0.03, margin=8)
    for slot in low.material_slots:                            # wire the baked map into each material
        mat = slot.material
        if not mat or not mat.use_nodes:
            continue
        nt = mat.node_tree
        tex = nt.nodes.get("bake_target")
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not tex or not bsdf:
            continue
        for old in [l for l in nt.links if l.to_socket == bsdf.inputs["Normal"]]:
            nt.links.remove(old)
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(tex.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])


def main():
    a = parse()
    print(f"Importing {a.input}")
    objs = import_glb(a.input)
    print(f"  {len(objs)} mesh object(s), {tri_count(objs)} triangles")
    obj = join_all(objs)
    clean_mesh(obj, a.merge)
    print(f"  after cleanup: {tri_count([obj])} triangles")
    high = None
    if a.bake_normals:
        high = obj.copy(); high.data = obj.data.copy(); high.name = "high_detail"
        bpy.context.scene.collection.objects.link(high)
    decimate(obj, a.target)
    print(f"  after reduction: {tri_count([obj])} triangles (target {a.target})")
    if high is not None:
        print("  baking normal map (this can take a few minutes)...")
        bake_normals(high, obj, a.bake_size)
        bpy.data.objects.remove(high, do_unlink=True)
    bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    select_only([obj])
    bpy.ops.export_scene.gltf(filepath=a.output, export_format="GLB", use_selection=True, export_apply=True,
                              export_image_format="JPEG", export_jpeg_quality=a.jpeg_quality, export_yup=True)
    print(f"Wrote {a.output}")


if __name__ == "__main__":
    main()
