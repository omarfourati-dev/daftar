// E2E-Tests der Verkaufswebseite und der Rechtstexte (landing/).
// Läuft gegen einen Server, der landing/ ausliefert: E2E_BASE_URL (Standard http://localhost:18083).
// Das Backend wird für das Pilot-Formular mit page.route gemockt.
import { test, expect, type Page, type Route } from "@playwright/test";

const BASE = (process.env.E2E_BASE_URL ?? "http://localhost:18083").replace(/\/$/, "");
const BASE_ORIGIN = new URL(BASE).origin;
const SITE = "https://daftar.omarfourati.de";
const API = "**/api/public/pilot-requests";

type PageSpec = {
  path: string;
  lang: "fr" | "ar" | "de";
  dir: "ltr" | "rtl";
  hreflang: Record<string, string>;
  switchTo: string; // Ziel des Sprachwechsels in der Kopfzeile
};

const HOME_ALT = { fr: "/", ar: "/ar/", "x-default": "/" };
const PRIVACY_ALT = { fr: "/confidentialite/", ar: "/ar/confidentialite/", de: "/datenschutz/", "x-default": "/confidentialite/" };

const PAGES: PageSpec[] = [
  { path: "/", lang: "fr", dir: "ltr", hreflang: HOME_ALT, switchTo: "/ar/" },
  { path: "/ar/", lang: "ar", dir: "rtl", hreflang: HOME_ALT, switchTo: "/" },
  { path: "/mentions-legales/", lang: "fr", dir: "ltr", hreflang: { fr: "/mentions-legales/", "x-default": "/mentions-legales/" }, switchTo: "/ar/" },
  { path: "/confidentialite/", lang: "fr", dir: "ltr", hreflang: PRIVACY_ALT, switchTo: "/ar/confidentialite/" },
  { path: "/ar/confidentialite/", lang: "ar", dir: "rtl", hreflang: PRIVACY_ALT, switchTo: "/confidentialite/" },
  { path: "/datenschutz/", lang: "de", dir: "ltr", hreflang: PRIVACY_ALT, switchTo: "/confidentialite/" },
  { path: "/contrat-sous-traitance/", lang: "fr", dir: "ltr", hreflang: { fr: "/contrat-sous-traitance/", "x-default": "/contrat-sous-traitance/" }, switchTo: "/ar/" },
];

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  mobile: { width: 390, height: 844 },
};

/** Sammelt Konsolenfehler (inkl. CSP-Verstöße), Skriptfehler und Requests an fremde Hosts. */
function watch(page: Page) {
  const errors: string[] = [];
  const foreign: string[] = [];
  page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
  page.on("pageerror", (err) => errors.push(err.message));
  page.on("request", (req) => {
    const url = new URL(req.url());
    if ((url.protocol === "http:" || url.protocol === "https:") && url.origin !== BASE_ORIGIN) foreign.push(req.url());
  });
  return { errors, foreign };
}

async function scrollThrough(page: Page) {
  // Lädt lazy-Bilder und alles, was erst beim Scrollen angefragt wird.
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += 600) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 30));
    }
    window.scrollTo(0, 0);
  });
}

