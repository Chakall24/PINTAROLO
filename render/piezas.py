# =====================================================================
# piezas.py: el "almacén" de alimentos. Cada función crea una pieza en Blender.
# Se comparten entre escenas para que todo parezca salido de la misma cocina.
# Coordenadas: la pieza se apoya sobre z = z0, salvo que se indique otra cosa.
# =====================================================================
import bpy
import numpy as np
from mathutils import Matrix

from lib import (
    extrude, fbm, food_mat, lathe, lin, mesh_obj, mix, perlin, plain_mat, ridged, sd_box, sd_ellipse_xy,
    sd_ellipsoid, sdf_obj, set_colors, smax, smin, smooth, tube, worley, ceramic_mat, wood_mat, _principled,
)


def hoja(name, X, Y, Z, grosor, mat, parent=None, nor=None):
    """Lámina fina con dos caras y borde cerrado (lechuga, jamón, queso, cuchara...)."""
    nu, nv = X.shape
    top = np.stack([X, Y, Z + grosor], -1).reshape(-1, 3)
    bot = np.stack([X, Y, Z], -1).reshape(-1, 3)
    verts = np.vstack([top, bot]).astype(np.float32)
    a = np.arange(nu - 1)[:, None] * nv
    b = np.arange(nv - 1)[None, :]
    i0 = (a + b).ravel()
    i1, i2, i3 = i0 + 1, i0 + 1 + nv, i0 + nv
    off = nu * nv
    idx = np.arange(nu * nv).reshape(nu, nv)
    faces = np.vstack([
        np.stack([i0, i3, i2, i1], 1),
        np.stack([i0 + off, i1 + off, i2 + off, i3 + off], 1),
        np.stack([idx[:-1, 0], idx[1:, 0], idx[1:, 0] + off, idx[:-1, 0] + off], 1),
        np.stack([idx[1:, -1], idx[:-1, -1], idx[:-1, -1] + off, idx[1:, -1] + off], 1),
        np.stack([idx[0, 1:], idx[0, :-1], idx[0, :-1] + off, idx[0, 1:] + off], 1),
        np.stack([idx[-1, :-1], idx[-1, 1:], idx[-1, 1:] + off, idx[-1, :-1] + off], 1),
    ])
    return mesh_obj(name, verts, faces, mat, parent)


def dup2(a):
    return np.concatenate([a.ravel(), a.ravel()])


# ---------- Pan ----------
def miga_corteza(p, borde, crust_w=0.03):
    """Color de pan: borde > 0 es corteza; negativo, miga."""
    t = smooth(-crust_w - 0.012, -crust_w + 0.012, borde + 0.006 * fbm(p * 26, 2))
    f1, _ = worley(p * 15)
    crumb = mix(lin("#F4E7C8"), lin("#E3CB98"), smooth(0.33, 0.14, f1))
    crumb = crumb * (0.97 + 0.07 * fbm(p * 38, 2))[..., None]
    tostado = 0.5 + 0.5 * fbm(p * np.array([20, 20, 44]) + 3, 4)
    crust = mix(lin("#C98F45"), lin("#A96E2E"), smooth(0.3, 0.72, tostado))
    return mix(crumb, crust, t)


def rebanada(name="pan", rx=0.47, ry=0.33, alto=0.135, z0=0.0, parent=None, voxel=0.0042):
    cz = z0 + alto / 2

    def base(x, y, z):
        return extrude(sd_ellipse_xy(x, y, rx, ry), z - cz, alto / 2, 0.02)

    def detalle(x, y, z, d):
        p = np.stack([x, y, z], -1)
        d = d + 0.0035 * fbm(p * np.array([7, 7, 14]), 3) + 0.0014 * fbm(p * 60, 2)
        borde = sd_ellipse_xy(x, y, rx, ry)
        miga = smooth(-0.024, -0.05, borde)
        f1, _ = worley(p * 15)
        f1b, _ = worley(p * 34 + 9)
        agujeros = np.maximum((0.27 - f1) * 0.10, (0.26 - f1b) * 0.038)
        return np.maximum(d, np.where(miga > 0, agujeros * miga, -1))

    def color(x, y, z):
        return miga_corteza(np.stack([x, y, z], -1), sd_ellipse_xy(x, y, rx, ry))

    mat = food_mat(name + "_mat", rough=0.74, sss=0.25, sss_scale=0.05, sss_radius=(1, 0.7, 0.4), bump_scale=260, bump_strength=0.25)
    return sdf_obj(name, base, (-rx - 0.03, -ry - 0.03, z0 - 0.03), (rx + 0.03, ry + 0.03, z0 + alto + 0.03), voxel, mat, color, detalle, parent=parent)


# ---------- Porción de tortilla de patata ----------
def tortilla_porcion(name="tortilla", R=0.70, alto=0.36, ang=58, z0=0.13, cx=-0.34, parent=None, voxel=0.004):
    a = np.radians(ang / 2)
    n1 = np.array([-np.sin(a), np.cos(a)])
    n2 = np.array([-np.sin(a), -np.cos(a)])
    cz = z0 + alto / 2
    esc = np.array([6.5, 6.5, 15.0])  # láminas de patata: anchas y aplastadas

    def partes(x, y, z):
        xr = x - cx
        rad = np.sqrt(xr ** 2 + y ** 2)
        cil = extrude(rad - R, z - cz, alto / 2, 0.095)
        cu = np.maximum(xr * n1[0] + y * n1[1], xr * n2[0] + y * n2[1])
        return cil, cu

    def base(x, y, z):
        cil, cu = partes(x, y, z)
        return smax(cil, cu, 0.022)

    def detalle(x, y, z, d):
        p = np.stack([x, y, z], -1)
        cil, cu = partes(x, y, z)
        q = p + 0.03 * np.stack([perlin(p * 7), perlin(p * 7 + 5), perlin(p * 7 + 9)], -1)
        f1, f2 = worley(q * esc)
        cara = smooth(-0.05, -0.002, cu)
        d = d + cara * (0.002 - 0.0035 * smooth(0.0, 0.3, f2 - f1)) + cara * 0.006 * fbm(p * 22, 3)
        pf1, _ = worley(p * 46)
        d = d + cara * 0.007 * smooth(0.16, 0.04, pf1)
        d = d + (1 - cara) * 0.012 * fbm(p * np.array([7, 7, 3]), 3)
        return d + 0.0016 * fbm(p * 70, 2)

    def color(x, y, z):
        p = np.stack([x, y, z], -1)
        cil, cu = partes(x, y, z)
        q = p + 0.03 * np.stack([perlin(p * 7), perlin(p * 7 + 5), perlin(p * 7 + 9)], -1)
        f1, f2, ids = worley(q * esc, want_id=True)
        var = (ids % 9) / 9.0
        patata = mix(lin("#F6E3A0"), lin("#EFD27E"), var)
        huevo = lin("#EBC552")
        roto = smooth(-0.15, 0.35, fbm(p * 8 + 2, 3))
        interior = mix(patata, huevo, (1 - smooth(0.0, 0.26, f2 - f1 + 0.10 * fbm(p * 22, 2))) * 0.55 * roto)
        interior = interior * (0.97 + 0.08 * fbm(p * 30, 3))[..., None]
        pf1, _ = worley(p * 46)
        interior = mix(interior, lin("#C79A3C"), smooth(0.16, 0.04, pf1) * 0.7)
        tost = 0.5 + 0.5 * fbm(p * 8 + 5, 5)
        costra = mix(lin("#EDC463"), lin("#D59D3C"), smooth(0.36, 0.62, tost))
        costra = mix(costra, lin("#A36C24"), smooth(0.64, 0.84, tost) * 0.55)
        t = smooth(-0.012, -0.05, cu) * smooth(-0.07, -0.018, cil)
        return mix(interior, costra, t)

    mat = food_mat(name + "_mat", rough=0.46, sss=0.5, sss_scale=0.06, sss_radius=(1, 0.7, 0.3), coat=0.2, coat_rough=0.35, bump_scale=180, bump_strength=0.18)
    return sdf_obj(name, base, (cx - 0.03, -R - 0.03, z0 - 0.03), (cx + R + 0.03, R + 0.03, z0 + alto + 0.03), voxel, mat, color, detalle, parent=parent)


