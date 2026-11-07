# =====================================================================
# lib.py: herramientas comunes para "fotografiar" comida simulada con Blender.
#
# La idea: en vez de hacer fotos, modelamos cada alimento con matemáticas
# (SDF = una función que dice a qué distancia está cada punto de la superficie),
# le damos color punto a punto y lo renderizamos con trazado de rayos.
# El fondo sale transparente, así que las imágenes se integran en la web.
#
# Se ejecuta dentro de Blender:  Blender --background --python escena.py
# Unidad de trabajo: 1 unidad = 10 cm, más o menos.
# =====================================================================
import math
import os

import bpy
import numpy as np
from mathutils import Matrix, Vector


# ---------- Color ----------
def lin(h):
    """Convierte '#RRGGBB' (sRGB) en un color lineal, que es el que usa el render."""
    h = h.lstrip("#")
    c = np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], dtype=np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def mix(a, b, t):
    t = np.asarray(t)
    if np.ndim(a) > 0 or np.ndim(b) > 0:
        t = t[..., None] if t.ndim else t
    return a * (1 - t) + b * t


# ---------- Ruido (textura natural) ----------
_rs = np.random.RandomState(7)
_P = _rs.permutation(256)
_P = np.concatenate([_P, _P, _P]).astype(np.int32)
_G = _rs.normal(size=(256, 3)).astype(np.float32)
_G /= np.linalg.norm(_G, axis=1, keepdims=True)
_J = _rs.random_sample((256, 3)).astype(np.float32)


def perlin(p):
    """Ruido suave entre -1 y 1 aprox. p: array (...,3)."""
    p = np.asarray(p, dtype=np.float32)
    pi = np.floor(p)
    f = p - pi
    pi = pi.astype(np.int32) & 255
    u = f * f * f * (f * (f * 6 - 15) + 10)
    x, y, z = pi[..., 0], pi[..., 1], pi[..., 2]
    out = 0
    for dx in (0, 1):
        wx = u[..., 0] if dx else 1 - u[..., 0]
        for dy in (0, 1):
            wy = u[..., 1] if dy else 1 - u[..., 1]
            for dz in (0, 1):
                wz = u[..., 2] if dz else 1 - u[..., 2]
                h = _P[_P[_P[(x + dx) & 255] + ((y + dy) & 255)] + ((z + dz) & 255)]
                g = _G[h]
                d = g[..., 0] * (f[..., 0] - dx) + g[..., 1] * (f[..., 1] - dy) + g[..., 2] * (f[..., 2] - dz)
                out = out + wx * wy * wz * d
    return out * 1.6


def fbm(p, octaves=4, lac=2.03, gain=0.5):
    p = np.asarray(p, dtype=np.float32)
    a, s, n = 1.0, 0.0, 0.0
    for i in range(octaves):
        s = s + a * perlin(p + i * 17.3)
        n += a
        a *= gain
        p = p * lac
    return s / n


def ridged(p, octaves=4):
    return 1 - np.abs(fbm(p, octaves)) * 2


def worley(p, want_id=False):
    """Celdas tipo piedras: F1 (distancia a la semilla) y F2. También un id aleatorio por celda."""
    p = np.asarray(p, dtype=np.float32)
    pi = np.floor(p).astype(np.int32)
    f1 = np.full(p.shape[:-1], 9.0, dtype=np.float32)
    f2 = np.full(p.shape[:-1], 9.0, dtype=np.float32)
    ids = np.zeros(p.shape[:-1], dtype=np.int32)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                cx = pi[..., 0] + dx
                cy = pi[..., 1] + dy
                cz = pi[..., 2] + dz
                h = _P[_P[_P[cx & 255] + (cy & 255)] + (cz & 255)]
                jit = _J[h]
                dd = (cx + jit[..., 0] - p[..., 0]) ** 2 + (cy + jit[..., 1] - p[..., 1]) ** 2 + (cz + jit[..., 2] - p[..., 2]) ** 2
                closer = dd < f1
                f2 = np.where(closer, f1, np.minimum(f2, dd))
                ids = np.where(closer, h, ids)
                f1 = np.where(closer, dd, f1)
    f1, f2 = np.sqrt(f1), np.sqrt(f2)
    return (f1, f2, ids) if want_id else (f1, f2)