for (const spec of PAGES) {
  test.describe(`Seite ${spec.path}`, () => {
    test("lädt mit 200 und hat lang/dir, Titel, Beschreibung, Canonical, hreflang, OG- und Twitter-Tags", async ({ page }) => {
      const response = await page.goto(BASE + spec.path);
      expect(response?.status()).toBe(200);

      const html = page.locator("html");
      await expect(html).toHaveAttribute("lang", spec.lang);
      await expect(html).toHaveAttribute("dir", spec.dir);
      await expect(page).toHaveTitle(/Daftar|دفتر/);
      expect((await page.locator('meta[name="description"]').getAttribute("content"))?.length ?? 0).toBeGreaterThan(40);

      const canonical = SITE + spec.path;
      await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", canonical);

      const alternates = await page.locator('link[rel="alternate"][hreflang]').evaluateAll((links) =>
        Object.fromEntries(links.map((l) => [l.getAttribute("hreflang"), l.getAttribute("href")])),
      );
      expect(alternates).toEqual(Object.fromEntries(Object.entries(spec.hreflang).map(([k, v]) => [k, SITE + v])));

      const meta = (sel: string) => page.locator(sel).getAttribute("content");
      expect(await meta('meta[property="og:url"]')).toBe(canonical);
      expect(await meta('meta[property="og:type"]')).toBe("website");
      expect(await meta('meta[property="og:image"]')).toBe(`${SITE}/og-image.png`);
      expect(await meta('meta[property="og:image:width"]')).toBe("1200");
      expect(await meta('meta[property="og:image:height"]')).toBe("630");
      expect((await meta('meta[property="og:title"]'))?.length ?? 0).toBeGreaterThan(5);
      expect((await meta('meta[property="og:description"]'))?.length ?? 0).toBeGreaterThan(20);
      expect(await meta('meta[name="twitter:card"]')).toBe("summary_large_image");
    });

    for (const [name, viewport] of Object.entries(VIEWPORTS)) {
      test(`${name}: keine Konsolenfehler, keine Requests an fremde Hosts`, async ({ page }) => {
        await page.setViewportSize(viewport);
        const seen = watch(page);
        await page.goto(BASE + spec.path, { waitUntil: "networkidle" });
        await scrollThrough(page);
        await page.waitForLoadState("networkidle");
        expect(seen.errors).toEqual([]);
        expect(seen.foreign).toEqual([]);
      });
    }

    test("keine horizontale Scrollleiste bei 360 und 390 px", async ({ page }) => {
      for (const width of [360, 390]) {
        await page.setViewportSize({ width, height: 800 });
        await page.goto(BASE + spec.path);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        expect(overflow, `Breite ${width}px`).toBeLessThanOrEqual(0);
      }
    });

    test("alle internen Links, Bilder und eingebundenen Dateien sind erreichbar", async ({ page, request }) => {
      await page.goto(BASE + spec.path);
      const refs = await page.evaluate(() => {
        const hrefs = [...document.querySelectorAll("a[href]")].map((a) => (a as HTMLAnchorElement).href);
        const assets = [
          ...[...document.querySelectorAll("img[src]")].map((i) => (i as HTMLImageElement).src),
          ...[...document.querySelectorAll("link[href]")].map((l) => (l as HTMLLinkElement).href),
          ...[...document.querySelectorAll("script[src]")].map((s) => (s as HTMLScriptElement).src),
        ];
        return { hrefs, assets };
      });
      const sameOrigin = (u: string) => u.startsWith(BASE_ORIGIN);
      const pageUrl = page.url().split("#")[0];

      // Anker auf derselben Seite müssen ein Ziel haben.
      for (const href of refs.hrefs.filter((h) => sameOrigin(h) && h.split("#")[0] === pageUrl && h.includes("#"))) {
        const id = decodeURIComponent(href.split("#")[1]);
        expect(await page.locator(`[id="${id}"]`).count(), `Anker #${id}`).toBe(1);
      }
      const targets = [...new Set([...refs.hrefs, ...refs.assets].filter(sameOrigin).map((u) => u.split("#")[0]))];
      expect(targets.length).toBeGreaterThan(3);
      for (const url of targets) {
        const res = await request.get(url, { maxRedirects: 0 });
        expect(res.status(), url).toBe(200);
      }
      // Jedes Bild hat einen Alternativtext (leer nur bei Schmuckbildern).
      expect(await page.locator("img:not([alt])").count()).toBe(0);
    });

    test("Sprachwechsel in der Kopfzeile führt zur anderen Sprache", async ({ page }) => {
      await page.goto(BASE + spec.path);
      const link = page.locator(".site-header .lang-switch");
      await expect(link).toHaveCount(1);
      await link.click();
      await expect(page).toHaveURL(BASE + spec.switchTo);
      const target = PAGES.find((p) => p.path === spec.switchTo)!;
      await expect(page.locator("html")).toHaveAttribute("lang", target.lang);
      expect(target.lang).not.toBe(spec.lang);
    });

    test("Grundstruktur: Skip-Link zum Inhalt, genau eine h1, main", async ({ page }) => {
      await page.goto(BASE + spec.path);
      await expect(page.locator("h1")).toHaveCount(1);
      await page.keyboard.press("Tab");
      const skip = page.locator(".skip-link");
      await expect(skip).toBeFocused();
      const target = await skip.getAttribute("href");
      await expect(page.locator(`main${target}`)).toHaveCount(1);
    });
  });
}