# ---------- Palillo y aceituna ----------
def palillo(name="palillo", base=(0, 0, 0.1), alto=0.82, tilt=(0.05, 0.03), parent=None):
    mat = plain_mat(name + "_mat", "#D9B57E", rough=0.55)
    b = np.array(base, dtype=np.float32)
    top = b + np.array([tilt[0], tilt[1], alto], dtype=np.float32)
    return tube(name, [b, (b + top) / 2, top], [0.004, 0.0105, 0.0105, 0.004], mat, segments=14, parent=parent)


def aceituna(name="aceituna", centro=(0, 0, 0.8), r=0.085, parent=None, voxel=0.0035, color_a="#7E8B2E", color_b="#566420"):
    c = np.array(centro, dtype=np.float32)

    def base(x, y, z):
        return sd_ellipsoid(x - c[0], y - c[1], z - c[2], r * 0.86, r * 0.86, r * 1.14)

    def color(x, y, z):
        t = 0.5 + 0.5 * fbm(np.stack([x, y, z], -1) * 14, 3)
        return mix(lin(color_a), lin(color_b), smooth(0.35, 0.72, t))

    mat = food_mat(name + "_mat", rough=0.16, sss=0.35, sss_scale=0.03, sss_radius=(0.8, 1, 0.3), coat=0.7, coat_rough=0.1, bump_strength=0.04)
    return sdf_obj(name, base, c - r * 1.3, c + r * 1.3, voxel, mat, color, parent=parent)


# ---------- Jamón ----------
def jamon_mat():
    return food_mat("jamon_mat", rough=0.30, sss=0.75, sss_scale=0.05, sss_radius=(1, 0.3, 0.2), coat=0.35, coat_rough=0.25, bump_scale=320, bump_strength=0.12)


def loncha_jamon(name="jamon", largo=0.95, ancho=0.46, pliegues=2.6, amp=0.10, seed=0.0, parent=None, mat=None, nu=260, nv=90, fase=0.0, pos=(0, 0, 0), rot=0.0, curva=0.0):
    u = np.linspace(0, 1, nu, dtype=np.float32)
    v = np.linspace(0, 1, nv, dtype=np.float32)
    U, V = np.meshgrid(u, v, indexing="ij")
    p = np.stack([U * 4 + seed, V * 2 + seed * 2, np.zeros_like(U) + seed], -1)
    ang = U * np.pi * 2 * pliegues + fase + 2.2 * fbm(p, 2) + V * 1.3
    s = np.sin(ang)
    X = (U - 0.5) * largo + 0.05 * np.cos(ang)  # el pliegue vuelve un poco sobre sí mismo
    Z = amp * (0.5 + 0.5 * s) ** 1.4 * (0.72 + 0.28 * np.sin(V * np.pi)) + 0.018 * fbm(p * 2, 2) + curva * (U - 0.5) ** 2
    Y = (V - 0.5) * ancho * (0.88 + 0.12 * np.sin(U * np.pi)) + 0.025 * np.sin(ang * 0.5 + V * 3) + 0.02 * fbm(p * 1.5 + 4, 2)
    c, sn = np.cos(rot), np.sin(rot)
    X2, Y2 = X * c - Y * sn + pos[0], X * sn + Y * c + pos[1]
    ob = hoja(name, X2, Y2, Z + pos[2], 0.009, mat or jamon_mat(), parent)
    uu, vv = dup2(U), dup2(V)
    q = np.stack([uu * 5 + seed, vv * 2.4 + seed, np.zeros_like(uu) + seed * 3], -1)
    vena = smooth(0.80, 0.97, ridged(q * np.array([1.2, 3.6, 1]), 3))
    tono = 0.5 + 0.5 * fbm(q * 1.5, 3)
    carne = mix(lin("#7E1A26"), lin("#AE3A46"), tono)
    carne = mix(carne, lin("#E5A79C"), vena * 0.42)
    grasa = np.clip(smooth(0.05, 0.012, vv + 0.012 * fbm(q * 4, 2)), 0, 1)
    set_colors(ob, mix(carne, lin("#F4E4C6"), grasa))
    return ob


# ---------- Empanada (como las de su barra) ----------
def empanada(name="empanada", lado=0.72, alto=0.27, z0=0.0, parent=None, voxel=0.0042):
    a0 = np.array([-lado * 0.55, -lado * 0.62])
    a1 = np.array([lado * 0.75, 0.0])
    a2 = np.array([-lado * 0.55, lado * 0.62])
    pts = [a0, a1, a2]

    def tri(x, y):
        d = -1e9
        for i in range(3):
            a, b = pts[i], pts[(i + 1) % 3]
            e = b - a
            n = np.array([e[1], -e[0]]) / np.linalg.norm(e)
            d = np.maximum(d, (x - a[0]) * n[0] + (y - a[1]) * n[1])
        return d

    def base(x, y, z):
        t = tri(x, y)
        dome = alto * (0.55 + 0.45 * smooth(0.0, -0.22, t))
        zr = z - z0
        return smax(smax(t + 0.03, -zr, 0.03), (zr - dome) * 0.75, 0.05) - 0.012

    def detalle(x, y, z, d):
        p = np.stack([x, y, z], -1)
        hoja_ = np.sin(z * 150 + 4 * fbm(p * 6, 2)) * 0.0024
        corte = x < -lado * 0.53
        return d + 0.006 * fbm(p * 7, 3) + np.where(corte, hoja_ * 1.5, 0.0) + 0.0016 * ridged(p * 20, 3) * (z > z0 + alto * 0.5)

    def color(x, y, z):
        p = np.stack([x, y, z], -1)
        tost = 0.5 + 0.5 * fbm(p * 26 + 2, 4)
        masa = mix(lin("#DBA34E"), lin("#C8903C"), smooth(0.30, 0.70, tost))
        masa = mix(masa, lin("#99601F"), smooth(0.70, 0.86, tost) * 0.45)
        tono = 0.5 + 0.5 * fbm(p * 3.5 + 7, 3)
        masa = mix(masa, lin("#B9792C"), smooth(0.45, 0.75, tono) * 0.45)
        # Cara cortada: hojaldre pálido y relleno de atún y pimiento.
        corte = smooth(-lado * 0.50, -lado * 0.545, x)
        zr = z - z0
        rel = smooth(0.05, 0.075, zr) * smooth(0.19, 0.165, zr)
        grumo = 0.5 + 0.5 * fbm(p * 34, 3)
        relleno = mix(lin("#B8431E"), lin("#6E3A1C"), smooth(0.38, 0.62, grumo))
        relleno = mix(relleno, lin("#E3B35D"), smooth(0.62, 0.72, grumo))
        pale = mix(lin("#F1D79A"), lin("#D9AE63"), 0.5 + 0.5 * np.sin(z * 150))
        cara = mix(pale, relleno, rel)
        return mix(masa, cara, corte)

    mat = food_mat(name + "_mat", rough=0.36, sss=0.3, sss_scale=0.05, sss_radius=(1, 0.6, 0.3), coat=0.6, coat_rough=0.18, bump_scale=240, bump_strength=0.12)
    return sdf_obj(name, base, (-lado * 0.7, -lado * 0.8, z0 - 0.05), (lado * 0.9, lado * 0.8, z0 + alto + 0.05), voxel, mat, color, detalle, parent=parent)


