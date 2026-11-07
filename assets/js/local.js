// ======================================================================
// local.js: los datos reales del bar. Mira la fecha y la hora de Salamanca y decide
// si está abierto. Esto no depende de la película: funciona igual en las dos versiones.
// Las líneas que empiezan por // son comentarios (el navegador las ignora).
// ======================================================================

// ---------- DATOS DEL NEGOCIO: lo único que hay que tocar si cambia el horario ----------
// Las franjas del día, en minutos desde medianoche (7:30 = 7 x 60 + 30 = 450).
// OJO: estas franjas son una propuesta. Confírmalas con el dueño (sobre todo cuándo empiezan las comidas).
const FRANJAS = [
  { nombre: "Desayunos", desde: 450, hasta: 720, frase: "hora de desayunar" },      // 7:30 a 12:00
  { nombre: "Aperitivo", desde: 720, hasta: 810, frase: "hora del aperitivo" },     // 12:00 a 13:30
  { nombre: "Comidas", desde: 810, hasta: 990, frase: "hora de comer" },            // 13:30 a 16:30
  { nombre: "Tarde y noche", desde: 990, hasta: 1320, frase: "hora de tapear" },    // 16:30 a 22:00
];

const APERTURA = FRANJAS[0].desde;
const CIERRE = FRANJAS[FRANJAS.length - 1].hasta;
const DIAS_ABIERTO = [1, 2, 3, 4, 5];  // días que abre: 0 = domingo, 1 = lunes ... 6 = sábado

// Días sueltos en que cierra aunque normalmente abra (festivos, vacaciones...).
// Formato: "año-mes-día": "motivo". Ejemplo (quita las dos barras // para activarlo):
const CIERRES_ESPECIALES = {
  // "2026-12-08": "la Inmaculada",
  // "2026-12-25": "Navidad",
};
// Está vacío a propósito: hay que preguntarle al dueño qué festivos cierra. Sin esto, la web diría
// "Abierto ahora" un día de Navidad que caiga entre semana.

const NOMBRES_DIA = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
const NOMBRES_MES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                     "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

const URL_MAPA = "https://www.google.com/maps?q=Pintarolo,+Av.+de+Filiberto+Villalobos+65,+37007+Salamanca&output=embed";

// ---------- Elementos del HTML que vamos a cambiar ----------
const estadosTexto = document.querySelectorAll("[data-estado-texto]");     // el estado sale en la portada y en el cierre
const estadosDetalle = document.querySelectorAll("[data-estado-detalle]");
const barra = document.getElementById("barra");
const capaClara = document.getElementById("capa-clara");
const capaOscura = document.getElementById("capa-oscura");
const marca = document.getElementById("marca");

// ---------- Pequeñas herramientas ----------
function formatoHora(minutos) {                        // 785 -> "13:05"
  const h = Math.floor(minutos / 60);
  const m = String(Math.floor(minutos % 60)).padStart(2, "0");
  return h + ":" + m;
}

function textoMinutos(n) {
  return n + (n === 1 ? " minuto" : " minutos");
}

// Cambia el texto solo si es distinto: si reescribiéramos lo mismo cada minuto,
// el lector de pantalla de una persona ciega lo repetiría cada minuto.
function escribir(elemento, texto) {
  if (elemento.textContent !== texto) elemento.textContent = texto;
}

// Usamos la hora de Madrid aunque el visitante esté en otro país: lo que importa es la hora del bar.
function ahoraEnSalamanca() {
  const partes = new Intl.DateTimeFormat("es-ES", {
    timeZone: "Europe/Madrid",
    year: "numeric", month: "numeric", day: "numeric",
    hour: "numeric", minute: "numeric",
    hourCycle: "h23",
  }).formatToParts(new Date());
  const valor = (tipo) => Number(partes.find((p) => p.type === tipo).value);
  return {
    anio: valor("year"),
    mes: valor("month"),
    dia: valor("day"),
    minutos: valor("hour") * 60 + valor("minute"),
  };
}

