"""netart_blender.py -- runs INSIDE Blender (4.5 LTS): renders a network piece with the game's projection.

    blender -b [scene.blend] -P netart_blender.py -- job.json

Driven by `netart.py render / calibrate / blend-template`, which write job.json and post-process the PNGs (crop to
the frame, registration point, alpha cut, RGB565 quantisation). Geometry (NET_ART.md 2):

  * Blender X = tile v (towards the bottom screen vertex), Y = tile u (towards the top vertex), Z = up.
    One cell = 1 Blender unit. The cell's left screen vertex (u = v = 0) is the Blender origin.
  * Heights: the game draws altitude a at a * (1 << zoom) px (SIMSPR 0x1000be25, 8 px per unit at zoom 3).
    An orthographic camera at 30 degrees elevation, 45 degrees azimuth gives the game's 2:1 ground diamond and
    0.6124 W px per vertical Blender unit, so ONE ALTITUDE UNIT = ALT = 0.20412 Blender units.
    Model in cells horizontally and multiply heights by ALT (the template .blend's "SC3_ALT" empty is ALT tall).
  * Rotation slot r = the model turned +90 degrees * r about the footprint centre (slot r+1 is slot r turned
    counter-clockwise on screen, measured by `netart.py check-rot`; frame = zoom*4 + ((state + view) & 3),
    SIMSPR 0x1005aeab).
  * The camera looks at the origin, so the left vertex lands on the render centre (cw/2, ch/2) plus the per-zoom
    calibration shift (dx, dy) in px that `netart.py calibrate` measures against stock frames.

job.json = {"scene": {"build": "box"|"flat"|"blend", "height": <altitude units>, "n": <footprint cells>,
                      "colors": {...}},
            "engine": "WORKBENCH"|"CYCLES", "samples": 16,
            "renders": [{"z": 3, "r": 0, "dx": 0.0, "dy": 0.0, "out": "path.png"}, ...]}
In "blend" mode every object of collection "SC3_PIECE" is rendered (parented to the "SC3_ROOT" empty, which the
script turns); objects elsewhere (guides) are hidden from render.
"""
import json
import math
import sys

import bpy

ALT = 1.0 / (8.0 * math.cos(math.radians(30)) / math.sqrt(2.0))      # 0.20412
ELEV = math.radians(30.0)


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return json.load(open(a[0], encoding="utf-8"))


def mat(name, rgb, emit=False):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
        bsdf.inputs["Roughness"].default_value = 0.9
    m.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)
    return m


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)