# ---------- Pincho moruno ----------
def pincho_moruno(name="moruno", n=5, parent=None, voxel=0.0042, z0=0.22):
    rs = np.random.RandomState(4)
    cen = [(-0.64 + i * 0.32, rs.uniform(-0.012, 0.012), z0 + rs.uniform(-0.012, 0.012)) for i in range(n)]
    rots = rs.uniform(-0.5, 0.5, size=(n, 2))
    tam = rs.uniform(0.13, 0.165, size=(n, 3))

    def base(x, y, z):
        d = 1e9
        for i, c in enumerate(cen):
            xr, yr, zr = x - c[0], y - c[1], z - c[2]
            ca, sa = np.cos(rots[i, 0]), np.sin(rots[i, 0])
            y2 = yr * ca - zr * sa
            z2 = yr * sa + zr * ca
            cb, sb = np.cos(rots[i, 1]), np.sin(rots[i, 1])
            x2 = xr * cb - y2 * sb
            y3 = xr * sb + y2 * cb
            d = np.minimum(d, sd_box(x2, y3, z2, tam[i, 0], tam[i, 1], tam[i, 2], 0.05))
        return d

    def detalle(x, y, z, d):
        p = np.stack([x, y, z], -1)
        return d + 0.024 * fbm(p * 8, 3) + 0.0065 * ridged(p * 34, 3) + 0.002 * fbm(p * 90, 2)

    def color(x, y, z):
        p = np.stack([x, y, z], -1)
        t = 0.5 + 0.5 * fbm(p * 13, 5)
        c = mix(lin("#B9601F"), lin("#7C3312"), smooth(0.34, 0.6, t))
        c = mix(c, lin("#2C1408"), smooth(0.57, 0.74, t) * 0.92)
        sp = 0.5 + 0.5 * perlin(p * 150)
        c = mix(c, lin("#D2401C"), smooth(0.68, 0.8, sp) * 0.6)
        return mix(c, lin("#EFA93E"), smooth(0.28, 0.2, t) * 0.5)

    mat = food_mat(name + "_mat", rough=0.32, sss=0.25, sss_scale=0.03, sss_radius=(1, 0.4, 0.2), coat=0.6, coat_rough=0.22, bump_scale=240, bump_strength=0.2)
    ob = sdf_obj(name, base, (-0.92, -0.32, z0 - 0.32), (0.92, 0.32, z0 + 0.32), voxel, mat, color, detalle, parent=parent)
    metal = plain_mat(name + "_metal", "#C9CACA", rough=0.24, metal=1.0)
    tube(name + "_varilla", [(-1.2, 0, z0), (0, 0, z0), (1.08, 0, z0)], 0.013, metal, segments=14, parent=parent)
    # Empuñadura: anilla sencilla al final de la varilla.
    tube(name + "_anilla", [(1.08, 0, z0), (1.15, 0.045, z0), (1.21, 0, z0), (1.15, -0.045, z0), (1.08, 0, z0)], 0.011, metal, segments=12, parent=parent)
    return ob


# ---------- Croissant ----------
def croissant(name="croissant", R=0.56, z0=0.0, parent=None, voxel=0.0045):
    tmax = 1.45
    cy = -0.28
    zc = z0 + 0.20

    def coords(x, y, z):
        th = np.arctan2(x, y - cy)
        tc = np.clip(th, -tmax, tmax)
        ax = R * np.sin(tc)
        ay = R * np.cos(tc) + cy
        s = tc / tmax
        return s, x - ax, y - ay, (z - zc)

    def radio(s):
        env = 0.30 * (1 - np.abs(s) ** 2.5) ** 0.62 + 0.035
        rib = np.abs(np.sin(s * np.pi * 3.5 + 0.2)) ** 0.55
        return env * (0.84 + 0.2 * rib)

    def base(x, y, z):
        s, dx, dy, dz = coords(x, y, z)
        d = np.sqrt(dx ** 2 + dy ** 2 + (dz / 0.72) ** 2) - radio(s)
        return smax(d * 0.8, z0 - z, 0.05)

    def detalle(x, y, z, d):
        p = np.stack([x, y, z], -1)
        s, dx, dy, dz = coords(x, y, z)
        phi = np.arctan2(dz, np.sqrt(dx ** 2 + dy ** 2))
        fibra = np.sin(s * 70 + phi * 2.5 + 7 * fbm(p * 5, 2))
        return d + 0.0022 * fibra + 0.012 * fbm(p * 9, 3) + 0.0035 * fbm(p * 34, 3)

    def color(x, y, z):
        p = np.stack([x, y, z], -1)
        s, dx, dy, dz = coords(x, y, z)
        rib = np.abs(np.sin(s * np.pi * 3.5 + 0.2)) ** 0.55
        tost = 0.5 + 0.5 * fbm(p * 7, 4)
        altura = smooth(0.02, 0.28, z - z0)
        c = mix(lin("#F3D189"), lin("#D99C47"), smooth(0.15, 0.75, rib))
        c = mix(c, lin("#A9692A"), smooth(0.5, 0.86, tost * 0.5 + rib * 0.25 + altura * 0.28) * 0.72)
        return c * (0.95 + 0.09 * np.sin(s * 70 + 7 * fbm(p * 5, 2)))[..., None]

    mat = food_mat(name + "_mat", rough=0.5, sss=0.35, sss_scale=0.05, sss_radius=(1, 0.6, 0.3), coat=0.18, coat_rough=0.35, bump_scale=300, bump_strength=0.25)
    return sdf_obj(name, base, (-R - 0.33, -0.55, z0 - 0.03), (R + 0.33, R + 0.1, z0 + 0.5), voxel, mat, color, detalle, parent=parent)


# ---------- Vajilla ----------
def rect_shape(a, b, n=5.0):
    """Superelipse: de círculo a rectángulo redondeado."""
    def f(th):
        c, s = np.cos(th), np.sin(th)
        return a * np.sign(c) * np.abs(c) ** (2 / n), b * np.sign(s) * np.abs(s) ** (2 / n)
    return f


def plato_rect(name="plato", a=1.5, b=0.95, z0=0.0, parent=None, mat=None):
    perfil = [(0, z0), (0.74, z0), (0.78, z0 + 0.012), (0.80, z0 + 0.03), (0.90, z0 + 0.075), (1.0, z0 + 0.11), (1.003, z0 + 0.125), (0.995, z0 + 0.135),
              (0.90, z0 + 0.10), (0.80, z0 + 0.06), (0.76, z0 + 0.042), (0.6, z0 + 0.04), (0, z0 + 0.04)]
    return lathe(name, perfil, mat or ceramic_mat(name + "_mat"), segments=256, parent=parent, per=8, shape=rect_shape(a, b))


