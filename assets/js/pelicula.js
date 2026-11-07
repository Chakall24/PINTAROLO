// ======================================================================
// pelicula.js: convierte la página en una película que se reproduce con el scroll.
//
// La idea: hay UNA sola línea de tiempo de GSAP (como la de un editor de vídeo) y
// ScrollTrigger une su cabezal a la barra de scroll. Bajar = avanzar; subir = rebobinar.
// Por eso todo lo que se mueve aquí depende de la posición y no del reloj: se puede
// parar, ir hacia atrás o saltar a cualquier momento, como en un vídeo.
//
// Unidad de tiempo de la película: 1 = una pantalla de scroll (100% de la altura).
// ======================================================================
(function () {
  const raiz = document.documentElement;
  if (!raiz.classList.contains("pelicula")) return;     // versión sin animación: no hay nada que hacer
  if (!window.gsap || !window.ScrollTrigger) {          // si GSAP no cargó, se ve la página normal
    raiz.classList.remove("pelicula");
    return;
  }
  gsap.registerPlugin(ScrollTrigger);
  gsap.defaults({ ease: "none" });

  // ---------- 1. El guion: cuándo empieza cada escena ----------
  const T = {
    inicio: 0,
    tapa: 1.1,
    aperitivo: 5.9,
    comidas: 10.4,
    bocadillos: 14.8,
    hamburguesas: 18.9,
    raciones: 22.9,
    cierre: 26.1,
    fin: 28.0,
  };

  // Dónde cae cada enlace del menú: en el momento en que su escena se lee bien.
  const ANCLAS = {
    "inicio": 0,
    "carta": T.tapa + 1.0,
    "con-tapa": T.tapa + 1.0,
    "aperitivo": T.aperitivo + 1.4,
    "platos-combinados": T.comidas + 2.2,
    "bocadillos": T.bocadillos + 1.9,
    "hamburguesas": T.hamburguesas + 1.9,
    "raciones": T.raciones + 1.9,
  };

  // La altura de la página es la duración de la película (más una pantalla, la del propio escenario).
  document.getElementById("pelicula").style.setProperty("--pantallas", T.fin + 1);

  // ---------- 2. Secuencias de fotogramas ----------
  // Cada plato es una tira de imágenes con fondo transparente: se dibuja la que toque en un <canvas>,
  // como los fotogramas de un vídeo. Un vídeo normal no sirve aquí: no se puede ir marcha atrás
  // fotograma a fotograma con suavidad y además no tendría el fondo transparente.
  const pantalla = Math.min(window.innerWidth, window.innerHeight * 1.1) * Math.min(window.devicePixelRatio || 1, 2);
  const LADO = pantalla > 1000 ? 900 : 600;   // 900 px en ordenador, 600 px en móvil
  const POCA_MEMORIA = LADO === 600;           // en móvil se libera lo que queda lejos

  const cola = [];
  let cargando = 0;
  const MAX_A_LA_VEZ = 6;

  function siguienteDeLaCola() {
    while (cargando < MAX_A_LA_VEZ && cola.length) {
      const trabajo = cola.shift();
      const s = trabajo.s;
      if (!s.pedida || s.imgs[trabajo.i]) continue;
      cargando++;
      const img = new Image();
      img.decoding = "async";
      img.onload = () => {
        cargando--;
        if (s.pedida) {
          s.imgs[trabajo.i] = img;
          s.dibujar();
        }
        siguienteDeLaCola();
      };
      img.onerror = () => {
        cargando--;
        siguienteDeLaCola();
      };
      img.src = s.url(trabajo.i);
    }
  }

  function crearSecuencia(fig) {
    const nombre = fig.dataset.seq;
    const n = Number(fig.dataset.n);
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = LADO;
    fig.appendChild(canvas);
    const ctx = canvas.getContext("2d");
    const s = {
      nombre, n, fig,
      imgs: new Array(n),
      pedida: false,
      visible: -1,     // fotograma que hay dibujado
      quiero: 0,       // fotograma que pide la línea de tiempo (con decimales)
      url: (i) => "assets/frames/" + nombre + "/" + LADO + "/" + String(i).padStart(4, "0") + ".webp",
      pedir() {
        if (s.pedida) return;
        s.pedida = true;
        // Primero uno de cada 8, luego de 4, de 2 y el resto: enseguida se puede rebobinar
        // (a saltos) y la secuencia va ganando suavidad mientras carga.
        const hechos = new Set();
        // En móvil hay un fotograma de cada dos: pesa la mitad y se sigue viendo fluido.
        (POCA_MEMORIA ? [8, 4, 2] : [8, 4, 2, 1]).forEach((paso) => {
          for (let i = 0; i < n; i += paso) {
            if (!hechos.has(i)) {
              hechos.add(i);
              cola.push({ s, i });
            }
          }
        });
        if (!hechos.has(n - 1)) cola.push({ s, i: n - 1 });
        siguienteDeLaCola();
      },
      soltar() {
        if (!s.pedida) return;
        s.pedida = false;
        s.imgs = new Array(n);
        s.visible = -1;
      },
      dibujar() {
        const q = Math.max(0, Math.min(n - 1, Math.round(s.quiero)));
        // Si ese fotograma aún no ha llegado, usamos el más cercano que ya tengamos.
        let elegido = -1;
        for (let d = 0; d < n; d++) {
          if (s.imgs[q - d]) { elegido = q - d; break; }
          if (s.imgs[q + d]) { elegido = q + d; break; }
        }
        if (elegido < 0 || elegido === s.visible) return;
        ctx.clearRect(0, 0, LADO, LADO);
        ctx.drawImage(s.imgs[elegido], 0, 0, LADO, LADO);
        s.visible = elegido;
      },
    };
    return s;
  }

  const seq = {};
  document.querySelectorAll("[data-seq]").forEach((fig) => {
    seq[fig.dataset.seq] = crearSecuencia(fig);
  });

  // Tramo de la película en el que se usa cada secuencia: así solo se descarga lo que va a hacer falta.
  const VENTANAS = [
    [seq.cafe, T.inicio, T.aperitivo + 0.2],
    [seq.croissant, T.tapa + 0.8, T.tapa + 3.6],
    [seq.tortilla, T.aperitivo, T.aperitivo + 2.4],
    [seq.jamon, T.aperitivo + 0.9, T.aperitivo + 3.3],
    [seq.empanada, T.aperitivo + 1.8, T.aperitivo + 4.2],
    [seq.moruno, T.aperitivo + 2.3, T.comidas + 0.2],
    [seq.plato, T.comidas, T.bocadillos],
    [seq.bocadillo, T.bocadillos, T.hamburguesas],
    [seq.burger, T.hamburguesas, T.raciones],
    [seq.racion, T.raciones, T.cierre + 0.3],
  ];

  function gestionarCargas(t) {
    VENTANAS.forEach(([s, a, b]) => {
      if (t > a - 2.5 && t < b + 1) s.pedir();
      else if (POCA_MEMORIA && (t < a - 6 || t > b + 6)) s.soltar();
    });
  }

  // ---------- 3. Lienzos: piezas sueltas y vapor ----------
  const lienzoAtras = document.getElementById("capa-atras");
  const lienzoDelante = document.getElementById("capa-delante");
  const ctxAtras = lienzoAtras.getContext("2d");
  const ctxDelante = lienzoDelante.getContext("2d");
  const ESCALA_LIENZO = Math.min(window.devicePixelRatio || 1, 1.5);
  const ES_MOVIL = window.innerWidth < 880;
  let W = 0;
  let H = 0;

  function medirLienzos() {
    const esc = document.getElementById("escenario");
    // En el móvil, la barra de direcciones avisa de "cambio de tamaño" al hacer scroll aunque nada cambie:
    // si las medidas son las mismas no se toca el lienzo (borrarlo daría un parpadeo).
    if (esc.clientWidth === W && esc.clientHeight === H) return;
    W = esc.clientWidth;
    H = esc.clientHeight;
    [lienzoAtras, lienzoDelante].forEach((c) => {
      c.width = Math.round(W * ESCALA_LIENZO);
      c.height = Math.round(H * ESCALA_LIENZO);
    });
    ctxAtras.setTransform(ESCALA_LIENZO, 0, 0, ESCALA_LIENZO, 0, 0);
    ctxDelante.setTransform(ESCALA_LIENZO, 0, 0, ESCALA_LIENZO, 0, 0);
    tiempoPintado = -1;
  }

  const sprites = {};
  ["grano0", "grano1", "grano2", "grano3", "tomate", "frita", "aceituna", "sesamo",
    "grano0-d", "tomate-d", "frita-d", "aceituna-d"].forEach((nombre) => {
    const img = new Image();
    img.src = "assets/img/" + nombre + ".webp";
    sprites[nombre] = img;
  });

  // Generador de números aleatorios "con semilla": da siempre los mismos, y así al rebobinar
  // cada grano vuelve exactamente por donde vino.
  function azar(semilla) {
    let x = semilla;
    return () => {
      x = (x * 16807) % 2147483647;
      return (x - 1) / 2147483646;
    };
  }

  const piezas = [];
  // a y b: tramo de la película; imgs: posibles imágenes; n: cuántas; tam: tamaño (fracción de la pantalla);
  // sube: si van hacia arriba en vez de caer; lado: si se mueven de derecha a izquierda; delante: capa delantera.
  // xMin, xMax, yMin, yMax: franja de pantalla por la que pasan. La capa delantera queda por encima del texto,
  // así que se le marca un camino que no pise nunca los títulos ni los precios. En el móvil no hay sitio: no se usa.
  function sembrar({ a, b, imgs, n, tam, sube = false, lado = false, delante = false, semilla = 7, alfa = 1, xMin = 0, xMax = 1, yMin = 0, yMax = 1 }) {
    if (delante && ES_MOVIL) return;
    const r = azar(semilla);
    const cuantas = ES_MOVIL ? Math.ceil(n * 0.6) : n;
    for (let i = 0; i < cuantas; i++) {
      const prof = 0.45 + r() * 0.55;        // lo más lejano es más pequeño y se mueve más despacio
      const dur = (b - a) * (0.55 + r() * 0.45);
      const ini = a + r() * (b - a - dur);
      const p = {
        a: ini,
        b: ini + dur,
        img: imgs[Math.floor(r() * imgs.length)],
        x: xMin + r() * (xMax - xMin),
        y: yMin + r() * (yMax - yMin),
        recorrido: (0.9 + r() * 0.5) * prof,
        tam: tam * prof * (0.8 + r() * 0.4),
        rot0: r() * 6.28,
        rot: (r() - 0.5) * 7,
        sube, lado, delante, alfa,
      };
      piezas.push(p);
    }
  }

  const GRANOS = ["grano0", "grano1", "grano2", "grano3"];
  sembrar({ a: T.inicio, b: T.aperitivo, imgs: GRANOS, n: 22, tam: 0.075, semilla: 11 });
  sembrar({ a: T.tapa + 0.2, b: T.aperitivo - 0.3, imgs: ["grano0-d"], n: 4, tam: 0.3, delante: true, semilla: 23, alfa: 0.9, xMin: 0.34, xMax: 0.66 });
  sembrar({ a: T.aperitivo, b: T.comidas, imgs: ["aceituna"], n: 9, tam: 0.06, lado: true, semilla: 31 });
  sembrar({ a: T.aperitivo + 0.5, b: T.comidas, imgs: ["aceituna-d"], n: 3, tam: 0.26, lado: true, delante: true, semilla: 37, alfa: 0.9, yMin: 0.62, yMax: 0.86 });
  sembrar({ a: T.comidas, b: T.bocadillos, imgs: ["frita", "tomate"], n: 11, tam: 0.11, semilla: 41 });
  sembrar({ a: T.comidas, b: T.comidas + 1.3, imgs: ["frita-d", "tomate-d"], n: 3, tam: 0.34, delante: true, semilla: 43, alfa: 0.9, xMin: 0.1, xMax: 0.55 });
  sembrar({ a: T.bocadillos, b: T.hamburguesas, imgs: ["tomate", "aceituna"], n: 8, tam: 0.08, semilla: 47 });
  sembrar({ a: T.hamburguesas, b: T.raciones, imgs: ["sesamo"], n: 22, tam: 0.06, sube: true, semilla: 53 });
  sembrar({ a: T.raciones, b: T.cierre, imgs: ["aceituna"], n: 8, tam: 0.05, semilla: 61 });

  let tiempoPintado = -1;

  function pintarPiezas(t) {
    if (t === tiempoPintado) return;
    tiempoPintado = t;
    const lado = Math.min(W, H) * (ES_MOVIL ? 1.1 : 1);
    ctxAtras.clearRect(0, 0, W, H);
    if (!vaporActivo) ctxDelante.clearRect(0, 0, W, H);
    for (const p of piezas) {
      if (t < p.a || t > p.b) continue;
      if (p.delante && vaporActivo) continue;     // mientras hay vapor, la capa delantera la pinta el reloj (ver abajo)
      const u = (t - p.a) / (p.b - p.a);
      const img = sprites[p.img];
      if (!img.complete || !img.naturalWidth) continue;
      const tam = p.tam * lado;
      let x, y;
      if (p.lado) {
        x = (1.15 - u * (1.3 + p.recorrido * 0.3)) * W;
        y = p.y * H;
      } else if (p.sube) {
        x = p.x * W;
        y = (1.15 - u * (1.3 + p.recorrido * 0.3)) * H;
      } else {
        x = p.x * W;
        y = (-0.15 + u * (1.3 + p.recorrido * 0.3)) * H;
      }
      const c = p.delante ? ctxDelante : ctxAtras;
      c.save();
      c.globalAlpha = p.alfa;
      c.translate(x, y);
      c.rotate(p.rot0 + p.rot * u);
      c.drawImage(img, -tam / 2, -tam / 2, tam, tam);
      c.restore();
    }
  }

  // ----- Vapor del café. Es lo único que se mueve solo, con el reloj: está vivo aunque no hagas scroll. -----
  const motaVapor = document.createElement("canvas");
  motaVapor.width = motaVapor.height = 128;
  (function () {
    const c = motaVapor.getContext("2d");
    const g = c.createRadialGradient(64, 64, 0, 64, 64, 64);
    g.addColorStop(0, "rgba(255,255,255,0.55)");
    g.addColorStop(0.5, "rgba(255,255,255,0.18)");
    g.addColorStop(1, "rgba(255,255,255,0)");
    c.fillStyle = g;
    c.fillRect(0, 0, 128, 128);
  })();

  const volutas = [];
  const rVapor = azar(99);
  for (let i = 0; i < (ES_MOVIL ? 12 : 22); i++) {
    volutas.push({ fase: rVapor(), x: rVapor() - 0.5, vaiven: rVapor() * 6.28, tam: 0.5 + rVapor() * 0.8 });
  }
  let vaporActivo = false;
  let segundos = 0;

  function pintarVapor() {
    ctxDelante.clearRect(0, 0, W, H);
    const caja = seq.cafe.fig.getBoundingClientRect();
    const u = seq.cafe.quiero / (seq.cafe.n - 1);
    const fuerza = Math.max(0, 1 - u * 2.2);          // al mirar desde arriba, el vapor deja de verse
    if (fuerza <= 0) return;
    const cx = caja.left + caja.width * 0.5;
    const cy = caja.top + caja.height * (0.40 + u * 0.1);
    const ancho = caja.width * 0.2;
    ctxDelante.save();
    for (const v of volutas) {
      const vida = (v.fase + segundos * 0.11) % 1;    // 0 = acaba de salir de la taza, 1 = se ha disuelto
      const alto = vida * caja.height * 0.55;
      const x = cx + v.x * ancho * (1 + vida) + Math.sin(segundos * 0.8 + v.vaiven + vida * 5) * ancho * 0.35 * vida;
      const y = cy - alto;
      const tam = ancho * v.tam * (0.5 + vida * 1.7);
      ctxDelante.globalAlpha = fuerza * 0.34 * Math.sin(vida * Math.PI);
      ctxDelante.drawImage(motaVapor, x - tam / 2, y - tam / 2, tam, tam);
    }
    ctxDelante.restore();
  }

  gsap.ticker.add((time) => {
    segundos = time;
    if (vaporActivo) {
      pintarVapor();
      const t = pelicula.time();
      for (const p of piezas) {
        if (!p.delante || t < p.a || t > p.b) continue;
        const u = (t - p.a) / (p.b - p.a);
        const img = sprites[p.img];
        if (!img.complete || !img.naturalWidth) continue;
        const tam = p.tam * Math.min(W, H);
        ctxDelante.save();
        ctxDelante.globalAlpha = p.alfa;
        ctxDelante.translate(p.x * W, (-0.15 + u * (1.3 + p.recorrido * 0.3)) * H);
        ctxDelante.rotate(p.rot0 + p.rot * u);
        ctxDelante.drawImage(img, -tam / 2, -tam / 2, tam, tam);
        ctxDelante.restore();
      }
    }
  });

  // ---------- 4. La línea de tiempo ----------
  const pelicula = gsap.timeline({
    scrollTrigger: {
      trigger: "#pelicula",
      start: "top top",
      end: "bottom bottom",
      scrub: 0.5,                 // el cabezal tarda medio segundo en alcanzar al scroll: da suavidad de vídeo
      invalidateOnRefresh: true,  // al girar el móvil o cambiar el tamaño, recalcula los recorridos
    },
    onUpdate() {
      const t = pelicula.time();
      gestionarCargas(t);
      vaporActivo = t < T.tapa + 3.2;
      pintarPiezas(t);
    },
  });

  // Tiempo total exacto, aunque el último movimiento acabe antes.
  pelicula.set({}, {}, T.fin);

  // Ayudantes: un movimiento de entrada y otro de salida, y el avance de fotogramas.
  const entra = (el, t, dur, desde, hasta = {}) => pelicula.fromTo(el, desde, { x: 0, y: 0, xPercent: 0, rotation: 0, scale: 1, autoAlpha: 1, ...hasta, duration: dur, ease: "power2.out" }, t);
  const sale = (el, t, dur, a) => pelicula.to(el, { ...a, duration: dur, ease: "power2.in" }, t);
  const fotogramas = (s, t, dur, desde, hasta) => pelicula.fromTo(s, { quiero: desde }, { quiero: hasta, duration: dur, onUpdate: s.dibujar, immediateRender: false }, t);
  const aparece = (id, a, b) => {
    pelicula.set(id, { autoAlpha: 1 }, a);
    pelicula.set(id, { autoAlpha: 0 }, b);
  };
  const cielo = (clase, t, dur = 0.6) => pelicula.to(clase, { opacity: 1, duration: dur }, t);

  // El rótulo de fondo de cada escena cruza despacio la pantalla.
  const cruza = (el, a, b, desde = 12, hasta = -40) => pelicula.fromTo(el, { xPercent: desde }, { xPercent: hasta, duration: b - a }, a);

  // Las escenas arrancan ocultas; la portada y la taza son las únicas visibles al abrir.
  gsap.set(".escena:not(#inicio, #carta), .espuma", { autoAlpha: 0 });
  gsap.set(".pieza-cafe", { transformOrigin: "50% 50%" });
  gsap.set(".gigante", { yPercent: -50 });
  gsap.set(".escena-tapa .tapa, .carta-intro, .gigante-tapa, .pieza-croissant, .hoja, .aperitivo-texto, .pieza-pincho, .pieza-plato, .pieza-bocadillo, .pieza-burger, .pieza-racion", { autoAlpha: 0 });

  // Responsive: lo que cambia entre ordenador y móvil es solo la posición inicial de la taza.
  const esAncho = window.matchMedia("(min-width: 880px)");

  // ----- 7:30 Portada -----
  pelicula.to(".r-a", { xPercent: -46, scale: 1.3, autoAlpha: 0, duration: 1.1, ease: "power1.in" }, 0);
  pelicula.to(".r-b", { xPercent: 46, scale: 1.3, autoAlpha: 0, duration: 1.1, ease: "power1.in" }, 0);
  pelicula.to(".portada-izq", { y: -50, autoAlpha: 0, duration: 0.5 }, 0.06);
  pelicula.to(".portada-der", { y: -50, autoAlpha: 0, duration: 0.5 }, 0.12);
  pelicula.to(".pista", { autoAlpha: 0, duration: 0.15 }, 0);
  pelicula.set("#inicio", { autoAlpha: 0 }, 1.3);

  // La taza crece desde abajo y la cámara empieza a subir.
  pelicula.fromTo(".pieza-cafe",
    { y: () => window.innerHeight * (esAncho.matches ? 0.16 : 0.2), scale: () => (esAncho.matches ? 0.78 : 1) },
    { y: 0, scale: 1, duration: 1.4, ease: "power1.inOut" }, 0);
  fotogramas(seq.cafe, 0, T.tapa + 1.0, 0, 26);

  // ----- Con tapa -----
  pelicula.set(".gigante-tapa", { autoAlpha: 1 }, T.tapa);
  cruza(".gigante-tapa", T.tapa, T.tapa + 3.8, 14, -32);
  entra(".carta-intro", T.tapa + 0.3, 0.6, { x: -80, autoAlpha: 0 });
  entra(".escena-tapa .tapa", T.tapa + 0.4, 0.6, { x: 120, autoAlpha: 0, rotation: 2 });

  // El croissant entra deslizándose y gira.
  entra(".pieza-croissant", T.tapa + 1.1, 0.9, { x: () => -window.innerWidth * 0.62, rotation: -8, autoAlpha: 1 });
  fotogramas(seq.croissant, T.tapa + 1.1, 2.3, 0, 23);
  sale(".pieza-croissant", T.tapa + 2.8, 0.6, { x: () => -window.innerWidth * 0.8, rotation: -10 });
  sale(".carta-intro", T.tapa + 2.9, 0.4, { y: -60, autoAlpha: 0 });
  sale(".escena-tapa .tapa", T.tapa + 2.9, 0.4, { x: 140, autoAlpha: 0 });
  pelicula.to(".gigante-tapa", { autoAlpha: 0, duration: 0.5 }, T.tapa + 3.1);

  // La cámara sube hasta mirar el café desde arriba y entra en la espuma.
  fotogramas(seq.cafe, T.tapa + 2.9, 0.95, 26, 59);
  pelicula.to(".pieza-cafe", { y: () => (esAncho.matches ? 0 : -window.innerHeight * 0.02), scale: 1.08, duration: 0.95, ease: "power1.inOut" }, T.tapa + 2.9);

  // La cámara entra en la espuma. Se amplía la taza entera (la espuma va dentro) hasta que el café llena la pantalla.
  const zoom = T.tapa + 3.8;
  const escalaFinal = () => {
    const taza = seq.cafe.fig.offsetWidth * 0.316;   // diámetro de la espuma dentro de la taza
    return (Math.hypot(window.innerWidth, window.innerHeight) * 1.5) / taza;
  };
  pelicula.fromTo(".espuma", { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.14 }, zoom);
  pelicula.to(".pieza-cafe", { scale: escalaFinal, duration: 1.0, ease: "power3.in" }, zoom);
  cielo(".cielo-claro", zoom + 0.72, 0.01);
  pelicula.set("#aperitivo", { autoAlpha: 1 }, zoom + 0.72);
  pelicula.to(".pieza-cafe", { autoAlpha: 0, duration: 0.28 }, zoom + 0.8);
  pelicula.set("#carta", { autoAlpha: 0 }, zoom + 1.1);

  // ----- 12:00 Aperitivo: los pinchos desfilan como por una barra -----
  cruza(".gigante-aperitivo", T.aperitivo - 0.1, T.comidas, 18, -58);
  entra(".aperitivo-texto", T.aperitivo + 0.3, 0.6, { y: 50, autoAlpha: 0 });
  const pinchos = gsap.utils.toArray(".pieza-pincho");
  const pasoPincho = 0.92;
  pinchos.forEach((el, i) => {
    const s = seq[el.dataset.seq];
    const t0 = T.aperitivo + 0.2 + i * pasoPincho;
    const altura = i % 2 ? 0.04 : -0.03;
    pelicula.fromTo(el,
      { x: () => window.innerWidth * 0.82, y: () => window.innerHeight * altura, scale: 0.72, rotation: 6, autoAlpha: 1 },
      { x: 0, y: () => window.innerHeight * altura, scale: 1, rotation: 0, duration: 1.15, ease: "power2.out" }, t0);
    pelicula.to(el, { x: () => -window.innerWidth * 0.82, scale: 0.72, rotation: -6, duration: 1.15, ease: "power2.in" }, t0 + 1.15);
    fotogramas(s, t0, 2.3, 0, s.n - 1);
  });
  sale(".aperitivo-texto", T.comidas - 0.5, 0.4, { y: -50, autoAlpha: 0 });
  pelicula.set("#aperitivo", { autoAlpha: 0 }, T.comidas + 0.1);

  // ----- Escenas de plato: comida en movimiento + hoja de la carta -----
  function escenaPlato({ id, t, fin, pieza, s, hoja, gigante, ciel, lado }) {
    const cuanto = lado === "der" ? 1 : -1;
    aparece(id, t - 0.1, fin);
    cielo(ciel, t - 0.25, 0.5);
    cruza(gigante, t - 0.1, fin, 16, -46);
    // Entra la comida.
    entra(pieza, t + 0.05, 0.85, { y: () => window.innerHeight * 0.42, scale: 0.8, autoAlpha: 1, rotation: -3 * cuanto });
    fotogramas(s, t + 0.1, 2.0, 0, s.n - 1);
    // Entra la hoja de la carta por su lado, como si te la pusieran delante.
    entra(hoja, t + 1.25, 0.65, { x: () => cuanto * window.innerWidth * 0.7, rotation: 3 * cuanto, autoAlpha: 1 });
    // Si la lista no cabe en la hoja, corre como los créditos de una película.
    const visor = document.querySelector(hoja + " .visor");
    const rollo = document.querySelector(hoja + " .rollo");
    pelicula.to(rollo, { y: () => -Math.max(0, rollo.scrollHeight - visor.clientHeight), duration: fin - t - 3.0 }, t + 2.0);
    // Y todo se va.
    sale(hoja, fin - 0.75, 0.6, { x: () => cuanto * window.innerWidth * 0.75, rotation: 3 * cuanto, autoAlpha: 1 });
    sale(pieza, fin - 0.65, 0.6, { y: () => -window.innerHeight * 0.62, scale: 0.85, autoAlpha: 1 });
  }

  // Del mediodía a la noche: el cielo va bajando de luz.
  escenaPlato({ id: "#comidas", t: T.comidas, fin: T.bocadillos, pieza: ".pieza-plato", s: seq.plato, hoja: "#platos-combinados", gigante: ".gigante-comidas", ciel: ".cielo-verde", lado: "der" });
  escenaPlato({ id: "#tarde", t: T.bocadillos, fin: T.hamburguesas, pieza: ".pieza-bocadillo", s: seq.bocadillo, hoja: "#bocadillos", gigante: ".gigante-bocadillos", ciel: ".cielo-arena", lado: "izq" });
  escenaPlato({ id: "#noche", t: T.hamburguesas, fin: T.raciones, pieza: ".pieza-burger", s: seq.burger, hoja: "#hamburguesas", gigante: ".gigante-burger", ciel: ".cielo-oscuro", lado: "der" });
  escenaPlato({ id: "#tabla", t: T.raciones, fin: T.cierre, pieza: ".pieza-racion", s: seq.racion, hoja: "#raciones", gigante: ".gigante-raciones", ciel: ".cielo-noche", lado: "izq" });

  // ----- 22:00 Cierre: se vuelve al rótulo, ahora de noche -----
  pelicula.set("#cierre", { autoAlpha: 1 }, T.cierre - 0.2);
  entra(".cierre-hora", T.cierre - 0.15, 0.5, { y: 50, autoAlpha: 0 });
  entra(".cierre-rotulo", T.cierre, 0.7, { scale: 0.86, autoAlpha: 0 });
  entra(".cierre-texto", T.cierre + 0.35, 0.5, { y: 40, autoAlpha: 0 });
  entra(".escena-cierre .estado", T.cierre + 0.45, 0.5, { y: 40, autoAlpha: 0 });
  entra(".escena-cierre .estado-detalle", T.cierre + 0.55, 0.5, { y: 40, autoAlpha: 0 });
  entra(".cierre-seguir", T.cierre + 0.75, 0.5, { y: 30, autoAlpha: 0 });

  // ---------- 5. Saltar a un momento de la película (lo usan los enlaces del menú) ----------
  function scrollDeTiempo(t) {
    const st = pelicula.scrollTrigger;
    return st.start + (st.end - st.start) * (t / pelicula.duration());
  }
  function irA(t, suave) {
    window.scrollTo({ top: scrollDeTiempo(t), behavior: suave ? "smooth" : "auto" });
  }

  // ----- Mini botón play/stop: baja la página solo, a velocidad constante. Stop la deja donde está. -----
  const botonPlay = document.getElementById("play");
  const SEGUNDOS_POR_PANTALLA = 2.8;
  let reproduciendo = false;
  let resto = 0;

  function avanzar(_t, delta) {
    const st = pelicula.scrollTrigger;
    const v = (window.innerHeight * 1) / SEGUNDOS_POR_PANTALLA;   // píxeles por segundo
    resto += v * (Math.min(delta, 50) / 1000);
    const px = Math.floor(resto);
    if (px > 0) {
      resto -= px;
      window.scrollBy(0, px);
    }
    if (window.scrollY >= st.end - 2) parar();
  }
  function parar() {
    if (!reproduciendo) return;
    reproduciendo = false;
    gsap.ticker.remove(avanzar);
    botonPlay.setAttribute("aria-pressed", "false");
    botonPlay.setAttribute("aria-label", "Reproducir la película");
    raiz.classList.remove("reproduciendo");
  }
  function empezar() {
    if (reproduciendo) return;
    const st = pelicula.scrollTrigger;
    if (window.scrollY >= st.end - 2) window.scrollTo(0, 0);    // si ya acabó, vuelve a empezar
    reproduciendo = true;
    resto = 0;
    gsap.ticker.add(avanzar);
    botonPlay.setAttribute("aria-pressed", "true");
    botonPlay.setAttribute("aria-label", "Parar la película");
    raiz.classList.add("reproduciendo");
  }
  botonPlay.addEventListener("click", () => (reproduciendo ? parar() : empezar()));
  // Si el visitante toca la página, manda él.
  // (Tocar el propio botón no cuenta: si no, en el móvil el dedo pararía y el clic volvería a arrancar).
  ["wheel", "touchstart"].forEach((ev) => window.addEventListener(ev, (e) => {
    if (!(e.target instanceof Element && e.target.closest("#play"))) parar();
  }, { passive: true }));
  window.addEventListener("keydown", (e) => {
    if (["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "].includes(e.key) && e.target !== botonPlay) parar();
  });

  // El reproductor se retira cuando la película termina y empieza la página normal.
  ScrollTrigger.create({
    trigger: "#donde",
    start: "top 70%",
    onEnter: () => raiz.classList.add("pelicula-acabada"),
    onLeaveBack: () => raiz.classList.remove("pelicula-acabada"),
  });

  // ---------- 6. Enlaces del menú: en vez de saltar a un sitio, llevan la película a ese momento ----------
  document.addEventListener("click", (e) => {
    const a = e.target.closest('a[href^="#"]');
    if (!a) return;
    const id = a.getAttribute("href").slice(1);
    if (id in ANCLAS) {
      e.preventDefault();
      parar();
      history.replaceState(null, "", "#" + id);
      irA(ANCLAS[id], true);
    } else {
      // "Dónde estamos" y "Horario" ya están fuera de la película: es un desplazamiento normal.
      e.preventDefault();
      parar();
      history.replaceState(null, "", "#" + id);
      const destino = document.getElementById(id);
      if (destino) destino.scrollIntoView({ behavior: "smooth" });
    }
  });

  // ---------- 7. Medidas y arranque ----------
  function medirAviso() {
    raiz.style.setProperty("--aviso", document.getElementById("aviso").offsetHeight + "px");
  }
  medirAviso();
  medirLienzos();
  window.addEventListener("resize", () => {
    medirAviso();
    medirLienzos();
  });
  ScrollTrigger.addEventListener("refresh", () => {
    medirLienzos();
    pintarPiezas(pelicula.time());
  });

  seq.cafe.pedir();
  seq.croissant.pedir();
  gestionarCargas(0);
  vaporActivo = true;

  // Las tipografías cambian las medidas al cargar: se recalcula todo.
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => ScrollTrigger.refresh());
  window.addEventListener("load", () => {
    ScrollTrigger.refresh();
    // Si se entra con un enlace directo (por ejemplo #raciones), la película salta a ese momento.
    const id = location.hash.slice(1);
    if (id in ANCLAS) irA(ANCLAS[id], false);
  });
  // Y si el ancla cambia estando ya en la página (por ejemplo, alguien la escribe en la barra de direcciones).
  window.addEventListener("hashchange", () => {
    const id = location.hash.slice(1);
    if (id in ANCLAS) irA(ANCLAS[id], false);
  });
})();