# ---------- SDF: formas básicas (x, y, z son arrays) ----------
def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def extrude(d2, z, h, r):
    """Da altura h (mitad) a una forma 2D, redondeando los cantos con radio r."""
    dx = d2 + r
    dz = np.abs(z) - h + r
    return np.minimum(np.maximum(dx, dz), 0) + np.sqrt(np.maximum(dx, 0) ** 2 + np.maximum(dz, 0) ** 2) - r


def sd_ellipse_xy(x, y, rx, ry):
    q = np.sqrt((x / rx) ** 2 + (y / ry) ** 2) + 1e-6
    return (q - 1) * np.minimum(rx, ry)


def sd_box(x, y, z, bx, by, bz, r=0.0):
    qx, qy, qz = np.abs(x) - bx + r, np.abs(y) - by + r, np.abs(z) - bz + r
    out = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2 + np.maximum(qz, 0) ** 2)
    return out + np.minimum(np.maximum(qx, np.maximum(qy, qz)), 0) - r


def sd_ellipsoid(x, y, z, rx, ry, rz):
    k0 = np.sqrt((x / rx) ** 2 + (y / ry) ** 2 + (z / rz) ** 2) + 1e-6
    k1 = np.sqrt((x / rx ** 2) ** 2 + (y / ry ** 2) ** 2 + (z / rz ** 2) ** 2) + 1e-6
    return k0 * (k0 - 1) / k1


# ---------- De SDF a malla (Surface Nets) ----------
def surface_nets(vol, origin, h):
    inside = vol < 0
    c = (inside[:-1, :-1, :-1].astype(np.int8) + inside[1:, :-1, :-1] + inside[:-1, 1:, :-1] + inside[1:, 1:, :-1]
         + inside[:-1, :-1, 1:] + inside[1:, :-1, 1:] + inside[:-1, 1:, 1:] + inside[1:, 1:, 1:])
    active = (c > 0) & (c < 8)
    idx = np.argwhere(active)
    vid = np.full(active.shape, -1, dtype=np.int32)
    vid[active] = np.arange(len(idx), dtype=np.int32)
    offs = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0], [0, 0, 1], [1, 0, 1], [0, 1, 1], [1, 1, 1]], dtype=np.float32)
    vals = np.stack([vol[idx[:, 0] + int(o[0]), idx[:, 1] + int(o[1]), idx[:, 2] + int(o[2])] for o in offs], 1)
    edges = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]
    acc = np.zeros((len(idx), 3), dtype=np.float32)
    cnt = np.zeros(len(idx), dtype=np.float32)
    for a, b in edges:
        va, vb = vals[:, a], vals[:, b]
        m = (va < 0) != (vb < 0)
        t = va[m] / (va[m] - vb[m])
        acc[m] += offs[a] + t[:, None] * (offs[b] - offs[a])
        cnt[m] += 1
    verts = (idx + acc / cnt[:, None]) * h + origin
    quads = []
    s = inside[:-1, :, :] != inside[1:, :, :]
    s[:, 0, :] = s[:, -1, :] = s[:, :, 0] = s[:, :, -1] = False
    i, j, k = np.nonzero(s)
    q = np.stack([vid[i, j - 1, k - 1], vid[i, j, k - 1], vid[i, j, k], vid[i, j - 1, k]], 1)
    fl = ~inside[i, j, k]
    q[fl] = q[fl][:, ::-1]
    quads.append(q)
    s = inside[:, :-1, :] != inside[:, 1:, :]
    s[0, :, :] = s[-1, :, :] = s[:, :, 0] = s[:, :, -1] = False
    i, j, k = np.nonzero(s)
    q = np.stack([vid[i - 1, j, k - 1], vid[i - 1, j, k], vid[i, j, k], vid[i, j, k - 1]], 1)
    fl = ~inside[i, j, k]
    q[fl] = q[fl][:, ::-1]
    quads.append(q)
    s = inside[:, :, :-1] != inside[:, :, 1:]
    s[0, :, :] = s[-1, :, :] = s[:, 0, :] = s[:, -1, :] = False
    i, j, k = np.nonzero(s)
    q = np.stack([vid[i - 1, j - 1, k], vid[i, j - 1, k], vid[i, j, k], vid[i - 1, j, k]], 1)
    fl = ~inside[i, j, k]
    q[fl] = q[fl][:, ::-1]
    quads.append(q)
    return verts.astype(np.float32), np.concatenate(quads, 0).astype(np.int32)