// Datos del día que está "n" días después de hoy. Se calcula en UTC para que sumar días
// nunca falle el día que se cambia la hora.
function diaDentroDe(hoy, n) {
  const f = new Date(Date.UTC(hoy.anio, hoy.mes - 1, hoy.dia + n));
  return {
    clave: f.toISOString().slice(0, 10),
    diaSemana: f.getUTCDay(),
    dia: f.getUTCDate(),
    mes: f.getUTCMonth(),
  };
}

function abreEseDia(d) {
  return DIAS_ABIERTO.includes(d.diaSemana) && !(d.clave in CIERRES_ESPECIALES);
}

// Cuándo vuelve a abrir: "hoy", "mañana", "el lunes" o "el 9 de diciembre".
function proximaApertura(ahora) {
  for (let n = 0; n <= 21; n++) {
    const d = diaDentroDe(ahora, n);
    if (n === 0 && ahora.minutos >= APERTURA) continue;
    if (!abreEseDia(d)) continue;
    if (n === 0) return "hoy";
    if (n === 1) return "mañana";
    if (n < 7) return "el " + NOMBRES_DIA[d.diaSemana];
    return "el " + d.dia + " de " + NOMBRES_MES[d.mes];
  }
  return null;
}

// Posición (de 0 a 1) de una hora dentro de la jornada: 0 = apertura, 1 = cierre.
function posicion(minutos) {
  return (minutos - APERTURA) / (CIERRE - APERTURA);
}

// Rellena una capa de la barra de la jornada con las franjas.
function rellenarCapa(capa) {
  capa.style.gridTemplateColumns = FRANJAS.map((f) => "minmax(0, " + (f.hasta - f.desde) + "fr)").join(" ");
  FRANJAS.forEach((f) => {
    const tramo = document.createElement("div");
    tramo.className = "tramo";
    const nombre = document.createElement("span");
    nombre.textContent = f.nombre;
    tramo.appendChild(nombre);
    capa.appendChild(tramo);
  });
}

// Oculta el nombre de las franjas en las que no cabe, en vez de verlo cortado a medias.
function ajustarEtiquetas(clara, oscura) {
  const claras = clara.querySelectorAll(".tramo");
  const oscuras = oscura.querySelectorAll(".tramo");
  claras.forEach((tramo, i) => {
    const relleno = parseFloat(getComputedStyle(tramo).paddingLeft) * 2;
    const cabe = tramo.querySelector("span").offsetWidth <= tramo.clientWidth - relleno;
    tramo.classList.toggle("sin-sitio", !cabe);
    oscuras[i].classList.toggle("sin-sitio", !cabe);
  });
}

function pintarHorario() {
  escribir(document.getElementById("hora-apertura"), formatoHora(APERTURA));
  escribir(document.getElementById("hora-cierre"), formatoHora(CIERRE));
  [capaClara, capaOscura].forEach(rellenarCapa);
  FRANJAS.slice(1).forEach((f) => {
    const etiqueta = document.createElement("span");
    etiqueta.className = "hora-intermedia";
    etiqueta.style.left = posicion(f.desde) * 100 + "%";
    etiqueta.textContent = formatoHora(f.desde);
    document.getElementById("horas").appendChild(etiqueta);
  });
}

