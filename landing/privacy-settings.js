/* Daftar – Knopf „Paramètres de confidentialité“ / „إعدادات الخصوصية“ in der Fußzeile der beiden Startseiten (/ und /ar/),
   den einzigen Seiten mit Google AdSense. Vergisst die gespeicherte Werbe-Einwilligung (Cookies FCCDCF und FCNEC von
   Googles Einwilligungsfenster, auf dem Host und allen Elterndomains) und lädt neu: Das Einwilligungsfenster erscheint
   wie beim ersten Besuch, so lässt sich die Einwilligung jederzeit ändern oder widerrufen. Wie bei Briefklar;
   googlefc.showRevocationMessage() war nicht zuverlässig. */
(function () {
  "use strict";

  var CONSENT_COOKIES = ["FCCDCF", "FCNEC"];
  var button = document.querySelector("[data-privacy-settings]");
  if (!button) return;

  button.addEventListener("click", function () {
    var parts = location.hostname.split(".");
    var domains = [""];
    for (var k = 0; k < parts.length - 1; k++) domains.push("; domain=." + parts.slice(k).join("."));
    CONSENT_COOKIES.forEach(function (name) {
      domains.forEach(function (domain) {
        document.cookie = name + "=; Max-Age=0; path=/" + domain;
      });
    });
    location.reload();
  });
})();