def platillo(name="platillo", parent=None, mat=None):
    perfil = [(0, 0), (0.36, 0), (0.39, 0.012), (0.42, 0.03), (0.62, 0.085), (0.84, 0.135), (0.87, 0.15), (0.865, 0.162), (0.84, 0.155), (0.62, 0.11), (0.44, 0.058), (0.34, 0.038), (0, 0.035)]
    return lathe(name, perfil, mat or ceramic_mat(), segments=200, parent=parent, per=8)


def taza(name="taza", z0=0.035, parent=None, mat=None):
    m = mat or ceramic_mat()
    p = [(0, 0), (0.20, 0), (0.225, 0.012), (0.232, 0.04), (0.29, 0.07), (0.38, 0.17), (0.455, 0.34), (0.495, 0.52), (0.51, 0.625), (0.507, 0.643), (0.492, 0.636),
         (0.47, 0.52), (0.42, 0.33), (0.31, 0.13), (0, 0.075)]
    ob = lathe(name, [(r, z + z0) for r, z in p], m, segments=200, parent=parent, per=10)
    tube(name + "_asa", [(0.455, 0, z0 + 0.47), (0.60, 0, z0 + 0.525), (0.695, 0, z0 + 0.43), (0.635, 0, z0 + 0.285), (0.505, 0, z0 + 0.225), (0.385, 0, z0 + 0.20)],
         [0.040, 0.030, 0.027, 0.029, 0.034, 0.042], m, segments=20, parent=parent)
    return ob


def textura_cafe(size=1600):
    """Espuma de café con un corazón de cacao, como la foto de perfil de su Facebook."""
    lin_ = np.linspace(-1, 1, size, dtype=np.float32)
    X, Y = np.meshgrid(lin_, lin_, indexing="xy")
    p = np.stack([X, Y, np.zeros_like(X)], -1)
    rad = np.sqrt(X ** 2 + Y ** 2)
    n1 = fbm(p * 3.2, 4)
    n2 = fbm(p * 14, 3)
    espuma = mix(lin("#EBD6AE"), lin("#D9B883"), smooth(-0.2, 0.45, n1 + 0.3 * n2))
    aro = smooth(0.72, 0.97, rad + 0.05 * n2)
    espuma = mix(espuma, lin("#A9733A"), aro * 0.9)
    espuma = mix(espuma, lin("#5D3A1A"), smooth(0.93, 1.0, rad) * 0.8)
    # Corazón: ecuación implícita (x^2 + y^2 - 1)^3 - x^2 y^3 = 0
    hx = X / 0.50
    hy = (Y + 0.03) / 0.49
    h = (hx ** 2 + hy ** 2 - 1) ** 3 - hx ** 2 * hy ** 3
    grain = np.random.RandomState(3).random_sample(X.shape).astype(np.float32)
    bord = h + 0.05 * fbm(p * 9, 3) + 0.035 * fbm(p * 46, 2)
    cacao = smooth(0.05, -0.05, bord)
    dust = smooth(0.40, 0.72, 0.5 + 0.5 * fbm(p * 60, 2)) * smooth(1.7, 0.25, np.maximum(h, 0.0))
    motas = np.clip(cacao * (0.8 + 0.24 * grain) + (grain > 0.985) * smooth(0.5, 0.02, np.maximum(h, 0)) * 0.8 + dust * 0.05, 0, 1)
    col = mix(lin("#4E2A12"), lin("#6E4120"), 0.5 + 0.5 * fbm(p * 28, 2))
    out = mix(espuma, col, motas)
    img = bpy.data.images.new("cafe_tex", size, size, alpha=False, float_buffer=True)
    rgba = np.concatenate([out, np.ones(out.shape[:2] + (1,), dtype=np.float32)], -1)
    img.pixels.foreach_set(rgba[::-1].ravel() if False else rgba.ravel())
    img.pack()
    img.colorspace_settings.name = "Non-Color"
    return img