// ---------- Función principal: actualiza todo lo que depende de la hora ----------
function actualizar() {
  const ahora = ahoraEnSalamanca();
  const hoy = diaDentroDe(ahora, 0);
  const minutos = ahora.minutos;
  const motivo = CIERRES_ESPECIALES[hoy.clave];
  const abierto = abreEseDia(hoy) && minutos >= APERTURA && minutos < CIERRE;
  const franja = abierto ? FRANJAS.find((f) => minutos >= f.desde && minutos < f.hasta) || null : null;

  document.body.classList.toggle("esta-abierto", abierto);
  document.body.classList.toggle("esta-cerrado", !abierto);

  let textoEstado, detalle;
  if (abierto) {
    textoEstado = "Abierto ahora";
    const quedan = CIERRE - minutos;
    const cierre = quedan <= 30
      ? "Cerramos en " + textoMinutos(quedan) + "."
      : "Cerramos a las " + formatoHora(CIERRE) + ".";
    detalle = cierre + (franja ? " Ahora es " + franja.frase + "." : "");
  } else {
    textoEstado = abreEseDia(hoy) ? "Cerrado ahora" : "Cerrado hoy";
    detalle = motivo ? "Hoy cerramos por " + motivo + ". " : "";
    const cuando = proximaApertura(ahora);
    if (cuando === "hoy" && APERTURA - minutos <= 60) {
      detalle += "Abrimos en " + textoMinutos(APERTURA - minutos) + ".";
    } else if (cuando) {
      detalle += "Abrimos " + cuando + " a las " + formatoHora(APERTURA) + ".";
    } else {
      detalle += "Llámanos para saber cuándo volvemos a abrir.";
    }
  }
  estadosTexto.forEach((e) => escribir(e, textoEstado));
  estadosDetalle.forEach((e) => escribir(e, detalle));

  // ----- Tabla de horario: horas de cada día y fila de hoy en negrita -----
  document.querySelectorAll("[data-dia]").forEach((fila) => {
    const dia = Number(fila.dataset.dia);
    const esHoy = dia === hoy.diaSemana;
    fila.classList.toggle("es-hoy", esHoy);
    let texto = DIAS_ABIERTO.includes(dia) ? formatoHora(APERTURA) + "–" + formatoHora(CIERRE) : "Cerrado";
    if (esHoy && motivo) texto = "Cerrado (" + motivo + ")";
    escribir(fila.querySelector("td"), texto);
  });

  // ----- Barra de la versión sin animación: raya de "ahora" y lo que queda hasta el cierre -----
  marca.hidden = !abierto;
  capaOscura.hidden = !abierto;
  let descripcion = "Horario de " + formatoHora(APERTURA) + " a " + formatoHora(CIERRE) + ". Ahora está cerrado.";
  if (abierto) {
    const p = posicion(minutos);
    barra.style.setProperty("--p", p);
    marca.dataset.hora = formatoHora(minutos);
    descripcion = "Abierto de " + formatoHora(APERTURA) + " a " + formatoHora(CIERRE) + ". Ahora son las "
      + formatoHora(minutos) + (franja ? ", " + franja.frase : "") + ".";
  }
  if (barra.getAttribute("aria-label") !== descripcion) barra.setAttribute("aria-label", descripcion);
}

// ---------- Mapa: se carga al pulsar el botón ----------
document.getElementById("cargar-mapa").addEventListener("click", () => {
  const iframe = document.createElement("iframe");
  iframe.className = "mapa";
  iframe.title = "Mapa con la ubicación de Pintarolo";
  iframe.src = URL_MAPA;
  iframe.referrerPolicy = "no-referrer-when-downgrade";
  document.getElementById("mapa").replaceWith(iframe);
  iframe.focus();  // el botón ha desaparecido: movemos el foco al mapa para no "perder" a quien usa teclado
});

// ---------- Arranque ----------
pintarHorario();
ajustarEtiquetas(capaClara, capaOscura);
actualizar();

// Actualizamos justo al empezar cada minuto.
function programarSiguiente() {
  const hastaElMinuto = 60000 - (Date.now() % 60000);
  setTimeout(() => {
    actualizar();
    programarSiguiente();
  }, hastaElMinuto + 100);
}
programarSiguiente();

// Si el móvil estaba bloqueado, el navegador congela los temporizadores: al volver, actualizamos en el acto.
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) actualizar();
});

function ajustarTodo() {
  ajustarEtiquetas(capaClara, capaOscura);
}
if (document.fonts) {
  document.fonts.ready.then(ajustarTodo);
  document.fonts.addEventListener("loadingdone", ajustarTodo);
}
window.addEventListener("resize", ajustarTodo);