def sdf_field(fn, bmin, bmax, voxel, detail=None, band=None):
    """Evalúa la forma en una rejilla. detail(p, d) añade el relieve caro solo cerca de la superficie."""
    bmin = np.array(bmin, dtype=np.float32)
    bmax = np.array(bmax, dtype=np.float32)
    n = np.ceil((bmax - bmin) / voxel).astype(int) + 1
    xs = bmin[0] + np.arange(n[0], dtype=np.float32) * voxel
    ys = bmin[1] + np.arange(n[1], dtype=np.float32) * voxel
    zs = bmin[2] + np.arange(n[2], dtype=np.float32) * voxel
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij", sparse=False, copy=True)
    vol = fn(X, Y, Z).astype(np.float32)
    if detail is not None:
        band = band if band is not None else 8 * voxel
        m = np.abs(vol) < band
        vol[m] = detail(X[m], Y[m], Z[m], vol[m])
    return vol, bmin, voxel


# ---------- Crear objetos en Blender ----------
def mesh_obj(name, verts, faces, material=None, parent=None):
    faces = np.asarray(faces, dtype=np.int32)
    verts = np.asarray(verts, dtype=np.float32)
    me = bpy.data.meshes.new(name)
    if faces.ndim == 2:
        n = faces.shape[1]
        me.vertices.add(len(verts))
        me.vertices.foreach_set("co", verts.ravel())
        me.loops.add(len(faces) * n)
        me.loops.foreach_set("vertex_index", faces.ravel())
        me.polygons.add(len(faces))
        me.polygons.foreach_set("loop_start", np.arange(len(faces), dtype=np.int32) * n)
        me.update(calc_edges=True)
    else:
        me.from_pydata(verts.tolist(), [], [list(f) for f in faces])
        me.update()
    me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if material is not None:
        me.materials.append(material)
    if parent is not None:
        ob.parent = parent
    return ob


def sdf_obj(name, fn, bmin, bmax, voxel, material, color_fn=None, detail=None, band=None, parent=None, rough_fn=None):
    vol, origin, h = sdf_field(fn, bmin, bmax, voxel, detail, band)
    v, q = surface_nets(vol, origin, h)
    del vol
    ob = mesh_obj(name, v, q, material, parent)
    if color_fn is not None:
        set_colors(ob, color_fn(v[:, 0], v[:, 1], v[:, 2]))
    if rough_fn is not None:
        set_scalar(ob, "rough", rough_fn(v[:, 0], v[:, 1], v[:, 2]))
    print(f"[{name}] verts={len(v):,}")
    return ob


def set_colors(ob, rgb, name="col"):
    rgb = np.asarray(rgb, dtype=np.float32)
    rgba = np.concatenate([rgb, np.ones((len(rgb), 1), dtype=np.float32)], 1)
    a = ob.data.color_attributes.new(name, "FLOAT_COLOR", "POINT")
    a.data.foreach_set("color", rgba.ravel())


def set_scalar(ob, name, values):
    a = ob.data.attributes.new(name, "FLOAT", "POINT")
    a.data.foreach_set("value", np.asarray(values, dtype=np.float32).ravel())


def empty(name="pivot", parent=None):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    if parent is not None:
        e.parent = parent
    return e