test.describe("Verkaufsseite", () => {
  test("FR: alle „Essayer la démo“-Knöpfe führen zu /app/demo, „Se connecter“ zu /connexion", async ({ page }) => {
    await page.goto(BASE + "/");
    const demo = page.getByRole("link", { name: "Essayer la démo" });
    expect(await demo.count()).toBeGreaterThanOrEqual(2);
    for (const href of await demo.evaluateAll((els) => els.map((e) => e.getAttribute("href")))) expect(href).toBe("/app/demo");
    await expect(page.locator(".site-header").getByRole("link", { name: "Se connecter" })).toHaveAttribute("href", "/connexion");
    await expect(page.locator(".hero").getByRole("link", { name: "Essayer la démo" })).toBeVisible();
  });

  test("AR: Demo-Knöpfe führen zu /app/demo mit arabischer Sprache, Anmelden zu /connexion", async ({ page }) => {
    await page.goto(BASE + "/ar/");
    const demo = page.getByRole("link", { name: "جرّبوا دفتر الآن" });
    expect(await demo.count()).toBeGreaterThanOrEqual(2);
    for (const href of await demo.evaluateAll((els) => els.map((e) => e.getAttribute("href")))) expect(href).toBe("/app/demo?lang=ar");
    await expect(page.locator(".site-header").getByRole("link", { name: "تسجيل الدخول" })).toHaveAttribute("href", "/connexion?lang=ar");
  });

  for (const path of ["/", "/ar/"]) {
    test(`${path}: JSON-LD ist gültiges SoftwareApplication-Schema mit kostenloser Pilotphase`, async ({ page }) => {
      await page.goto(BASE + path);
      const raw = await page.locator('script[type="application/ld+json"]').textContent();
      const data = JSON.parse(raw ?? "");
      expect(data["@type"]).toBe("SoftwareApplication");
      expect(data.name).toBe("Daftar");
      expect(data.offers.price).toBe("0");
      expect(data.offers.priceCurrency).toBe("TND");
    });
  }

  test("AR: Layout ist gespiegelt (Heftrand und Bildspalte rechts bzw. links)", async ({ page }) => {
    await page.setViewportSize(VIEWPORTS.desktop);
    await page.goto(BASE + "/ar/");
    const textBox = await page.locator(".hero h1").boundingBox();
    const visualBox = await page.locator(".hero-visual").boundingBox();
    expect(textBox && visualBox && textBox.x > visualBox.x).toBeTruthy();
  });
});