def collection(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c


def add_box(col, root, x0, y0, z0, x1, y1, z1, m_top, m_side, name="box"):
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                                    (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    faces = [(4, 5, 6, 7), (0, 3, 2, 1), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    for i, f in enumerate(faces):
        fc = bm.faces.new([vs[k] for k in f])
        fc.material_index = 0 if i == 0 else 1
    bm.to_mesh(me)
    bm.free()
    me.materials.append(m_top)
    me.materials.append(m_side)
    o = bpy.data.objects.new(name, me)
    col.objects.link(o)
    o.parent = root
    return o


def build(spec):
    """Calibration / simple scenes built from code. Returns the root empty."""
    clear()
    col = collection("SC3_PIECE")
    n = spec.get("n", 1)
    root = bpy.data.objects.new("SC3_ROOT", None)
    col.objects.link(root)
    root.location = (n / 2.0, n / 2.0, 0.0)
    c = spec.get("colors", {})
    top = mat("top", c.get("top", (0.55, 0.55, 0.58)))
    side = mat("side", c.get("side", (0.75, 0.72, 0.62)))
    kind = spec.get("build", "box")
    h = spec.get("height", 4) * ALT
    if kind == "box":
        add_box(col, root, -n / 2.0, -n / 2.0, 0.0, n / 2.0, n / 2.0, h, top, side)
    elif kind == "flat":
        add_box(col, root, -n / 2.0, -n / 2.0, -0.0001, n / 2.0, n / 2.0, 0.0, top, top)
    elif kind == "parts":
        # props in TILE coordinates of slot 0 (u, v as in netart.py), heights in ALTITUDE units:
        #   {"cyl": [u, v, radius, z0, z1], "color": [r, g, b]}       vertical cylinder
        #   {"box": [u0, v0, u1, v1, z0, z1], "color": [...]}         axis-aligned box
        #   {"ball": [u, v, z, radius], "color": [...]}               sphere (radius in tiles)
        for i, p in enumerate(spec.get("parts", [])):
            m = mat("part%d" % i, p.get("color", (0.5, 0.5, 0.5)))
            if "cyl" in p:
                u, v, rad, z0, z1 = p["cyl"]
                bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=rad, depth=(z1 - z0) * ALT,
                                                    location=(v, u, (z0 + z1) / 2.0 * ALT))
            elif "ball" in p:
                u, v, z, rad = p["ball"]
                bpy.ops.mesh.primitive_uv_sphere_add(radius=rad, location=(v, u, z * ALT))
            elif "box" in p:
                u0, v0, u1, v1, z0, z1 = p["box"]
                o = add_box(col, root, v0 - n / 2.0, u0 - n / 2.0, z0 * ALT, v1 - n / 2.0, u1 - n / 2.0, z1 * ALT,
                            m, m, name="part%d" % i)
                continue
            o = bpy.context.active_object
            for c0 in list(o.users_collection):
                c0.objects.unlink(o)
            col.objects.link(o)
            o.data.materials.append(m)
            o.parent = root
            o.location = (o.location[0] - n / 2.0, o.location[1] - n / 2.0, o.location[2])
            bpy.ops.object.shade_smooth()
    return root


def setup_camera(engine, samples):
    sc = bpy.context.scene
    cam = bpy.data.objects.get("SC3_CAM")
    if cam is None:
        cd = bpy.data.cameras.new("SC3_CAM")
        cam = bpy.data.objects.new("SC3_CAM", cd)
        sc.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.rotation_euler = (math.radians(90) - ELEV, 0.0, math.radians(45))
    f = (-math.cos(ELEV) / math.sqrt(2), math.cos(ELEV) / math.sqrt(2), -math.sin(ELEV))
    d = 50.0
    cam.location = (-f[0] * d, -f[1] * d, -f[2] * d)
    cam.data.clip_start = 0.1
    cam.data.clip_end = 200.0
    sc.camera = cam
    sc.render.engine = "BLENDER_WORKBENCH" if engine == "WORKBENCH" else "CYCLES"
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.resolution_percentage = 100
    sc.render.filter_size = 0.01                      # no anti-aliasing filter: hard edges like the stock art
    sc.view_settings.view_transform = "Standard"
    if engine == "WORKBENCH":
        sc.display.shading.light = "FLAT"
        sc.display.shading.color_type = "MATERIAL"
        sc.display.render_aa = "OFF"
    else:
        sc.cycles.samples = samples
        sc.cycles.use_denoising = False
        sc.cycles.device = "CPU"
        sc.cycles.pixel_filter_type = "BOX"
        sc.cycles.filter_width = 0.01
    if engine != "WORKBENCH" and not any(o.type == "LIGHT" for o in sc.objects):
        # the stock art's light: top brightest, the left (SW) face lighter than the right (SE) face
        ld = bpy.data.lights.new("SC3_SUN", "SUN")
        ld.energy = 3.0
        lo = bpy.data.objects.new("SC3_SUN", ld)
        sc.collection.objects.link(lo)
        lo.rotation_euler = (math.radians(40), 0.0, math.radians(-20))
        w = sc.world or bpy.data.worlds.new("W")
        sc.world = w
        w.use_nodes = True
        w.node_tree.nodes["Background"].inputs[1].default_value = 0.6
    return cam


def render_one(cam, root, n, z, r, dx, dy, out, canvas=None, bleed=0.0):
    sc = bpy.context.scene
    W = 8 << z
    s = W / math.sqrt(2.0)                              # px per Blender unit in the screen plane
    cw, ch = canvas or (2 * (n + 2) * W, 2 * (n + 3) * W)
    sc.render.resolution_x, sc.render.resolution_y = cw, ch
    big = max(cw, ch)
    cam.data.ortho_scale = big / s
    # shift is in units of the larger dimension; +x moves the view right = the scene left
    cam.data.shift_x = -dx / big
    cam.data.shift_y = dy / big
    root.rotation_euler = (0.0, 0.0, math.radians(90.0 * r))
    k = 1.0 + 2.0 * bleed / (n * W)                    # grow the footprint by `bleed` px on each side
    root.scale = (k, k, 1.0)
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)


def main():
    job = args()
    spec = job.get("scene", {})
    if spec.get("build", "blend") == "blend":
        root = bpy.data.objects.get("SC3_ROOT")
        if root is None:
            raise SystemExit("scene has no SC3_ROOT empty (make one with netart.py blend-template)")
        keep = set(o.name for o in bpy.data.collections["SC3_PIECE"].all_objects)
        for o in bpy.context.scene.objects:
            if o.type in ("MESH", "CURVE", "SURFACE", "META", "FONT") and o.name not in keep:
                o.hide_render = True
    else:
        root = build(spec)
    cam = setup_camera(job.get("engine", "WORKBENCH"), job.get("samples", 16))
    n = spec.get("n", 1)
    for rj in job["renders"]:
        render_one(cam, root, n, rj["z"], rj["r"], rj.get("dx", 0.0), rj.get("dy", 0.0), rj["out"],
                   tuple(rj["canvas"]) if rj.get("canvas") else None, rj.get("bleed", 0.0))
    if job.get("save_blend"):
        bpy.ops.wm.save_as_mainfile(filepath=job["save_blend"])


if __name__ == "__main__":
    main()