def catmull(points, per=10):
    """Suaviza una lista de puntos con una curva que pasa por todos ellos."""
    pts = np.asarray(points, dtype=np.float32)
    pts = np.vstack([pts[0], pts, pts[-1]])
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for t in np.linspace(0, 1, per, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(pts[-2])
    return np.array(out, dtype=np.float32)


def lathe(name, profile, material, segments=160, parent=None, per=10, close_ends=True, shape=None):
    """Hace girar un perfil (radio, altura) alrededor del eje Z, como en un torno de alfarero.
    shape(theta) -> (ax, ay) permite deformar el círculo (un plato rectangular, por ejemplo)."""
    prof = catmull(profile, per)
    th = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    ax, ay = np.cos(th), np.sin(th)
    if shape is not None:
        ax, ay = shape(th)
    m = len(prof)
    verts = np.zeros((m * segments, 3), dtype=np.float32)
    verts[:, 0] = np.outer(prof[:, 0], ax).ravel()
    verts[:, 1] = np.outer(prof[:, 0], ay).ravel()
    verts[:, 2] = np.repeat(prof[:, 1], segments)
    faces = []
    a = np.arange(m - 1)[:, None] * segments
    b = np.arange(segments)[None, :]
    i0 = (a + b).ravel()
    i1 = (a + (b + 1) % segments).ravel()
    i2 = i1 + segments
    i3 = i0 + segments
    faces = np.stack([i0, i1, i2, i3], 1)
    return mesh_obj(name, verts, faces, material, parent)


def tube(name, path, radius, material, segments=24, parent=None, per=12):
    """Un tubo a lo largo de una curva (asa de la taza, palillo...). radius: número o lista por punto."""
    pts = catmull(path, per)
    n = len(pts)
    rad = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(radius)), radius) if np.ndim(radius) else np.full(n, radius)
    tang = np.gradient(pts, axis=0)
    tang /= np.linalg.norm(tang, axis=1, keepdims=True)
    up = np.array([0.0, 1.0, 0.0])
    if abs(np.dot(up, tang[0])) > 0.9:
        up = np.array([1.0, 0.0, 0.0])
    nor = np.cross(tang, up)
    nor /= np.linalg.norm(nor, axis=1, keepdims=True) + 1e-8
    bin_ = np.cross(tang, nor)
    th = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    verts = (pts[:, None, :] + rad[:, None, None] * (np.cos(th)[None, :, None] * nor[:, None, :] + np.sin(th)[None, :, None] * bin_[:, None, :])).reshape(-1, 3)
    a = np.arange(n - 1)[:, None] * segments
    b = np.arange(segments)[None, :]
    i0 = (a + b).ravel()
    i1 = (a + (b + 1) % segments).ravel()
    faces = np.stack([i0, i1, i1 + segments, i0 + segments], 1)
    return mesh_obj(name, verts, faces, material, parent)


