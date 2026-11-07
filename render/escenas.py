# =====================================================================
# escenas.py: rueda las secuencias de fotogramas que la web reproduce con el scroll.
# Cada secuencia es un PNG por fotograma, con fondo transparente.
#
#   SOLO=cafe,burger   solo esas secuencias
#   PREVIEW=1          solo 3 fotogramas a baja resolución, para revisar el encuadre
# =====================================================================
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
import piezas as P

OUT = os.environ.get("OUT", "/tmp/renders")
SOLO = set(filter(None, os.environ.get("SOLO", "").split(",")))
PREVIEW = os.environ.get("PREVIEW") == "1"
RES = 500 if PREVIEW else int(os.environ.get("RES", "1000"))
SAMPLES = 32 if PREVIEW else int(os.environ.get("SAMPLES", "64"))


def lerp(a, b, t):
    return a + (b - a) * t


def rodar(nombre, n, montar, actualizar, world=0.55, escala=1.0, objetivo=(0, 0, 0.3), suelo=True):
    """Monta la escena y renderiza n fotogramas. actualizar(t, cam) coloca todo para el instante t (0 a 1)."""
    if SOLO and nombre not in SOLO:
        return
    t0 = time.time()
    new_scene(res=RES, samples=SAMPLES)
    cam = montar()
    if suelo:
        shadow_catcher()
    studio(target=objetivo, world=world, scale=escala)
    indices = [0, n // 2, n - 1] if PREVIEW else list(range(n))
    for i in indices:
        t = i / (n - 1) if n > 1 else 0.0
        actualizar(t, cam)
        bpy.context.view_layer.update()
        render_to(os.path.join(OUT, nombre, f"{i:04d}.png"))
    print(f"OK {nombre}: {len(indices)} fotogramas en {time.time() - t0:.0f} s")


def cam_orbita(cam, dist, elev, azim, objetivo):
    aim(cam, orbit(dist, elev, azim, objetivo), objetivo)
    cam.data.dof.focus_distance = dist


# ---------- Giro simple: una pieza que rota mientras pasa ----------
def giro(nombre, n, construir, dist, elev, azim=-70, objetivo=(0, 0, 0.3), desde=-50, hasta=50, dof=2.2, extra=None, suelo=True):
    piv = {}

    def montar():
        piv["p"] = empty()
        construir(piv["p"])
        if extra:
            extra(piv["p"])
        return camera(orbit(dist, elev, azim, objetivo), objetivo, lens=70, dof=dof)

    def actualizar(t, cam):
        piv["p"].rotation_euler.z = math.radians(lerp(desde, hasta, t))

    rodar(nombre, n, montar, actualizar, objetivo=objetivo, suelo=suelo)


def b_tortilla(p):
    P.rebanada(parent=p)
    P.tortilla_porcion(parent=p)
    P.palillo(base=(0.02, 0, 0.3), alto=0.72, parent=p)
    P.aceituna(centro=(0.06, 0.02, 0.86), parent=p)


def b_jamon(p):
    P.rebanada(parent=p)
    m = P.jamon_mat()
    P.loncha_jamon("j1", seed=1.1, pos=(0.0, -0.06, 0.13), rot=0.25, largo=0.92, ancho=0.40, parent=p, mat=m)
    P.loncha_jamon("j2", seed=2.7, pos=(-0.03, 0.07, 0.16), rot=-0.3, largo=0.86, ancho=0.38, parent=p, mat=m, fase=1.2)
    P.loncha_jamon("j3", seed=4.2, pos=(0.02, 0.0, 0.21), rot=0.1, largo=0.74, ancho=0.32, parent=p, mat=m, fase=2.5)


def b_empanada(p):
    P.empanada(parent=p)


def b_moruno(p):
    P.pincho_moruno(parent=p)
    p.location = (0, 0, 0.5)
    p.rotation_euler = (0, math.radians(-30), 0)


def b_croissant(p):
    P.plato_rect("plato_c", a=1.14, b=0.72, parent=p)
    c = P.croissant(z0=0.04, parent=p)
    c.rotation_euler.z = math.radians(8)


# ---------- Café: la cámara sube hasta mirar desde arriba ----------
def cafe():
    def montar():
        p = empty()
        P.platillo(parent=p)
        P.taza(parent=p)
        P.superficie_cafe(z=0.60, parent=p)
        P.cuchara(parent=p)
        return camera(orbit(4.7, 14, -90, (0, 0, 0.3)), (0, 0, 0.3), lens=70, dof=3.2)

    def actualizar(t, cam):
        e = ease_io(t)
        cam_orbita(cam, 4.7, lerp(14, 89.6, e), -90 + 26 * (1 - e) * math.sin(e * math.pi), (0, 0, lerp(0.34, 0.3, e)))

    rodar("cafe", 60, montar, actualizar)


def cafe_espuma():
    """Primer plano de la espuma: la web entra por aquí en la transición (se ve nítido al ampliar)."""
    if SOLO and "espuma" not in SOLO:
        return
    new_scene(res=1400 if not PREVIEW else 500, samples=SAMPLES)
    p = empty()
    P.platillo(parent=p)
    P.taza(parent=p)
    P.superficie_cafe(z=0.60, parent=p)
    studio(target=(0, 0, 0.3), world=0.55)  # la misma luz que la taza, para que el paso de una a otra no se note
    camera((0, 0, 3.0), (0, 0.0001, 0.6), lens=120)
    render_to(os.path.join(OUT, "espuma", "0000.png"))


# ---------- Comida que cae al plato ----------
class Caidas:
    def __init__(self):
        self.lista = []

    def add(self, ob, loc, rot, t0, t1, alto=3.4, spin=1.6, rs=None):
        rs = rs or random
        self.lista.append((ob, tuple(loc), tuple(rot), t0, t1, alto, (rs.uniform(-spin, spin), rs.uniform(-spin, spin), rs.uniform(-spin, spin))))

    def poner(self, t):
        for ob, loc, rot, t0, t1, alto, sp in self.lista:
            u = 0.0 if t <= t0 else (1.0 if t >= t1 else (t - t0) / (t1 - t0))
            b = ease_out_bounce(u)
            # Antes de su turno, la pieza espera muy arriba, fuera de cuadro.
            zz = loc[2] + (alto * (1 - b) if u > 0 else alto * 3)
            ob.location = (loc[0], loc[1], zz)
            k = 1 - min(u * 1.25, 1)
            ob.rotation_euler = (rot[0] + sp[0] * k, rot[1] + sp[1] * k, rot[2] + sp[2] * k)


def plato():
    ca = Caidas()
    piv = {}

    def montar():
        rs = random.Random(3)
        p = piv["p"] = empty()
        P.plato_rect(parent=p)
        l1 = P.lomo(parent=p, seed=1.3)
        l2 = P.lomo("lomo2", parent=p, seed=4.3)
        ca.add(l1, (0.66, -0.12, 0.10), (0, 0, 0.3), 0.04, 0.30)
        ca.add(l2, (0.74, 0.27, 0.15), (0.03, -0.07, -0.25), 0.12, 0.38)
        m = P.frita_mat()
        base = [P.patata_frita_malla(i, parent=p, mat=m) for i in range(6)]
        for k in range(42):
            o = base[k % 6]
            if k >= 6:
                o = o.copy()
                bpy.context.scene.collection.objects.link(o)
                o.parent = p
            a, r = rs.uniform(0, 6.28), rs.uniform(0, 0.48) ** 0.8
            ca.add(o, (-0.72 + r * math.cos(a) * 1.05, 0.22 + r * math.sin(a) * 0.95, 0.08 + (0.48 - r) * 0.34 * rs.uniform(0.3, 1.0) + 0.01 * k * 0.25),
                   (rs.uniform(-0.25, 0.25), rs.uniform(-0.25, 0.25), rs.uniform(0, 6.28)), 0.22 + 0.32 * k / 42, 0.46 + 0.32 * k / 42, rs=rs)
        c, y = P.huevo_frito(parent=p)
        ca.add(c, (-0.10, -0.34, 0.055), (0, 0, 0.4), 0.56, 0.78, spin=0.25)
        ca.add(y, (-0.10, -0.34, 0.055), (0, 0, 0.4), 0.56, 0.78, spin=0.25)
        lc = P.lechuga("lech", R=0.5, parent=p, amp=0.07)
        ca.add(lc, (0.12, 0.50, 0.07), (0.05, 0, 0.4), 0.68, 0.86, spin=0.4)
        t1 = P.rodaja_tomate(R=0.2, grosor=0.03, parent=p, voxel=0.0036)
        t2 = P.rodaja_tomate("tomate2", R=0.2, grosor=0.03, parent=p, voxel=0.0036, mat=t1.data.materials[0])
        ca.add(t1, (-0.02, 0.48, 0.16), (0.25, 0, 0.2), 0.76, 0.94, spin=0.7)
        ca.add(t2, (0.30, 0.45, 0.17), (0.2, -0.1, 1.2), 0.80, 0.98, spin=0.7)
        return camera(orbit(7.2, 42, -90, (0, 0, 0.05)), (0, 0, 0.05), lens=70, dof=3.5)

    def actualizar(t, cam):
        ca.poner(t)
        piv["p"].rotation_euler.z = math.radians(lerp(-13, 7, ease_io(t)))
        cam_orbita(cam, lerp(7.6, 7.0, t), lerp(36, 46, ease_io(t)), -90, (0, 0, 0.05))

    rodar("plato", 72, montar, actualizar, objetivo=(0, 0, 0.1), escala=1.25)


# ---------- Bocadillo: la barra se abre y cae el jamón ----------
def bocadillo():
    ca = Caidas()
    obj = {}
    zc = 0.27
    hy = 0.30

    def montar():
        p = obj["p"] = empty()
        abajo, arriba = P.barra(zc=zc, parent=p)
        h = obj["h"] = empty("bisagra", parent=p)
        h.location = (0, hy, zc)
        arriba.parent = h
        arriba.data.transform(Matrix.Translation((0, -hy, -zc)))
        m = P.jamon_mat()
        rs = random.Random(5)
        for i, (x, y, r) in enumerate([(-0.86, 0.03, 0.10), (-0.42, -0.04, -0.08), (0.02, 0.04, 0.12), (0.46, -0.03, -0.10), (0.88, 0.02, 0.05)]):
            j = P.loncha_jamon(f"j{i}", seed=i * 1.9 + 0.4, largo=0.86, ancho=0.60, amp=0.09, parent=p, mat=m, fase=i * 1.1)
            ca.add(j, (x, y, zc + 0.012 + (i % 2) * 0.02), (0, 0, r), 0.40 + i * 0.07, 0.66 + i * 0.07, alto=2.6, spin=0.7, rs=rs)
        return camera(orbit(6.1, 22, -76, (0, 0, 0.36)), (0, 0, 0.36), lens=70, dof=4)

    def actualizar(t, cam):
        ca.poner(t)
        a = ease_io(max(0.0, min(1.0, (t - 0.10) / 0.34)))
        obj["h"].rotation_euler.x = math.radians(-44) * a
        obj["p"].rotation_euler.z = math.radians(lerp(-11, 5, ease_io(t)))
        cam_orbita(cam, 6.1, lerp(16, 33, ease_io(t)), -76, (0, 0, lerp(0.30, 0.42, a)))

    rodar("bocadillo", 56, montar, actualizar, objetivo=(0, 0, 0.3), escala=1.25)


# ---------- Hamburguesa que se despieza ----------
def hamburguesa():
    capas = []
    piv = {}

    def montar():
        p = piv["p"] = empty()
        a, _ = P.pan_burger("base", parent=p)
        capas.append(([a], 0.0))
        capas.append(([P.lechuga(parent=p)], 0.235))
        t1 = P.rodaja_tomate(parent=p, centro=(0.25, 0.07, 0.0))
        t2 = P.rodaja_tomate("tomate2", parent=p, centro=(-0.33, -0.10, 0.0), mat=t1.data.materials[0])
        capas.append(([t1, t2], 0.325))
        capas.append(([P.carne_burger(parent=p)], 0.465))
        capas.append(([P.queso_lamina(parent=p)], 0.56))
        capas.append((list(P.cebolla(parent=p)), 0.615))
        ta, se = P.pan_burger("tapa", parent=p)
        capas.append(([ta, se], 0.64))
        return camera(orbit(5.2, 12, -72, (0, 0, 0.55)), (0, 0, 0.55), lens=70, dof=4.5)

    def actualizar(t, cam):
        e = ease_io(max(0.0, min(1.0, (t - 0.08) / 0.84)))
        hueco = 0.40 * e
        for i, (obs, z) in enumerate(capas):
            for o in obs:
                o.location.z = z + i * hueco + (0.08 if i == 6 else 0.0) * e
        alto_total = 0.64 + 6 * hueco + 0.5
        piv["p"].rotation_euler.z = math.radians(lerp(-30, 26, ease_io(t)))
        cam_orbita(cam, lerp(4.9, 8.7, e), lerp(10, 15, e), -72, (0, 0, alto_total / 2))

    rodar("burger", 56, montar, actualizar, objetivo=(0, 0, 0.9), escala=1.4)


# ---------- Ración: la tabla se va llenando ----------
def racion():
    ca = Caidas()
    piv = {}

    def montar():
        rs = random.Random(9)
        p = piv["p"] = empty()
        P.tabla(parent=p)
        m = P.jamon_mat()
        pos = [(-0.82, 0.42, 0.25), (-0.62, -0.10, -0.32), (-1.02, -0.34, 0.45), (-0.34, 0.34, -0.12), (-0.42, -0.45, 0.2), (-0.86, 0.05, 0.05)]
        for i, (x, y, r) in enumerate(pos):
            j = P.loncha_jamon(f"j{i}", seed=i * 1.7 + 0.3, largo=1.06, ancho=0.52, amp=0.11, parent=p, mat=m, fase=i * 0.9)
            ca.add(j, (x, y, 0.095 + i * 0.03), (0, 0, r), 0.02 + i * 0.05, 0.26 + i * 0.05, spin=0.6, rs=rs)
        qm = None
        for i, (x, y, r) in enumerate([(0.34, 0.76, -1.0), (0.46, 0.50, -0.72), (0.60, 0.24, -0.44), (0.76, 0.0, -0.16)]):
            q = P.cuna_queso(f"cuna{i}", parent=p, mat=qm)
            qm = q.data.materials[0]
            ca.add(q, (x, y, 0.095 + i * 0.012), (0.0, -0.03, r), 0.34 + i * 0.05, 0.56 + i * 0.05, spin=0.5, rs=rs)
        em = P.embutido_mat()
        for i in range(7):
            c = P.rodaja_embutido(f"ch{i}", "chorizo" if i % 2 == 0 else "salchichon", parent=p, mat=em)
            ca.add(c, (0.02 + i * 0.18, -0.58 + i * 0.012, 0.125 + i * 0.008), (0.12, -0.24, 0), 0.54 + i * 0.05, 0.76 + i * 0.05, spin=0.8, rs=rs)
        return camera(orbit(7.2, 38, -90, (0, 0, 0.05)), (0, 0, 0.05), lens=70, dof=4)

    def actualizar(t, cam):
        ca.poner(t)
        piv["p"].rotation_euler.z = math.radians(lerp(-10, 6, ease_io(t)))
        cam_orbita(cam, 7.0, lerp(30, 42, ease_io(t)), -90, (0, 0, 0.05))

    rodar("racion", 56, montar, actualizar, objetivo=(0, 0, 0.1), escala=1.25)


# ---------- Piezas sueltas para las capas de fondo ----------
def sueltas():
    if SOLO and "sueltas" not in SOLO:
        return
    rs = np.random.RandomState(2)
    res = 200 if PREVIEW else 420

    def foto(nombre, construir, dist=1.5, objetivo=(0, 0, 0), plano=False):
        new_scene(res=res, samples=48)
        p = empty()
        construir(p)
        p.rotation_euler = (0.3, 0.2, 0.4) if plano else tuple(rs.uniform(-1.0, 1.0, 3))
        studio(target=objetivo, world=0.7)
        camera(orbit(dist, 35, -75, objetivo), objetivo, lens=70)
        render_to(os.path.join(OUT, "sueltas", nombre + ".png"))

    for i in range(4):
        foto(f"grano{i}", lambda p, i=i: P.grano(seed=i, parent=p), dist=1.45)
    foto("tomate", lambda p: P.rodaja_tomate(R=0.42, grosor=0.05, parent=p), dist=2.9)
    foto("frita", lambda p: P.patata_frita_malla(2, parent=p, mat=P.frita_mat()), dist=2.4)
    foto("aceituna", lambda p: P.aceituna(centro=(0, 0, 0), r=0.15, parent=p), dist=1.5)
    foto("sesamo", lambda p: P.aceituna(centro=(0, 0, 0), r=0.09, parent=p, color_a="#F3E1B4", color_b="#E7CE96"), dist=0.9)


cafe()
cafe_espuma()
giro("croissant", 24, b_croissant, dist=5.6, elev=32, azim=-84, objetivo=(0, 0, 0.12), desde=-32, hasta=30)
giro("tortilla", 24, b_tortilla, dist=2.85, elev=19, azim=-68, objetivo=(0, 0, 0.42), desde=-48, hasta=42)
giro("jamon", 24, b_jamon, dist=2.55, elev=25, azim=-68, objetivo=(0, 0, 0.17), desde=-48, hasta=42)
giro("empanada", 24, b_empanada, dist=2.75, elev=26, azim=-125, objetivo=(0, 0, 0.13), desde=-46, hasta=38)
giro("moruno", 24, b_moruno, dist=5.3, elev=18, azim=-82, objetivo=(0, 0, 0.5), desde=-24, hasta=22, dof=3, suelo=False)
plato()
bocadillo()
hamburguesa()
racion()
sueltas()
