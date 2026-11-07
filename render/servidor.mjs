// Servidor mínimo para ver la web en local: node servidor.mjs [puerto]
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const puerto = Number(process.env.PORT || process.argv[2] || 8321);
const tipos = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".webp": "image/webp", ".woff2": "font/woff2", ".png": "image/png" };
http.createServer((req, res) => {
  const ruta = decodeURIComponent(new URL(req.url, "http://x").pathname);
  const archivo = path.join(raiz, ruta.endsWith("/") ? ruta + "index.html" : ruta);
  if (!archivo.startsWith(raiz)) { res.writeHead(403); return res.end(); }
  fs.readFile(archivo, (err, datos) => {
    if (err) { res.writeHead(404); return res.end("no encontrado"); }
    res.writeHead(200, { "Content-Type": tipos[path.extname(archivo)] || "application/octet-stream", "Cache-Control": "no-cache" });
    res.end(datos);
  });
}).listen(puerto, "127.0.0.1", () => console.log("http://localhost:" + puerto));