test.describe("Pilot-Formular", () => {
  async function mockApi(page: Page, respond: (route: Route) => Promise<void>) {
    const calls: { method: string; contentType: string | undefined; body: unknown }[] = [];
    await page.route(API, async (route) => {
      const req = route.request();
      calls.push({ method: req.method(), contentType: req.headers()["content-type"], body: req.postDataJSON() });
      await respond(route);
    });
    return calls;
  }
  const accepted = (route: Route) => route.fulfill({ status: 202 });
  const problem = (status: number, title: string) => (route: Route) =>
    route.fulfill({ status, contentType: "application/problem+json", body: JSON.stringify({ type: "about:blank", title, status, detail: title }) });

  async function fillValid(page: Page) {
    await page.getByLabel("Nom et prénom").fill("Amira Ben Salem");
    await page.getByLabel("Cabinet", { exact: true }).fill("Cabinet dentaire Les Jasmins");
    await page.getByLabel("Ville").fill("Sousse");
    await page.getByLabel("Téléphone").fill("+216 00 000 123");
  }

  test("leeres Absenden markiert die Pflichtfelder, fokussiert das erste und sendet nichts", async ({ page }) => {
    const calls = await mockApi(page, accepted);
    await page.goto(BASE + "/#pilote");
    await page.getByRole("button", { name: "Envoyer la demande" }).click();
    const invalid = page.locator('#pilot-form [aria-invalid="true"]');
    await expect(invalid).toHaveCount(4);
    expect(await invalid.evaluateAll((els) => els.map((e) => e.getAttribute("name")))).toEqual(["name", "practice", "city", "phone"]);
    await expect(page.getByLabel("Nom et prénom")).toBeFocused();
    // Die Fehlermeldung ist dem Feld zugeordnet (aria-describedby) und sichtbar.
    await expect(page.getByLabel("Nom et prénom")).toHaveAccessibleDescription(/obligatoire/);
    expect(calls).toHaveLength(0);
  });

  const phones: [string, boolean][] = [
    ["00 000 123", true],
    ["+216 00 000 123", true],
    ["0021600000123", true],
    ["+33 6 00 00 00 00", true],
    ["123", false],
    ["+216 123", false],
    ["abcdefgh", false],
    ["00 000 12", false],
  ];
  for (const [phone, ok] of phones) {
    test(`Telefon „${phone}“ wird ${ok ? "angenommen" : "abgelehnt"}`, async ({ page }) => {
      const calls = await mockApi(page, accepted);
      await page.goto(BASE + "/#pilote");
      await fillValid(page);
      await page.getByLabel("Téléphone").fill(phone);
      await page.getByRole("button", { name: "Envoyer la demande" }).click();
      if (ok) {
        await expect(page.getByRole("heading", { name: "Demande envoyée" })).toBeVisible();
        expect(calls).toHaveLength(1);
      } else {
        await expect(page.getByLabel("Téléphone")).toHaveAttribute("aria-invalid", "true");
        expect(calls).toHaveLength(0);
      }
    });
  }

  test("ungültige E-Mail wird abgelehnt, obwohl das Feld freiwillig ist", async ({ page }) => {
    const calls = await mockApi(page, accepted);
    await page.goto(BASE + "/#pilote");
    await fillValid(page);
    await page.getByLabel("E-mail").fill("pas-une-adresse");
    await page.getByRole("button", { name: "Envoyer la demande" }).click();
    await expect(page.getByLabel("E-mail")).toHaveAttribute("aria-invalid", "true");
    expect(calls).toHaveLength(0);
  });

  test("zu lange Nachricht (> 2000 Zeichen) wird abgelehnt", async ({ page }) => {
    const calls = await mockApi(page, accepted);
    await page.goto(BASE + "/#pilote");
    await fillValid(page);
    // maxlength verhindert das Tippen; per Skript gesetzte Werte (z. B. Einfügen über Erweiterungen) werden trotzdem geprüft.
    await page.getByLabel("Message").evaluate((el) => { (el as HTMLTextAreaElement).value = "x".repeat(2001); });
    await page.getByRole("button", { name: "Envoyer la demande" }).click();
    await expect(page.getByLabel("Message")).toHaveAttribute("aria-invalid", "true");
    expect(calls).toHaveLength(0);
  });

  test("Erfolg (202): sendet das JSON laut API inkl. Sprache und Honeypot und zeigt die Bestätigung", async ({ page }) => {
    const calls = await mockApi(page, accepted);
    await page.goto(BASE + "/#pilote");
    await fillValid(page);
    await page.getByLabel("E-mail").fill("amira@example.com");
    await page.getByLabel("Message").fill("Deux praticiens, une assistante.");
    await page.getByRole("button", { name: "Envoyer la demande" }).click();

    const success = page.locator("#pilot-success");
    await expect(success).toBeVisible();
    await expect(success).toBeFocused();
    await expect(success.getByRole("heading", { name: "Demande envoyée" })).toBeVisible();
    await expect(page.locator("#pilot-form")).toBeHidden();

    expect(calls).toHaveLength(1);
    expect(calls[0].method).toBe("POST");
    expect(calls[0].contentType).toContain("application/json");
    expect(calls[0].body).toEqual({
      name: "Amira Ben Salem",
      practice: "Cabinet dentaire Les Jasmins",
      city: "Sousse",
      phone: "+216 00 000 123",
      email: "amira@example.com",
      message: "Deux praticiens, une assistante.",
      lang: "fr",
      website: "",
    });
  });

  test("leere freiwillige Felder werden nicht mitgeschickt", async ({ page }) => {
    const calls = await mockApi(page, accepted);
    await page.goto(BASE + "/#pilote");
    await fillValid(page);
    await page.getByRole("button", { name: "Envoyer la demande" }).click();
    await expect(page.locator("#pilot-success")).toBeVisible();
    expect(calls[0].body).toEqual({
      name: "Amira Ben Salem",
      practice: "Cabinet dentaire Les Jasmins",
      city: "Sousse",
      phone: "+216 00 000 123",
      lang: "fr",
      website: "",
    });
  });

  test("Honeypot ist für Menschen unsichtbar und nicht fokussierbar, ein Bot-Wert wird an die API weitergegeben", async ({ page }) => {
    const calls = await mockApi(page, accepted);
    await page.goto(BASE + "/#pilote");
    const hp = page.locator('#pilot-form input[name="website"]');
    await expect(hp).toHaveAttribute("tabindex", "-1");
    const box = await hp.boundingBox();
    expect(box === null || box.x + box.width <= 0).toBeTruthy();
    await fillValid(page);
    await hp.evaluate((el) => { (el as HTMLInputElement).value = "https://spam.example"; });
    await page.getByRole("button", { name: "Envoyer la demande" }).click();
    await expect(page.locator("#pilot-success")).toBeVisible();
    expect((calls[0].body as { website: string }).website).toBe("https://spam.example");
  });

  test("während des Sendens ist der Knopf gesperrt (kein doppeltes Absenden)", async ({ page }) => {
    let release!: () => void;
    const gate = new Promise<void>((r) => { release = r; });
    const calls = await mockApi(page, async (route) => { await gate; await route.fulfill({ status: 202 }); });
    await page.goto(BASE + "/#pilote");
    await fillValid(page);
    const button = page.getByRole("button", { name: "Envoyer la demande" });
    await button.click();
    await expect(button).toBeDisabled();
    release();
    await expect(page.locator("#pilot-success")).toBeVisible();
    expect(calls).toHaveLength(1);
  });

  test("429: Hinweis „zu viele Anfragen“, Formular bleibt nutzbar", async ({ page }) => {
    await mockApi(page, problem(429, "Too Many Requests"));
    await page.goto(BASE + "/#pilote");
    await fillValid(page);
    const button = page.getByRole("button", { name: "Envoyer la demande" });
    await button.click();
    await expect(page.locator(".form-status")).toContainText("Trop de demandes");
    await expect(button).toBeEnabled();
    await expect(page.locator("#pilot-form")).toBeVisible();
    await expect(page.locator("#pilot-success")).toBeHidden();
  });

  test("Serverfehler (500) und Netzwerkfehler zeigen einen allgemeinen Fehler mit Kontaktadresse", async ({ page }) => {
    let fail = true;
    await page.route(API, (route) => (fail ? route.fulfill({ status: 500 }) : route.abort("failed")));
    await page.goto(BASE + "/#pilote");
    await fillValid(page);
    const status = page.locator(".form-status");
    await page.getByRole("button", { name: "Envoyer la demande" }).click();
    await expect(status).toContainText("n'a pas pu être envoyée");
    await expect(status).toContainText("info@omarfourati.de");
    await expect(status).not.toContainText("Trop de demandes");
    fail = false;
    await status.evaluate((el) => { el.textContent = ""; });
    await page.getByRole("button", { name: "Envoyer la demande" }).click();
    await expect(status).toContainText("n'a pas pu être envoyée");
  });

  test("AR: sendet lang=ar und zeigt Meldungen auf Arabisch", async ({ page }) => {
    const calls = await mockApi(page, problem(429, "Too Many Requests"));
    await page.goto(BASE + "/ar/#pilote");
    const button = page.locator('#pilot-form button[type="submit"]');
    await button.click();
    await expect(page.locator('#pilot-form [name="name"]')).toHaveAccessibleDescription(/إجبارية/);
    await page.locator('#pilot-form [name="name"]').fill("أميرة بن سالم");
    await page.locator('#pilot-form [name="practice"]').fill("عيادة الياسمين");
    await page.locator('#pilot-form [name="city"]').fill("سوسة");
    await page.locator('#pilot-form [name="phone"]').fill("00 000 123");
    await button.click();
    await expect(page.locator(".form-status")).toContainText("عدد كبير من الطلبات");
    expect(calls).toHaveLength(1);
    expect((calls[0].body as { lang: string }).lang).toBe("ar");
  });

  test("ohne JavaScript: Hinweis mit mailto statt Formular", async ({ browser }) => {
    const context = await browser.newContext({ javaScriptEnabled: false });
    const page = await context.newPage();
    for (const path of ["/", "/ar/"]) {
      await page.goto(BASE + path + "#pilote");
      const note = page.locator("[data-nojs]");
      await expect(note).toBeVisible();
      await expect(note.locator('a[href^="mailto:info@omarfourati.de"]')).toBeVisible();
      await expect(page.locator("#pilot-form")).toBeHidden();
    }
    await context.close();
  });

  test("mit JavaScript: Formular sichtbar, mailto-Hinweis ausgeblendet", async ({ page }) => {
    await page.goto(BASE + "/#pilote");
    await expect(page.locator("#pilot-form")).toBeVisible();
    await expect(page.locator("[data-nojs]")).toBeHidden();
  });
});

