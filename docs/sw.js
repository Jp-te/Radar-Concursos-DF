// Service worker do Radar Concursos DF: permite abrir o app sem internet.
// Página e dados: tenta a rede primeiro e usa a cópia guardada se estiver offline.
var VERSAO = "radar-v3";
var BASE = ["./", "index.html", "manifest.webmanifest", "icon-192.png", "icon-512.png"];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(VERSAO).then(function (c) { return c.addAll(BASE); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (ks) {
      return Promise.all(ks.filter(function (k) { return k !== VERSAO; }).map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

function guardar(req, resp) {
  if (resp && (resp.ok || resp.type === "opaque")) {
    var copia = resp.clone();
    caches.open(VERSAO).then(function (c) { c.put(req, copia); });
  }
  return resp;
}

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;
  var url = new URL(req.url);
  var mesmaOrigem = url.origin === self.location.origin;
  var rede = req.mode === "navigate" || /dados\.json$|index\.html$/.test(url.pathname);

  if (mesmaOrigem && rede) {
    e.respondWith(
      fetch(req).then(function (r) { return guardar(req, r); }).catch(function () {
        return caches.match(req).then(function (c) { return c || caches.match("index.html"); });
      })
    );
    return;
  }
  // Ícones, fontes e demais arquivos: usa a cópia guardada e atualiza em segundo plano.
  if (mesmaOrigem || /fonts\.(googleapis|gstatic)\.com$/.test(url.hostname)) {
    e.respondWith(
      caches.match(req).then(function (c) {
        var busca = fetch(req).then(function (r) { return guardar(req, r); }).catch(function () { return c; });
        return c || busca;
      })
    );
  }
});
