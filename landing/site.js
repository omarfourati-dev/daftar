/* Daftar – Formular „Accès pilote“ als progressive Verbesserung.
   Ohne JavaScript bleibt der Hinweis mit mailto: sichtbar. Setzt selbst keine Cookies und trackt nicht;
   einziger Request: POST /api/public/pilot-requests. */
(function () {
  "use strict";

  var form = document.getElementById("pilot-form");
  if (!form || !window.fetch) return;

  var lang = document.documentElement.lang === "ar" ? "ar" : "fr";
  var TEXT = {
    fr: {
      required: "Ce champ est obligatoire.",
      tooLong: "Ce texte est trop long ({max} caractères au maximum).",
      phone: "Indiquez un numéro à 8 chiffres, ou un numéro international commençant par +.",
      email: "Cette adresse e-mail n'est pas valide.",
      check: "Vérifiez les champs signalés.",
      sending: "Envoi en cours…",
      tooMany: "Trop de demandes ont été envoyées depuis cette connexion. Réessayez dans une heure ou écrivez à info@omarfourati.de.",
      rejected: "Certaines informations n'ont pas été acceptées. Vérifiez le formulaire et réessayez.",
      failed: "La demande n'a pas pu être envoyée. Réessayez plus tard ou écrivez à info@omarfourati.de."
    },
    ar: {
      required: "هذه الخانة إجبارية.",
      tooLong: "النص طويل جدًا (الحد الأقصى {max} حرفًا).",
      phone: "أدخلوا رقمًا من 8 أرقام، أو رقمًا دوليًا يبدأ بـ +.",
      email: "عنوان البريد الإلكتروني غير صحيح.",
      check: "يُرجى مراجعة الخانات المُشار إليها.",
      sending: "جارٍ الإرسال…",
      tooMany: "أُرسل عدد كبير من الطلبات من هذا الاتصال. أعيدوا المحاولة بعد ساعة أو اكتبوا إلى info@omarfourati.de.",
      rejected: "لم تُقبل بعض المعلومات. راجعوا الاستمارة وأعيدوا المحاولة.",
      failed: "تعذّر إرسال الطلب. أعيدوا المحاولة لاحقًا أو اكتبوا إلى info@omarfourati.de."
    }
  }[lang];

  // Telefon: 8 Ziffern (Tunesien), +216/00216 mit 8 Ziffern oder international mit +.
  function isPhone(value) {
    var compact = value.replace(/[\s.\-()\/]/g, "");
    return /^\d{8}$/.test(compact) || /^(\+|00)216\d{8}$/.test(compact) || /^\+\d{8,15}$/.test(compact);
  }
  function isEmail(value) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
  }

  var FIELDS = [
    { name: "name", required: true, max: 120 },
    { name: "practice", required: true, max: 120 },
    { name: "city", required: true, max: 120 },
    { name: "phone", required: true, max: 30, valid: isPhone, invalid: TEXT.phone },
    { name: "email", required: false, max: 254, valid: isEmail, invalid: TEXT.email },
    { name: "message", required: false, max: 2000 }
  ];

  var status = form.querySelector(".form-status");
  var submit = form.querySelector('button[type="submit"]');
  var success = document.getElementById("pilot-success");
  var note = document.querySelector("[data-nojs]");

  if (note) note.hidden = true;
  form.hidden = false;

  function input(name) {
    return form.elements.namedItem(name);
  }

  function showError(el, message) {
    var errorId = el.id + "-error";
    var error = document.getElementById(errorId);
    var describedBy = (el.getAttribute("aria-describedby") || "").split(/\s+/).filter(function (id) {
      return id && id !== errorId;
    });
    if (message) {
      if (!error) {
        error = document.createElement("span");
        error.id = errorId;
        error.className = "error";
        el.insertAdjacentElement("afterend", error);
      }
      error.textContent = message;
      el.setAttribute("aria-invalid", "true");
      describedBy.push(errorId);
    } else {
      if (error) error.remove();
      el.removeAttribute("aria-invalid");
    }
    if (describedBy.length) el.setAttribute("aria-describedby", describedBy.join(" "));
    else el.removeAttribute("aria-describedby");
  }

  function check(field) {
    var el = input(field.name);
    var value = el.value.trim();
    var message = "";
    if (!value) message = field.required ? TEXT.required : "";
    else if (value.length > field.max) message = TEXT.tooLong.replace("{max}", field.max);
    else if (field.valid && !field.valid(value)) message = field.invalid;
    showError(el, message);
    return !message;
  }

  function say(message, isError) {
    status.textContent = message;
    status.classList.toggle("is-error", Boolean(isError));
  }

  FIELDS.forEach(function (field) {
    var el = input(field.name);
    el.addEventListener("blur", function () {
      if (el.value.trim() || el.hasAttribute("aria-invalid")) check(field);
    });
    el.addEventListener("input", function () {
      if (el.hasAttribute("aria-invalid")) check(field);
    });
  });

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    if (submit.disabled) return;

    var firstInvalid = null;
    FIELDS.forEach(function (field) {
      if (!check(field) && !firstInvalid) firstInvalid = input(field.name);
    });
    if (firstInvalid) {
      say(TEXT.check, true);
      firstInvalid.focus();
      return;
    }

    var body = {
      name: input("name").value.trim(),
      practice: input("practice").value.trim(),
      city: input("city").value.trim(),
      phone: input("phone").value.trim()
    };
    var email = input("email").value.trim();
    var message = input("message").value.trim();
    if (email) body.email = email;
    if (message) body.message = message;
    body.lang = lang;
    body.website = input("website").value;

    submit.disabled = true;
    say(TEXT.sending, false);

    fetch("/api/public/pilot-requests", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
      credentials: "same-origin"
    })
      .then(function (response) {
        if (response.ok) {
          form.hidden = true;
          success.hidden = false;
          success.focus();
          return;
        }
        submit.disabled = false;
        if (response.status === 429) say(TEXT.tooMany, true);
        else if (response.status === 400 || response.status === 422) say(TEXT.rejected, true);
        else say(TEXT.failed, true);
      })
      .catch(function () {
        submit.disabled = false;
        say(TEXT.failed, true);
      });
  });
})();