test.describe("Dateien für Suchmaschinen und Vorschauen", () => {
  test("robots.txt verweist auf die Sitemap und sperrt die App", async ({ request }) => {
    const res = await request.get(BASE + "/robots.txt");
    expect(res.status()).toBe(200);
    const text = await res.text();
    expect(text).toContain(`Sitemap: ${SITE}/sitemap.xml`);
    expect(text).toMatch(/^Disallow: \/app\/$/m);
    expect(text).toMatch(/^Disallow: \/api\/$/m);
  });

  test("sitemap.xml ist gültiges XML und listet genau die indexierbaren Seiten FR und AR", async ({ page, request }) => {
    const res = await request.get(BASE + "/sitemap.xml");
    expect(res.status()).toBe(200);
    const xml = await res.text();
    await page.goto(BASE + "/");
    const locs = await page.evaluate((src) => {
      const doc = new DOMParser().parseFromString(src, "application/xml");
      if (doc.querySelector("parsererror")) return ["PARSE ERROR"];
      return [...doc.getElementsByTagNameNS("http://www.sitemaps.org/schemas/sitemap/0.9", "loc")].map((n) => n.textContent);
    }, xml);
    expect(locs.sort()).toEqual([`${SITE}/`, `${SITE}/ar/`]);
  });

  test("llms.txt ist erreichbar und nennt Daftar mit Links auf die Seiten", async ({ request }) => {
    const res = await request.get(BASE + "/llms.txt");
    expect(res.status()).toBe(200);
    const text = await res.text();
    expect(text.startsWith("# Daftar")).toBeTruthy();
    expect(text).toContain(`${SITE}/ar/`);
  });

  test("og-image.png ist ein PNG mit 1200 × 630 px", async ({ request }) => {
    const res = await request.get(BASE + "/og-image.png");
    expect(res.status()).toBe(200);
    const buf = await res.body();
    expect(buf.subarray(1, 4).toString("ascii")).toBe("PNG");
    expect(buf.readUInt32BE(16)).toBe(1200);
    expect(buf.readUInt32BE(20)).toBe(630);
  });

  test("App-Icon brand/icon.svg ist quadratisch und vollflächig (maskable-tauglich)", async ({ page }) => {
    await page.goto(BASE + "/");
    const result = await page.evaluate(async () => {
      const img = new Image();
      img.src = "/brand/icon.svg";
      await img.decode();
      const c = document.createElement("canvas");
      c.width = 96; c.height = 96;
      const ctx = c.getContext("2d")!;
      ctx.drawImage(img, 0, 0, 96, 96);
      const alpha = (x: number, y: number) => ctx.getImageData(x, y, 1, 1).data[3];
      return { w: img.naturalWidth, h: img.naturalHeight, corners: [alpha(0, 0), alpha(95, 0), alpha(0, 95), alpha(95, 95)] };
    });
    expect(result.w).toBe(result.h);
    // Die Ecken sind deckend: der Hintergrund füllt die ganze Fläche, das Motiv liegt im Sicherheitsbereich.
    expect(result.corners).toEqual([255, 255, 255, 255]);
  });
});
