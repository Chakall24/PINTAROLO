// =====================================================================
// exportar.mjs: comprime los PNG que saca Blender en los WebP que usa la web.
// - Dos tamaños de cada fotograma: 900 px (ordenador) y 600 px (móvil).
// - Difumina los bordes del encuadre, para que ninguna sombra se corte de golpe contra el borde del lienzo.
// Uso: SHARP=/ruta/a/node_modules/sharp node exportar.mjs carpeta_renders carpeta_assets [secuencia...]
// =====================================================================
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const require = createRequire(import.meta.url);
const sharp = require(process.env.SHARP || "sharp");
const [, , entrada, salida, ...soloEstas] = process.argv;

const TAMANOS = [900, 600];
const BORDE = 0.05;   // el 5% exterior del lienzo se funde a transparente

function suave(x) {
  const t = Math.max(0, Math.min(1, x));
  return t * t * (3 - 2 * t);
}

// Calcula de una vez la máscara de bordes: multiplica la distancia a cada lado.
const mascaras = new Map();
function mascara(lado) {
  if (mascaras.has(lado)) return mascaras.get(lado);
  const m = new Float32Array(lado * lado);
  const banda = lado * BORDE;
  for (let y = 0; y < lado; y++) {
    const dy = suave(Math.min(y, lado - 1 - y) / banda);
    for (let x = 0; x < lado; x++) {
      m[y * lado + x] = dy * suave(Math.min(x, lado - 1 - x) / banda);
    }
  }
  mascaras.set(lado, m);
  return m;
}

const radiales = new Map();
function radial(lado) {
  if (radiales.has(lado)) return radiales.get(lado);
  const m = new Float32Array(lado * lado);
  for (let y = 0; y < lado; y++) {
    for (let x = 0; x < lado; x++) {
      const d = Math.hypot(x / lado - 0.5, y / lado - 0.5);
      m[y * lado + x] = suave((0.5 - d) / 0.17);   // pleno hasta el 33% del lado, nada a partir del 50%
    }
  }
  radiales.set(lado, m);
  return m;
}

async function fotograma(origen, destino, lado, calidad = 84) {
  const { data, info } = await sharp(origen).resize(lado, lado).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const m = mascara(lado);
  const r = radial(lado);
  for (let i = 0; i < m.length; i++) {
    const j = i * 4;
    let alfa = data[j + 3] * m[i];
    // Los píxeles de sombra pura son negros y semitransparentes. Solo a esos se les aplica un degradado circular,
    // para que la sombra se apague antes de llegar al borde y nunca se adivine el cuadrado de la imagen.
    const brillo = Math.max(data[j], data[j + 1], data[j + 2]) / 255;
    const sombra = 1 - suave((brillo - 0.015) / 0.14);
    if (sombra > 0) alfa = Math.max(0, alfa * (1 - sombra + sombra * r[i]) - 1.5 * sombra);
    data[j + 3] = alfa;
  }
  fs.mkdirSync(path.dirname(destino), { recursive: true });
  await sharp(data, { raw: { width: info.width, height: info.height, channels: 4 } })
    .webp({ quality: calidad, alphaQuality: 100, effort: 4, smartSubsample: true })
    .toFile(destino);
}

async function enParalelo(trabajos, limite = 8) {
  let i = 0;
  await Promise.all(Array.from({ length: limite }, async () => {
    while (i < trabajos.length) await trabajos[i++]();
  }));
}

const SECUENCIAS = ["cafe", "croissant", "tortilla", "jamon", "empanada", "moruno", "plato", "bocadillo", "burger", "racion"];

for (const s of SECUENCIAS) {
  if (soloEstas.length && !soloEstas.includes(s)) continue;
  const dir = path.join(entrada, s);
  if (!fs.existsSync(dir)) continue;
  const archivos = fs.readdirSync(dir).filter((f) => f.endsWith(".png")).sort();
  const trabajos = [];
  archivos.forEach((f, n) => {
    for (const lado of TAMANOS) {
      // En móvil basta con un fotograma de cada dos (y el último): pesa la mitad y se sigue viendo fluido.
      if (lado === 600 && n % 2 === 1 && n !== archivos.length - 1) continue;
      trabajos.push(() => fotograma(path.join(dir, f), path.join(salida, "frames", s, String(lado), f.replace(".png", ".webp")), lado));
    }
  });
  await enParalelo(trabajos);
  const peso = (lado) => {
    const d = path.join(salida, "frames", s, String(lado));
    return fs.existsSync(d) ? fs.readdirSync(d).reduce((a, f) => a + fs.statSync(path.join(d, f)).size, 0) : 0;
  };
  console.log(s, archivos.length, "fotogramas |", (peso(900) / 1e6).toFixed(1), "MB (900) |", (peso(600) / 1e6).toFixed(1), "MB (600)");
}

// Espuma del café: imagen única, sin recortar bordes (se ve dentro de un círculo).
const espuma = path.join(entrada, "espuma", "0000.png");
if (fs.existsSync(espuma) && (!soloEstas.length || soloEstas.includes("espuma"))) {
  const d = path.join(salida, "frames", "espuma");
  fs.mkdirSync(d, { recursive: true });
  await sharp(espuma).flatten({ background: "#D9B883" }).resize(1400, 1400).webp({ quality: 80, effort: 5 }).toFile(path.join(d, "espuma.webp"));
  console.log("espuma ok");
}

// Piezas sueltas para los lienzos: normal y desenfocada (las que pasan muy cerca de la cámara).
const sueltas = path.join(entrada, "sueltas");
if (fs.existsSync(sueltas) && (!soloEstas.length || soloEstas.includes("sueltas"))) {
  const d = path.join(salida, "img");
  fs.mkdirSync(d, { recursive: true });
  for (const f of fs.readdirSync(sueltas).filter((x) => x.endsWith(".png") && !x.startsWith("lechuga"))) {
    const nombre = f.replace(".png", "");
    await sharp(path.join(sueltas, f)).resize(220, 220).webp({ quality: 80, alphaQuality: 80, effort: 5 }).toFile(path.join(d, nombre + ".webp"));
    if (["grano0", "tomate", "frita", "aceituna"].includes(nombre)) {
      await sharp(path.join(sueltas, f)).resize(220, 220).extend({ top: 30, bottom: 30, left: 30, right: 30, background: { r: 0, g: 0, b: 0, alpha: 0 } }).blur(7).webp({ quality: 70, alphaQuality: 70, effort: 5 }).toFile(path.join(d, nombre + "-d.webp"));
    }
  }
  console.log("sueltas ok");
}

// Grano de película: un mosaico de puntitos casi invisibles.
{
  const lado = 240;
  const px = Buffer.alloc(lado * lado * 4);
  let x = 123456789;
  for (let i = 0; i < lado * lado; i++) {
    x ^= x << 13; x ^= x >>> 17; x ^= x << 5;
    const v = (x >>> 0) % 256;
    const claro = v > 127;
    px[i * 4] = px[i * 4 + 1] = px[i * 4 + 2] = claro ? 255 : 0;
    px[i * 4 + 3] = (Math.abs(v - 127) / 127) * 26;
  }
  fs.mkdirSync(path.join(salida, "img"), { recursive: true });
  await sharp(px, { raw: { width: lado, height: lado, channels: 4 } }).webp({ quality: 40, alphaQuality: 50 }).toFile(path.join(salida, "img", "grano.webp"));
}