def superficie_cafe(name="cafe", radio=0.492, z=0.60, parent=None):
    m, n, l, b = _principled(name + "_mat")
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.5 / radio, 0.5 / radio, 1)
    mp.inputs["Location"].default_value = (0.5, 0.5, 0)
    l.new(tc.outputs["Object"], mp.inputs["Vector"])
    tx = n.new("ShaderNodeTexImage")
    tx.image = textura_cafe()
    tx.extension = "CLIP"
    l.new(mp.outputs["Vector"], tx.inputs["Vector"])
    l.new(tx.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.52
    b.inputs["Subsurface Weight"].default_value = 0.3
    b.inputs["Subsurface Scale"].default_value = 0.02
    no = n.new("ShaderNodeTexNoise")
    no.inputs["Scale"].default_value = 260
    no.inputs["Detail"].default_value = 5
    l.new(tc.outputs["Object"], no.inputs["Vector"])
    bu = n.new("ShaderNodeBump")
    bu.inputs["Strength"].default_value = 0.25
    bu.inputs["Distance"].default_value = 0.004
    l.new(no.outputs["Fac"], bu.inputs["Height"])
    l.new(bu.outputs["Normal"], b.inputs["Normal"])
    perfil = [(0, z - 0.004), (radio * 0.7, z - 0.002), (radio * 0.93, z + 0.004), (radio, z + 0.016)]
    return lathe(name, perfil, m, segments=160, parent=parent, per=12)


def cuchara(name="cuchara", parent=None, pos=(-0.12, -0.63, 0.135), rot=0.20):
    nu, nv = 150, 30
    u = np.linspace(0, 1, nu, dtype=np.float32)
    v = np.linspace(-1, 1, nv, dtype=np.float32)
    U, V = np.meshgrid(u, v, indexing="ij")
    w = np.where(U < 0.3, 0.118 * np.sqrt(np.clip(1 - ((U - 0.15) / 0.15) ** 2, 0, 1)) ** 0.8, 0.012 + 0.024 * smooth(0.32, 1.0, U))
    w = np.maximum(w, 0.001)
    X = U * 0.98
    Y = V * w
    conc = np.where(U < 0.3, 0.032 * (1 - V ** 2) * np.sqrt(np.clip(1 - ((U - 0.15) / 0.15) ** 2, 0, 1)), 0.0)
    Z = -conc + 0.05 * smooth(0.26, 0.6, U) + 0.07 * smooth(0.55, 1.0, U)
    c, s = np.cos(rot), np.sin(rot)
    X2, Y2 = X * c - Y * s + pos[0], X * s + Y * c + pos[1]
    mat = plain_mat(name + "_mat", "#D9DADA", rough=0.14, metal=1.0)
    return hoja(name, X2, Y2, Z + pos[2], 0.008, mat, parent)


# ---------- Hamburguesa ----------
def _semillas(name, dome_fn, n, parent, seed=2):
    """Semillas de sésamo repartidas sobre la tapa del pan."""
    rs = np.random.RandomState(seed)
    th = np.linspace(0, 2 * np.pi, 10, endpoint=False)
    ph = np.linspace(0, np.pi, 7)
    unit = []
    for f in ph:
        for t in th:
            unit.append((np.sin(f) * np.cos(t) * 0.031, np.sin(f) * np.sin(t) * 0.018, np.cos(f) * 0.009))
    unit = np.array(unit, dtype=np.float32)
    idx = []
    for i in range(len(ph) - 1):
        for j in range(len(th)):
            idx.append((i * 10 + j, i * 10 + (j + 1) % 10, (i + 1) * 10 + (j + 1) % 10, (i + 1) * 10 + j))
    idx = np.array(idx, dtype=np.int32)
    verts, faces = [], []
    for k in range(n):
        a = rs.uniform(0, 2 * np.pi)
        r = np.sqrt(rs.uniform(0, 1)) * 0.74
        x, y = r * np.cos(a), r * np.sin(a)
        z, nor = dome_fn(x, y)
        rot = rs.uniform(0, 2 * np.pi)
        cr, sr = np.cos(rot), np.sin(rot)
        v = unit.copy()
        v[:, 0], v[:, 1] = unit[:, 0] * cr - unit[:, 1] * sr, unit[:, 0] * sr + unit[:, 1] * cr
        tang = np.cross(nor, [1.0, 0.0, 0.0])
        tang /= np.linalg.norm(tang)
        bit = np.cross(nor, tang)
        w = np.array([x, y, z]) + v[:, 0, None] * tang + v[:, 1, None] * bit + v[:, 2, None] * nor
        verts.append(w)
        faces.append(idx + k * len(unit))
    mat = plain_mat(name + "_mat", "#F3E1B4", rough=0.42, sss=0.3, sss_scale=0.02)
    return mesh_obj(name, np.vstack(verts), np.vstack(faces), mat, parent)


def pan_burger(tipo, R=0.86, parent=None, voxel=0.0055):
    alto = 0.5 if tipo == "tapa" else 0.2
    name = "pan_" + tipo

    def base(x, y, z):
        rad = np.sqrt(x ** 2 + y ** 2)
        if tipo == "tapa":
            d = sd_ellipsoid(x, y, z, R, R, alto)
            return smax(d, -z, 0.035)
        d = extrude(rad - R * 0.985, z - alto / 2, alto / 2, 0.08)
        return d

    def detalle(x, y, z, d):
        p = np.stack([x, y, z], -1)
        cara = smooth(0.045, 0.0, z) if tipo == "tapa" else smooth(alto - 0.045, alto, z)
        f1, _ = worley(p * 20)
        hol = (0.27 - f1) * 0.05
        d2 = d + 0.006 * fbm(p * 5, 3) + 0.0012 * fbm(p * 50, 2)
        return np.where(cara > 0.5, np.maximum(d2, hol), d2)

    def color(x, y, z):
        p = np.stack([x, y, z], -1)
        if tipo == "tapa":
            cara = smooth(0.03, 0.006, z)
            alt = smooth(0.03, 0.36, z + 0.02 * fbm(p * 5, 2))
        else:
            cara = smooth(alto - 0.03, alto - 0.006, z)
            alt = smooth(0.2, 0.0, z) * 0.7
        tost = 0.5 + 0.5 * fbm(p * 5 + 3, 4)
        c = mix(lin("#EDC67E"), lin("#C07C2C"), alt)
        c = mix(c, lin("#8F4F18"), alt * smooth(0.45, 0.72, tost) * 0.75)
        miga = mix(lin("#F6EACB"), lin("#E8CF9E"), 0.5 + 0.5 * fbm(p * 22, 2))
        return mix(c, miga, cara)

    mat = food_mat(name + "_mat", rough=0.38, sss=0.3, sss_scale=0.06, sss_radius=(1, 0.65, 0.35), coat=0.35 if tipo == "tapa" else 0.1, coat_rough=0.3, bump_scale=240, bump_strength=0.08)
    bmin = (-R - 0.04, -R - 0.04, -0.05)
    bmax = (R + 0.04, R + 0.04, alto + 0.05)
    ob = sdf_obj(name, base, bmin, bmax, voxel, mat, color, detalle, parent=parent)
    if tipo == "tapa":
        def dome(x, y):
            z = alto * np.sqrt(np.clip(1 - (x ** 2 + y ** 2) / R ** 2, 0.001, 1))
            nor = np.array([x / R ** 2, y / R ** 2, z / alto ** 2])
            return z + 0.002, nor / np.linalg.norm(nor)
        s = _semillas("sesamo", dome, 150, parent)
        return ob, s
    return ob, None


def carne_burger(R=0.87, alto=0.17, parent=None, voxel=0.0055, name="carne"):
    def base(x, y, z):
        rad = np.sqrt(x ** 2 + y ** 2)
        return extrude(rad - R, z, alto / 2, 0.06)

    def detalle(x, y, z, d):
        p = np.stack([x, y, z], -1)
        return d + 0.03 * fbm(p * 7, 3) + 0.013 * ridged(p * 24, 3) + 0.0035 * fbm(p * 70, 2)

    def color(x, y, z):
        p = np.stack([x, y, z], -1)
        t = 0.5 + 0.5 * fbm(p * 18, 4)
        c = mix(lin("#7A4522"), lin("#40200E"), smooth(0.34, 0.6, t))
        c = mix(c, lin("#190C05"), smooth(0.58, 0.74, t))
        return mix(c, lin("#A66A36"), smooth(0.3, 0.2, t) * 0.7)

    mat = food_mat(name + "_mat", rough=0.34, sss=0.15, sss_scale=0.03, coat=0.55, coat_rough=0.25, bump_scale=300, bump_strength=0.18)
    return sdf_obj(name, base, (-R - 0.07, -R - 0.07, -alto / 2 - 0.07), (R + 0.07, R + 0.07, alto / 2 + 0.07), voxel, mat, color, detalle, parent=parent)


def lechuga(name="lechuga", R=0.98, parent=None, seed=1.0, nr=120, nt=420, amp=0.075, mat=None):
    r = np.linspace(0.02, 1, nr, dtype=np.float32)
    t = np.linspace(0, 2 * np.pi, nt, dtype=np.float32)
    Rr, T = np.meshgrid(r, t, indexing="ij")
    c = np.stack([np.cos(T), np.sin(T), np.zeros_like(T) + seed], -1)
    borde = 1 + 0.09 * fbm(c * 2.4, 3) + 0.03 * fbm(c * 11, 2)
    ruf = smooth(0.55, 1.0, Rr)
    Z = amp * ruf * (np.sin(T * 13 + 3 * fbm(c * 2, 2)) + 0.6 * np.sin(T * 31 + seed) * ruf) + 0.022 * fbm(np.stack([Rr * 4 * np.cos(T), Rr * 4 * np.sin(T), np.zeros_like(T) + seed], -1), 3)
    Z = Z - 0.08 * ruf ** 2
    X = R * Rr * borde * np.cos(T)
    Y = R * Rr * borde * np.sin(T)
    ob = hoja(name, X, Y, Z, 0.006, mat or lechuga_mat(), parent)
    rr, tt = dup2(Rr), dup2(T)
    q = np.stack([rr * 6 * np.cos(tt), rr * 6 * np.sin(tt), np.zeros_like(tt) + seed], -1)
    vena = smooth(0.82, 0.97, ridged(np.stack([tt * 7, rr * 0.7, np.zeros_like(tt) + seed], -1), 2))
    col = mix(lin("#C7DC7E"), lin("#6FA02F"), smooth(0.25, 0.95, rr + 0.14 * fbm(q, 3)))
    col = mix(col, lin("#3F7E22"), smooth(0.86, 1.0, rr) * 0.75)
    col = mix(col, lin("#E2EDAC"), vena * 0.65)
    set_colors(ob, col)
    return ob


def lechuga_mat():
    return food_mat("lechuga_mat", rough=0.32, sss=0.65, sss_scale=0.05, sss_radius=(0.5, 1.0, 0.2), coat=0.25, coat_rough=0.15, bump_scale=120, bump_strength=0.2)


def rodaja_tomate(name="tomate", R=0.47, grosor=0.05, parent=None, voxel=0.0042, centro=(0, 0, 0), mat=None):
    c = np.array(centro, dtype=np.float32)

    def base(x, y, z):
        rad = np.sqrt((x - c[0]) ** 2 + (y - c[1]) ** 2)
        return extrude(rad - R, z - c[2], grosor, 0.03)

    def _gajo(x, y, z):
        p = np.stack([x, y, z], -1)
        xr, yr = x - c[0], y - c[1]
        rad = np.sqrt(xr ** 2 + yr ** 2) / R
        th = np.arctan2(yr, xr) + 0.5 * fbm(p / R * 2 + 3, 2)
        sec = np.abs(((th * 5 / (2 * np.pi)) % 1) - 0.5) * 2
        # Paredes irregulares: el gajo no es un dibujo geométrico.
        return smooth(0.80, 0.66, rad + 0.05 * fbm(p / R * 5, 2)) * smooth(0.12, 0.24, rad) * smooth(0.86, 0.66, sec + 0.08 * fbm(p / R * 6, 2))

    def detalle(x, y, z, d):
        p = np.stack([x, y, z], -1)
        return d + _gajo(x, y, z) * 0.011 + 0.002 * fbm(p / R * 14, 2)

    def color(x, y, z):
        p = np.stack([x, y, z], -1)
        g = _gajo(x, y, z)
        pared = mix(lin("#D8402A"), lin("#BF2A1B"), 0.5 + 0.5 * fbm(p / R * 5, 3))
        pared = mix(pared, lin("#E97C5E"), smooth(0.4, 0.8, 0.5 + 0.5 * fbm(p / R * 16, 2)) * 0.35)
        pulpa = mix(lin("#CF4A22"), lin("#E0682C"), 0.5 + 0.5 * fbm(p / R * 11, 2))
        col = mix(pared, pulpa, g)
        seeds = smooth(0.16, 0.08, worley(p / R * np.array([8, 8, 3]))[0]) * g
        return mix(col, lin("#EFD58E"), seeds * 0.9)

    mat = mat or food_mat("tomate_mat", rough=0.14, sss=0.7, sss_scale=0.05, sss_radius=(1, 0.3, 0.15), coat=0.7, coat_rough=0.08, bump_strength=0.03)
    return sdf_obj(name, base, c - np.array([R + 0.04, R + 0.04, grosor + 0.04]), c + np.array([R + 0.04, R + 0.04, grosor + 0.04]), voxel, mat, color, detalle, parent=parent)


def queso_lamina(name="queso", L=0.74, R=0.72, parent=None, nu=220, grosor=0.022):
    u = np.linspace(-1, 1, nu, dtype=np.float32)
    U, V = np.meshgrid(u, u, indexing="ij")
    X = U * L
    Y = V * L
    rad = np.sqrt(X ** 2 + Y ** 2)
    salida = np.maximum(rad - R, 0)
    Z = -salida * 0.85 - 0.015 * np.sin(salida * 10) - salida ** 2 * 0.6
    enco = 1 - 0.16 * smooth(0, 0.33, salida)
    ob = hoja(name, X * enco, Y * enco, Z, grosor, food_mat(name + "_mat", rough=0.3, sss=0.3, sss_scale=0.008, sss_radius=(1, 0.75, 0.3), coat=0.25, coat_rough=0.2, bump_strength=0.02), parent)
    p = np.stack([dup2(X), dup2(Y), np.zeros(dup2(X).shape, dtype=np.float32)], -1)
    set_colors(ob, mix(lin("#FFC02A"), lin("#F9A71C"), 0.5 + 0.5 * fbm(p * 4, 3)))
    return ob


def cebolla(name="cebolla", parent=None):
    m = food_mat(name + "_mat", rough=0.2, sss=0.7, sss_scale=0.04, sss_radius=(1, 0.5, 1), coat=0.4, coat_rough=0.1, bump_strength=0.02)
    obs = []
    for i, (R, cx, cy) in enumerate([(0.56, 0.15, 0.05), (0.44, -0.25, 0.12), (0.36, 0.05, -0.28), (0.26, 0.15, 0.05)]):
        th = np.linspace(0, 2 * np.pi, 96)
        path = [(cx + R * np.cos(t), cy + R * np.sin(t), 0.012 * np.sin(t * 3 + i)) for t in th]
        ob = tube(f"{name}_{i}", path, 0.022, m, segments=14, parent=parent, per=2)
        v = np.zeros(len(ob.data.vertices) * 3, dtype=np.float32)
        ob.data.vertices.foreach_get("co", v)
        v = v.reshape(-1, 3)
        k = 0.5 + 0.5 * np.sin(v[:, 2] * 60 + i)
        set_colors(ob, mix(lin("#EFE3F0"), lin("#9A3A7E"), k * 0.8))
        obs.append(ob)
    return obs


# ---------- Plato combinado ----------
def lomo(name="lomo", rx=0.52, ry=0.34, alto=0.07, parent=None, voxel=0.0048, seed=0.0):
    def base(x, y, z):
        a = np.arctan2(y, x)
        c = np.stack([np.cos(a) * 1.3, np.sin(a) * 1.3, np.zeros_like(a) + seed], -1)
        return extrude(sd_ellipse_xy(x, y, rx * (1 + 0.1 * perlin(c)), ry * (1 + 0.1 * perlin(c + 3))), z, alto / 2, 0.028)

    def detalle(x, y, z, d):
        p = np.stack([x + seed, y, z], -1)
        marca = smooth(0.09, 0.03, np.abs(((x * 0.82 + y * 0.57) * 5.2 + 0.1 * perlin(p * 9)) % 1 - 0.5) / 2.6)
        return d + 0.014 * fbm(p * 7, 3) + 0.0024 * fbm(p * 50, 2) + marca * 0.005

    def color(x, y, z):
        p = np.stack([x + seed, y, z], -1)
        t = 0.5 + 0.5 * fbm(p * 8, 4)
        c = mix(lin("#D2A070"), lin("#A9754A"), smooth(0.34, 0.65, t))
        marca = smooth(0.16, 0.06, np.abs(((x * 0.82 + y * 0.57) * 5.2 + 0.1 * perlin(p * 9)) % 1 - 0.5))
        c = mix(c, lin("#4A2811"), marca * smooth(0.0, 0.03, z) * 0.8)
        borde = sd_ellipse_xy(x, y, rx, ry)
        return mix(c, lin("#E3BE86"), smooth(-0.045, -0.012, borde + 0.012 * fbm(p * 12, 2)) * 0.55)

    mat = food_mat(name + "_mat", rough=0.32, sss=0.25, sss_scale=0.04, coat=0.55, coat_rough=0.2, bump_scale=230, bump_strength=0.15)
    return sdf_obj(name, base, (-rx * 1.2, -ry * 1.3, -alto), (rx * 1.2, ry * 1.3, alto), voxel, mat, color, detalle, parent=parent)


def huevo_frito(name="huevo", R=0.50, parent=None, voxel=0.0042):
    def forma(x, y):
        a = np.arctan2(y, x)
        c = np.stack([np.cos(a), np.sin(a), np.zeros_like(a)], -1)
        rr = R * (1 + 0.16 * fbm(c * 1.8, 3) + 0.05 * fbm(c * 7, 2))
        return np.sqrt(x ** 2 + y ** 2) - rr

    def base(x, y, z):
        sub = 0.022 + 0.022 * smooth(0.0, -0.22, forma(x, y))
        return extrude(forma(x, y), z - 0.02, sub, 0.018)

    def detalle(x, y, z, d):
        p = np.stack([x, y, z], -1)
        cerca = smooth(-0.13, -0.02, forma(x, y))
        burb = (0.26 - worley(p * 22)[0]) * 0.03
        return np.maximum(d + 0.006 * fbm(p * 12, 3) + cerca * 0.008 * fbm(p * 40, 2), burb * cerca - 0.6 * (1 - cerca))

    def color(x, y, z):
        p = np.stack([x, y, z], -1)
        cerca = smooth(-0.14, -0.012, forma(x, y) + 0.05 * fbm(p * 16, 3))
        c = mix(lin("#FBF7EC"), lin("#F4E7CC"), 0.5 + 0.5 * fbm(p * 7, 2))
        c = mix(c, lin("#D69A45"), cerca * 0.85)
        return mix(c, lin("#8C5118"), smooth(0.62, 1.0, cerca) * 0.9)

    mat = food_mat(name + "_mat", rough=0.22, sss=0.75, sss_scale=0.03, sss_radius=(1, 0.9, 0.7), coat=0.6, coat_rough=0.15, bump_scale=180, bump_strength=0.08)
    clara = sdf_obj(name, base, (-R * 1.3, -R * 1.3, -0.05), (R * 1.3, R * 1.3, 0.1), voxel, mat, color, detalle, parent=parent)

    def yema(x, y, z):
        return sd_ellipsoid(x - 0.02, y + 0.02, z - 0.056, 0.195, 0.195, 0.115)

    def col_y(x, y, z):
        p = np.stack([x, y, z], -1)
        return mix(lin("#F9A906"), lin("#EF8A00"), 0.5 + 0.5 * fbm(p * 7, 2))

    my = food_mat(name + "_yema", rough=0.12, sss=0.9, sss_scale=0.05, sss_radius=(1, 0.5, 0.1), coat=1.0, coat_rough=0.05, bump_strength=0.0)
    ye = sdf_obj(name + "_yema", yema, (-0.24, -0.26, 0.0), (0.26, 0.24, 0.2), 0.0032, my, col_y, parent=parent)
    return clara, ye


def patata_frita_malla(seed, name="frita", largo=0.34, parent=None, mat=None, voxel=0.0048):
    rs = np.random.RandomState(seed)
    L = largo * rs.uniform(0.75, 1.2)
    w = rs.uniform(0.032, 0.042)
    b = rs.uniform(-0.25, 0.25)

    def base(x, y, z):
        y2 = y - b * x ** 2
        return sd_box(x, y2, z, L, w, w * 0.92, 0.014)

    def detalle(x, y, z, d):
        p = np.stack([x + seed, y, z], -1)
        return d + 0.006 * fbm(p * 9, 2) + 0.0016 * fbm(p * 50, 2)

    def color(x, y, z):
        p = np.stack([x + seed, y, z], -1)
        c = mix(lin("#F3CE6A"), lin("#E2A83F"), 0.5 + 0.5 * fbm(p * 8, 3))
        tips = smooth(L * 0.72, L * 1.02, np.abs(x) + 0.03 * fbm(p * 12, 2))
        c = mix(c, lin("#A9682A"), tips * 0.75)
        c = mix(c, lin("#C9862F"), smooth(0.62, 0.86, 0.5 + 0.5 * fbm(p * 24, 2)) * 0.5)
        return c

    return sdf_obj(f"{name}_{seed}", base, (-L - 0.03, -w - 0.08, -w - 0.03), (L + 0.03, w + 0.08, w + 0.03), voxel, mat, color, detalle, parent=parent)


def frita_mat():
    return food_mat("frita_mat", rough=0.38, sss=0.45, sss_scale=0.04, sss_radius=(1, 0.65, 0.25), coat=0.35, coat_rough=0.3, bump_scale=260, bump_strength=0.15)


# ---------- Bocadillo: barra de pan partida ----------
def barra(zc=0.27, L=1.36, rr=0.36, parent=None, voxel=0.0058):
    """Devuelve (parte de abajo, parte de arriba). La de arriba gira sobre su bisagra trasera."""
    cz = 0.26

    def exterior(x, y, z):
        ax = np.maximum(np.abs(x) - (L - rr), 0)
        taper = 1 - 0.28 * (np.abs(x) / L) ** 4
        d = np.sqrt(ax ** 2 + y ** 2 + ((z - cz) / 0.76) ** 2) - rr * taper
        # Cortes diagonales típicos de la barra.
        tram = np.abs(((x * 0.84 + y * 0.8) * 1.72 + 0.5) % 1 - 0.5)
        corte = smooth(0.07, 0.0, tram) * smooth(0.08, 0.40, z - cz + 0.12) * smooth(1.0, 0.72, np.abs(x) / L)
        return d + corte * 0.022

    def color_general(x, y, z):
        p = np.stack([x, y, z], -1)
        d = exterior(x, y, z)
        tost = 0.5 + 0.5 * fbm(p * np.array([5, 9, 9]) + 2, 5)
        alt = smooth(0.1, 0.5, z)
        tram = np.abs(((x * 0.84 + y * 0.8) * 1.72 + 0.5) % 1 - 0.5)
        ranura = smooth(0.09, 0.02, tram) * smooth(0.08, 0.40, z - cz + 0.12)
        c = mix(lin("#DDA350"), lin("#B06C27"), alt * 0.9)
        c = mix(c, lin("#83481A"), alt * smooth(0.42, 0.72, tost) * 0.8)
        c = mix(c, lin("#E8C98C"), ranura * smooth(1.0, 0.72, np.abs(x) / L) * 0.7)  # interior de los cortes: más claro
        c = mix(c, lin("#F7EFD9"), smooth(0.68, 0.84, 0.5 + 0.5 * fbm(p * 30, 2)) * 0.22)
        return miga_vs(p, d, c)

    def miga_vs(p, d, c):
        crumb = mix(lin("#F6EBD0"), lin("#E5CF9F"), smooth(0.33, 0.12, worley(p * 15)[0]))
        return mix(crumb, c, smooth(-0.035, -0.02, d))

    def mk(sign, name):
        def base(x, y, z):
            return smax(exterior(x, y, z), sign * (z - zc), 0.012)

        def detalle(x, y, z, dd):
            p = np.stack([x, y, z], -1)
            f1, _ = worley(p * 15)
            f1b, _ = worley(p * 34 + 9)
            ag = np.maximum((0.27 - f1) * 0.10, (0.25 - f1b) * 0.04)
            inter = smooth(-0.03, -0.055, exterior(x, y, z))
            d2 = dd + 0.0055 * fbm(p * np.array([7, 12, 12]), 3) + 0.0012 * fbm(p * 60, 2)
            return np.maximum(d2, np.where(inter > 0, ag * inter, -1))

        mat = food_mat(name + "_mat", rough=0.66, sss=0.25, sss_scale=0.05, sss_radius=(1, 0.7, 0.4), bump_scale=260, bump_strength=0.18)
        bmin = (-L - 0.05, -rr - 0.05, (zc - 0.03) if sign < 0 else -0.05)
        bmax = (L + 0.05, rr + 0.05, (zc + 0.03) if sign > 0 else 0.6)
        return sdf_obj(name, base, bmin, bmax, voxel, mat, color_general, detalle, parent=parent)

    return mk(1, "barra_abajo"), mk(-1, "barra_arriba")


# ---------- Ración: tabla, queso y embutido ----------
def tabla(name="tabla", a=1.55, b=0.98, h=0.09, parent=None):
    def base(x, y, z):
        d = sd_box(x, y, z - h / 2, a, b, h / 2, 0.04)
        d2 = sd_box(x, y, 0 * z, a, b, 1.0, 0.16)
        return smax(d, d2, 0.02)

    def detalle(x, y, z, d):
        p = np.stack([x, y, z], -1)
        return d + 0.0014 * fbm(p * np.array([2, 28, 28]), 2)

    m = wood_mat(name + "_mat", "#D2A36B", "#955F2E")
    return sdf_obj(name, base, (-a - 0.03, -b - 0.03, -0.03), (a + 0.03, b + 0.03, h + 0.03), 0.0075, m, None, detalle, parent=parent)


def cuna_queso(name="cuna", R=0.62, alto=0.05, ang=42, parent=None, voxel=0.0036, mat=None):
    """Loncha triangular de queso curado, tumbada: la corteza queda solo en el arco."""
    a = np.radians(ang / 2)
    n1 = np.array([-np.sin(a), np.cos(a)])
    n2 = np.array([-np.sin(a), -np.cos(a)])

    def partes(x, y, z):
        rad = np.sqrt(x ** 2 + y ** 2)
        c = extrude(rad - R, z - alto / 2, alto / 2, 0.012)
        cu = np.maximum(x * n1[0] + y * n1[1], x * n2[0] + y * n2[1])
        return c, cu, rad

    def base(x, y, z):
        c, cu, _ = partes(x, y, z)
        return smax(c, cu, 0.006)

    def detalle(x, y, z, d):
        p = np.stack([x, y, z], -1)
        f1, _ = worley(p * 24)
        return np.maximum(d + 0.0012 * fbm(p * 60, 2), (0.14 - f1) * 0.03)

    def color(x, y, z):
        p = np.stack([x, y, z], -1)
        c, cu, rad = partes(x, y, z)
        pasta = mix(lin("#F6E5AE"), lin("#EBD38A"), 0.5 + 0.5 * fbm(p * 7, 3))
        dib = 0.5 + 0.5 * np.sin(np.arctan2(y, x) * 80) * np.sin(z * 130)
        cor = mix(lin("#7A5A2C"), lin("#4C3417"), dib)
        return mix(pasta, cor, smooth(R - 0.03, R - 0.018, rad))

    return sdf_obj(name, base, (-0.03, -R, -0.03), (R + 0.03, R, alto + 0.03), voxel, mat or food_mat("queso_c_mat", rough=0.42, sss=0.45, sss_scale=0.03, sss_radius=(1, 0.8, 0.45), bump_scale=200, bump_strength=0.08), color, detalle, parent=parent)


def rodaja_embutido(name, tipo="chorizo", R=0.27, grosor=0.018, parent=None, voxel=0.0034, mat=None):
    def base(x, y, z):
        return extrude(np.sqrt(x ** 2 + y ** 2) - R, z, grosor, 0.006)

    def detalle(x, y, z, d):
        p = np.stack([x, y, z], -1)
        return d + 0.0022 * fbm(p * 24, 2)

    def color(x, y, z):
        p = np.stack([x, y, z], -1) + (3.0 if tipo == "chorizo" else 19.0)
        f1, f2 = worley(p * np.array([23, 23, 8]))
        grasa = smooth(0.26, 0.16, f1)
        if tipo == "chorizo":
            c = mix(lin("#9E2614"), lin("#7A180B"), 0.5 + 0.5 * fbm(p * 14, 3))
            c = mix(c, lin("#E7A36C"), grasa)
            piel = lin("#4E1A0D")
        else:
            c = mix(lin("#7E2A33"), lin("#5F1D24"), 0.5 + 0.5 * fbm(p * 14, 3))
            c = mix(c, lin("#F0DCC8"), grasa)
            piel = lin("#CFC6B4")
        rad = np.sqrt(x ** 2 + y ** 2)
        return mix(c, piel, smooth(R - 0.014, R - 0.006, rad))

    return sdf_obj(name, base, (-R - 0.015, -R - 0.015, -grosor - 0.012), (R + 0.015, R + 0.015, grosor + 0.012), voxel, mat, color, detalle, parent=parent)


def embutido_mat():
    return food_mat("embutido_mat", rough=0.30, sss=0.6, sss_scale=0.03, sss_radius=(1, 0.35, 0.2), coat=0.3, coat_rough=0.2, bump_scale=300, bump_strength=0.08)


# ---------- Granos de café ----------
def grano(name="grano", seed=0, parent=None, voxel=0.0024, mat=None):
    rs = np.random.RandomState(seed)
    k = rs.uniform(0.92, 1.08)

    def surco(x, y):
        return y - 0.018 * np.sin(x * 15 + seed) - 0.006 * np.sin(x * 37 + seed)

    def base(x, y, z):
        # Una cara abombada y la otra casi plana, como un grano partido en dos.
        zz = np.where(z > 0, z / 0.62, z / 1.0)
        d = sd_ellipsoid(x, y, zz, 0.20 * k, 0.14, 0.13)
        return d + smooth(0.012, 0.0, np.abs(surco(x, y))) * smooth(0.0, 0.05, z) * 0.042

    def detalle(x, y, z, d):
        p = np.stack([x, y, z], -1) + seed
        return d + 0.006 * fbm(p * 7, 2) + 0.0009 * fbm(p * 60, 2)

    def color(x, y, z):
        p = np.stack([x, y, z], -1) + seed
        c = mix(lin("#42210E"), lin("#2A1307"), 0.5 + 0.5 * fbm(p * 13, 3))
        c = mix(c, lin("#5E3519"), smooth(0.1, 0.0, np.abs(surco(x, y)) - 0.03) * 0.3)
        return mix(c, lin("#0E0603"), smooth(0.012, 0.0, np.abs(surco(x, y))) * smooth(0.0, 0.05, z))

    m = mat or food_mat("grano_mat", rough=0.36, sss=0.08, sss_scale=0.02, coat=0.35, coat_rough=0.28, bump_scale=240, bump_strength=0.1)
    return sdf_obj(f"{name}_{seed}", base, (-0.26, -0.19, -0.17), (0.26, 0.19, 0.12), voxel, m, color, detalle, parent=parent)