# ---------- Materiales ----------
def _principled(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree.nodes, m.node_tree.links, m.node_tree.nodes["Principled BSDF"]


def plain_mat(name, color, rough=0.4, metal=0.0, coat=0.0, coat_rough=0.05, spec=0.5, sss=0.0, sss_scale=0.05, transmission=0.0, ior=1.45):
    m, n, l, b = _principled(name)
    c = lin(color) if isinstance(color, str) else color
    b.inputs["Base Color"].default_value = (float(c[0]), float(c[1]), float(c[2]), 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = coat_rough
    b.inputs["Specular IOR Level"].default_value = spec
    b.inputs["Subsurface Weight"].default_value = sss
    b.inputs["Subsurface Scale"].default_value = sss_scale
    b.inputs["Transmission Weight"].default_value = transmission
    b.inputs["IOR"].default_value = ior
    return m


def food_mat(name, rough=0.45, sss=0.2, sss_scale=0.06, sss_radius=(1.0, 0.45, 0.2), spec=0.5, coat=0.0, coat_rough=0.2, sheen=0.0,
             bump_scale=220.0, bump_strength=0.15, bump_dist=0.004, rough_attr=False):
    """Material de comida: el color viene punto a punto de la malla ('col') y la luz penetra un poco (subsurface)."""
    m, n, l, b = _principled(name)
    at = n.new("ShaderNodeAttribute")
    at.attribute_name = "col"
    l.new(at.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Subsurface Weight"].default_value = sss
    b.inputs["Subsurface Scale"].default_value = sss_scale
    b.inputs["Subsurface Radius"].default_value = sss_radius
    b.inputs["Specular IOR Level"].default_value = spec
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = coat_rough
    b.inputs["Sheen Weight"].default_value = sheen
    if rough_attr:
        ar = n.new("ShaderNodeAttribute")
        ar.attribute_name = "rough"
        l.new(ar.outputs["Fac"], b.inputs["Roughness"])
    if bump_strength > 0:
        tc = n.new("ShaderNodeTexCoord")
        no = n.new("ShaderNodeTexNoise")
        no.inputs["Scale"].default_value = bump_scale
        no.inputs["Detail"].default_value = 6
        no.inputs["Roughness"].default_value = 0.6
        l.new(tc.outputs["Object"], no.inputs["Vector"])
        bu = n.new("ShaderNodeBump")
        bu.inputs["Strength"].default_value = bump_strength
        bu.inputs["Distance"].default_value = bump_dist
        l.new(no.outputs["Fac"], bu.inputs["Height"])
        l.new(bu.outputs["Normal"], b.inputs["Normal"])
    return m


def ceramic_mat(name="ceramica", color="#FBF9F4"):
    return plain_mat(name, color, rough=0.12, coat=1.0, coat_rough=0.03, sss=0.05, sss_scale=0.02)


def wood_mat(name="madera", a="#C99A63", b="#8A5A2B"):
    """Madera procedural: veta fina y alargada en el eje X, con poco contraste."""
    m, n, l, p = _principled(name)
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.32, 7.0, 7.0)
    l.new(tc.outputs["Object"], mp.inputs["Vector"])
    no = n.new("ShaderNodeTexNoise")
    no.inputs["Scale"].default_value = 3.0
    no.inputs["Detail"].default_value = 10
    no.inputs["Roughness"].default_value = 0.62
    no.inputs["Distortion"].default_value = 0.6
    l.new(mp.outputs["Vector"], no.inputs["Vector"])
    mp2 = n.new("ShaderNodeMapping")
    mp2.inputs["Scale"].default_value = (0.5, 1.6, 1.6)
    l.new(tc.outputs["Object"], mp2.inputs["Vector"])
    no2 = n.new("ShaderNodeTexNoise")
    no2.inputs["Scale"].default_value = 1.6
    no2.inputs["Detail"].default_value = 5
    l.new(mp2.outputs["Vector"], no2.inputs["Vector"])
    mx = n.new("ShaderNodeMath")
    mx.operation = "MULTIPLY_ADD"
    mx.inputs[1].default_value = 0.72
    l.new(no.outputs["Fac"], mx.inputs[0])
    l2 = n.new("ShaderNodeMath")
    l2.operation = "MULTIPLY"
    l2.inputs[1].default_value = 0.28
    l.new(no2.outputs["Fac"], l2.inputs[0])
    l.new(l2.outputs[0], mx.inputs[2])
    ramp = n.new("ShaderNodeValToRGB")
    ca, cb = lin(a), lin(b)
    ramp.color_ramp.elements[0].position = 0.36
    ramp.color_ramp.elements[0].color = (float(cb[0]), float(cb[1]), float(cb[2]), 1)
    ramp.color_ramp.elements[1].position = 0.62
    ramp.color_ramp.elements[1].color = (float(ca[0]), float(ca[1]), float(ca[2]), 1)
    l.new(mx.outputs[0], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = 0.5
    bu = n.new("ShaderNodeBump")
    bu.inputs["Strength"].default_value = 0.1
    bu.inputs["Distance"].default_value = 0.008
    l.new(no.outputs["Fac"], bu.inputs["Height"])
    l.new(bu.outputs["Normal"], p.inputs["Normal"])
    return m


# ---------- Plató: render, luces, cámara ----------
def new_scene(res=1000, samples=96, seed=1):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == "METAL"
    s.cycles.device = "GPU"
    s.cycles.samples = samples
    s.cycles.use_adaptive_sampling = True
    s.cycles.adaptive_threshold = 0.015
    s.cycles.use_denoising = True
    s.cycles.denoiser = "OPENIMAGEDENOISE"
    s.cycles.seed = seed
    s.cycles.max_bounces = 8
    s.cycles.caustics_reflective = False
    s.cycles.caustics_refractive = False
    s.render.film_transparent = True
    s.render.resolution_x = res
    s.render.resolution_y = res
    s.render.resolution_percentage = 100
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_mode = "RGBA"
    s.render.image_settings.color_depth = "8"
    s.render.image_settings.compression = 15
    s.render.use_persistent_data = True
    s.view_settings.view_transform = "Khronos PBR Neutral"
    s.view_settings.look = "None"
    s.view_settings.exposure = 0.0
    s.view_settings.gamma = 1.0
    return s


def add_light(name, loc, target, size, energy, color="#FFFFFF", size_y=None):
    li = bpy.data.lights.new(name, "AREA")
    li.shape = "RECTANGLE"
    li.size = size
    li.size_y = size_y if size_y is not None else size
    li.energy = energy
    c = lin(color)
    li.color = (float(c[0]), float(c[1]), float(c[2]))
    ob = bpy.data.objects.new(name, li)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y")
    return ob


def studio(target=(0, 0, 0.2), scale=1.0, key=1.0, world=0.32, warm="#FFF1DF", cool="#EAF2FF"):
    """Luz de estudio de foto de producto: principal suave arriba-izquierda, contraluz y relleno."""
    s = bpy.context.scene
    t = np.array(target)
    add_light("principal", t + np.array([-2.2, -2.4, 3.8]) * scale, target, 6.0 * scale, 120 * key * scale ** 2, warm)
    add_light("contraluz", t + np.array([2.2, 3.0, 2.6]) * scale, target, 4.0 * scale, 70 * key * scale ** 2, "#FFFFFF")
    add_light("relleno", t + np.array([3.4, -2.6, 1.0]) * scale, target, 3.6 * scale, 16 * key * scale ** 2, cool)
    w = bpy.data.worlds.new("mundo")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    c = lin("#F4EFE6")
    bg.inputs["Color"].default_value = (float(c[0]), float(c[1]), float(c[2]), 1)
    bg.inputs["Strength"].default_value = world
    s.world = w


def shadow_catcher(size=30, z=0.0):
    """Suelo invisible que solo recoge sombras: así la comida 'se apoya' sobre el fondo de la web."""
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z))
    ob = bpy.context.active_object
    ob.name = "suelo"
    ob.is_shadow_catcher = True
    return ob


def camera(pos, target, lens=70, dof=None):
    cam = bpy.data.cameras.new("camara")
    cam.lens = lens
    cam.sensor_width = 36
    cam.clip_start = 0.05
    cam.clip_end = 200
    ob = bpy.data.objects.new("camara", cam)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.scene.camera = ob
    aim(ob, pos, target)
    if dof:
        cam.dof.use_dof = True
        cam.dof.focus_distance = (Vector(pos) - Vector(target)).length
        cam.dof.aperture_fstop = dof
    return ob


def aim(ob, pos, target):
    ob.location = pos
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = (Vector(target) - Vector(pos)).to_track_quat("-Z", "Y")


def orbit(dist, elev_deg, azim_deg, target=(0, 0, 0)):
    e, a = math.radians(elev_deg), math.radians(azim_deg)
    return (target[0] + dist * math.cos(e) * math.cos(a), target[1] + dist * math.cos(e) * math.sin(a), target[2] + dist * math.sin(e))


def render_to(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def ease_io(t):
    t = max(0.0, min(1.0, t))
    return t * t * t * (t * (6 * t - 15) + 10)


def ease_out_bounce(t):
    t = max(0.0, min(1.0, t))
    if t < 1 / 2.75:
        return 7.5625 * t * t
    if t < 2 / 2.75:
        t -= 1.5 / 2.75
        return 7.5625 * t * t + 0.75
    if t < 2.5 / 2.75:
        t -= 2.25 / 2.75
        return 7.5625 * t * t + 0.9375
    t -= 2.625 / 2.75
    return 7.5625 * t * t + 0.984375
