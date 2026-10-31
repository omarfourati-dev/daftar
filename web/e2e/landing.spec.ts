// E2E-Tests der Verkaufswebseite und der Rechtstexte (landing/).
// Läuft gegen einen Server, der landing/ ausliefert: E2E_BASE_URL (Standard http://localhost:18083).
// Das Backend wird für das Pilot-Formular mit page.route gemockt.
// Google AdSense läuft nur auf / und /ar/. Die Google-Hosts werden in jedem Test per page.route blockiert
// (wie ein Werbeblocker): Die Tests hängen nicht vom Netz ab und laden nie echte Werbung.
import { test, expect, type Page, type Route } from "@playwright/test";

const BASE = (process.env.E2E_BASE_URL ?? "http://localhost:18083").replace(/\/$/, "");
const BASE_ORIGIN = new URL(BASE).origin;
const SITE = "https://daftar.omarfourati.de";
/** Die App hat einen eigenen Ursprung ohne Werbung (Fix-Liste 1): Links der Landing zeigen dorthin. */
const APP_SITE = "https://app.daftar.omarfourati.de";
/** App-Host des getesteten Servers (BASE_DOMAIN=localhost → app.localhost:<port>). Node auf Windows löst *.localhost
 * nicht auf → Requests aus Node gehen mit Host-Header an BASE; im Browser funktioniert APP_ORIGIN direkt. */
const APP_HOST = `app.${new URL(BASE).host}`;
const APP_ORIGIN = `${new URL(BASE).protocol}//${APP_HOST}`;
/** Pfade der App – auf der Hauptdomain nur noch eine 301 auf den App-Host. */
/** (`/rdv` ist die Seite des persönlichen Links `/rdv#<token>`, Fix-Liste 2 – `/rdv/<token>` gibt es nicht mehr.) */
const APP_PATHS = ["/app", "/app/demo", "/connexion", "/invitation", "/r/cabinet-test", "/rdv", "/salle/abc123", "/ticket/abc123"];
const API = "**/api/public/pilot-requests";

const ADSENSE_CLIENT = "ca-pub-4072840905222883";
const ADSENSE_LOADER = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${ADSENSE_CLIENT}`;
/** Die einzigen Seiten mit Werbung: die beiden Startseiten. */
const AD_PAGES = new Set(["/", "/ar/"]);
/** Hosts von AdSense und Googles Einwilligungsfenster (fundingchoicesmessages.google.com fällt unter google.com). */
const GOOGLE_AD_HOSTS = ["googlesyndication.com", "doubleclick.net", "google.com", "gstatic.com", "adtrafficquality.google"];
const isGoogleAdHost = (hostname: string) => GOOGLE_AD_HOSTS.some((h) => hostname === h || hostname.endsWith("." + h));
const isGoogleAdUrl = (url: string) => {
  try {
    return isGoogleAdHost(new URL(url).hostname);
  } catch {
    return false;
  }
};

/** Blockiert alle Google-Werbe-Hosts und merkt sich, was angefragt wurde. */
async function blockGoogleAds(page: Page) {
  const blocked: string[] = [];
  await page.route((url) => isGoogleAdHost(url.hostname), async (route) => {
    blocked.push(route.request().url());
    await route.abort("blockedbyclient");
  });
  return blocked;
}

test.beforeEach(async ({ page }) => {
  await blockGoogleAds(page);
});

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

/**
 * Sammelt Konsolenfehler (inkl. CSP-Verstöße), Skriptfehler und Requests an fremde Hosts.
 * Mit `ads` (nur / und /ar/) zählen Requests an Google-Werbe-Hosts nicht als fremd, und die Fehlermeldungen der im
 * Test blockierten Google-Requests werden ausgenommen. Jeder andere fremde Host bleibt ein Fehler.
 */
function watch(page: Page, { ads = false } = {}) {
  const errors: string[] = [];
  const foreign: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() !== "error") return;
    if (ads && isGoogleAdUrl(msg.location().url) && msg.text().includes("ERR_BLOCKED_BY_CLIENT")) return;
    errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(err.message));
  page.on("request", (req) => {
    const url = new URL(req.url());
    if (url.protocol !== "http:" && url.protocol !== "https:") return;
    if (url.origin === BASE_ORIGIN || url.origin === APP_ORIGIN || (ads && isGoogleAdHost(url.hostname))) return;
    foreign.push(req.url());
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
      const ads = AD_PAGES.has(spec.path);
      test(`${name}: keine Konsolenfehler, keine Requests an fremde Hosts${ads ? " außer Google-Werbung" : ""}`, async ({ page }) => {
        await page.setViewportSize(viewport);
        const seen = watch(page, { ads });
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
  test("FR: alle „Essayer la démo“-Knöpfe führen zu app.…/app/demo, „Se connecter“ zu app.…/connexion", async ({ page }) => {
    await page.goto(BASE + "/");
    const demo = page.getByRole("link", { name: "Essayer la démo" });
    expect(await demo.count()).toBeGreaterThanOrEqual(2);
    for (const href of await demo.evaluateAll((els) => els.map((e) => e.getAttribute("href")))) expect(href).toBe(`${APP_SITE}/app/demo`);
    await expect(page.locator(".site-header").getByRole("link", { name: "Se connecter" })).toHaveAttribute("href", `${APP_SITE}/connexion`);
    await expect(page.locator(".hero").getByRole("link", { name: "Essayer la démo" })).toBeVisible();
  });

  test("AR: Demo-Knöpfe führen zu app.…/app/demo mit arabischer Sprache, Anmelden zu app.…/connexion", async ({ page }) => {
    await page.goto(BASE + "/ar/");
    const demo = page.getByRole("link", { name: "جرّبوا دفتر الآن" });
    expect(await demo.count()).toBeGreaterThanOrEqual(2);
    for (const href of await demo.evaluateAll((els) => els.map((e) => e.getAttribute("href")))) expect(href).toBe(`${APP_SITE}/app/demo?lang=ar`);
    await expect(page.locator(".site-header").getByRole("link", { name: "تسجيل الدخول" })).toHaveAttribute("href", `${APP_SITE}/connexion?lang=ar`);
  });

  test("keine Seite verlinkt App-Pfade der Hauptdomain, App-Links zeigen auf app.daftar.omarfourati.de", async ({ page, request }) => {
    const appPath = /^\/(app|connexion|invitation|reinitialiser|r\/|rdv(?:[/#?]|$)|salle\/|ticket\/)/;
    for (const spec of PAGES) {
      await page.goto(BASE + spec.path);
      const hrefs = await page.locator("a[href]").evaluateAll((els) => els.map((e) => e.getAttribute("href") ?? ""));
      for (const href of hrefs) {
        expect(href, `${spec.path}: ${href}`).not.toMatch(appPath);
        expect(href, `${spec.path}: ${href}`).not.toContain(`${SITE}/app`);
        expect(href, `${spec.path}: ${href}`).not.toContain(`${SITE}/connexion`);
      }
      expect(hrefs.filter((h) => h.startsWith(APP_SITE + "/")).length, spec.path).toBeGreaterThanOrEqual(1);
    }
    const llms = await (await request.get(BASE + "/llms.txt")).text();
    expect(llms).toContain(`(${APP_SITE}/app/demo)`);
    expect(llms).not.toContain(`${SITE}/app/`);
  });

  for (const path of APP_PATHS) {
    test(`${path} auf der Hauptdomain: 301 auf den App-Host (mit Query)`, async ({ request }) => {
      const res = await request.get(BASE + path + "?lang=ar", { maxRedirects: 0 });
      expect(res.status()).toBe(301);
      expect(res.headers()["location"]).toBe(`${APP_ORIGIN}${path}?lang=ar`);
    });
  }

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

  for (const path of ["/", "/ar/"]) {
    test(`${path}: Installationsschritte bleiben ein Textfluss (Zitate zerreißen die Zeile nicht)`, async ({ page }) => {
      for (const viewport of Object.values(VIEWPORTS)) {
        await page.setViewportSize(viewport);
        await page.goto(BASE + path);
        const heights = await page.locator("#appareils .install li").evaluateAll((lis) => lis.map((li) => li.getBoundingClientRect().height));
        expect(heights.length).toBe(9);
        // Höchstens drei Textzeilen pro Schritt; ein zerrissener Schritt ist mehrere hundert Pixel hoch.
        for (const h of heights) expect(h, `${viewport.width}px`).toBeLessThan(100);
      }
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

// Google AdSense (Omar, 30.10.): nur auf den beiden Startseiten, mit Googles Einwilligungsfenster und einem Knopf zum
// Widerruf. App, Buchungs-, Ticket- und Wartezimmerseiten sowie die Rechtstexte bleiben ohne Werbung und ohne fremde Hosts.
test.describe("Werbung nur auf den beiden Startseiten", () => {
  const PRIVACY_BUTTON = { "/": "Paramètres de confidentialité", "/ar/": "إعدادات الخصوصية" } as Record<string, string>;
  const CONSENT_COOKIES = ["FCCDCF", "FCNEC"];

  for (const path of AD_PAGES) {
    test(`${path}: AdSense-Loader mit dem richtigen Client, gelockerte CSP, Knopf „${PRIVACY_BUTTON[path]}“`, async ({ page, request }) => {
      const blocked: string[] = [];
      page.on("requestfailed", (req) => { if (isGoogleAdUrl(req.url())) blocked.push(req.url()); });
      const response = await page.goto(BASE + path, { waitUntil: "networkidle" });
      const loader = page.locator(`head script[src="${ADSENSE_LOADER}"]`);
      await expect(loader).toHaveCount(1);
      await expect(loader).toHaveAttribute("async", "");
      await expect(loader).toHaveAttribute("crossorigin", "anonymous");
      await expect(page.locator('script[src*="adsbygoogle"]')).toHaveCount(1); // nur dieser eine Loader
      await expect(page.locator('head script[src="/privacy-settings.js"]')).toHaveAttribute("defer", "");
      expect(blocked).toContain(ADSENSE_LOADER); // der Browser hat ihn wirklich angefragt (im Test blockiert)

      const csp = response?.headers()["content-security-policy"] ?? "";
      expect(csp).toContain("script-src 'self' 'unsafe-inline' https:");
      expect(csp).toContain("frame-src https:");
      expect(csp).toContain("frame-ancestors 'none'");
      expect(csp).not.toContain("sha256-"); // ein Hash würde 'unsafe-inline' abschalten

      const button = page.locator(".site-footer").getByRole("button", { name: PRIVACY_BUTTON[path] });
      await expect(button).toBeVisible();
      await expect(button).toHaveAttribute("type", "button");
      expect((await request.get(BASE + "/privacy-settings.js")).status()).toBe(200);
    });

    test(`${path}: „${PRIVACY_BUTTON[path]}“ löscht die Einwilligungs-Cookies FCCDCF und FCNEC und lädt neu`, async ({ page, context }) => {
      await context.addCookies([
        ...CONSENT_COOKIES.map((name) => ({ name, value: "entscheidung", url: BASE })),
        { name: "anderes", value: "bleibt", url: BASE },
      ]);
      await page.goto(BASE + path);
      expect(await page.evaluate(() => document.cookie)).toContain("FCCDCF=entscheidung");
      await page.evaluate(() => { (window as unknown as { vorher: boolean }).vorher = true; });
      const reloaded = page.waitForEvent("load");
      await page.getByRole("button", { name: PRIVACY_BUTTON[path] }).click();
      await reloaded;
      expect(await page.evaluate(() => (window as unknown as { vorher?: boolean }).vorher)).toBeUndefined();
      const names = (await context.cookies(BASE)).map((c) => c.name);
      for (const name of CONSENT_COOKIES) expect(names).not.toContain(name);
      expect(names).toContain("anderes"); // nur die Einwilligung wird vergessen
    });

    test(`${path}: vergisst eine alte App-Anmeldung dieses Ursprungs (daftar.token/daftar.user), sonst nichts`, async ({ page }) => {
      // Security-Review M3: Früher lief die App samt Anmeldung auf der Hauptdomain – das Token läge hier neben AdSense.
      await page.goto(BASE + "/robots.txt"); // derselbe Ursprung, ohne Skripte
      await page.evaluate(() => {
        localStorage.setItem("daftar.token", "altes-token");
        localStorage.setItem("daftar.user", "{}");
        localStorage.setItem("anderes", "bleibt");
      });
      await page.goto(BASE + path, { waitUntil: "load" });
      expect(await page.evaluate(() => [localStorage.getItem("daftar.token"), localStorage.getItem("daftar.user"), localStorage.getItem("anderes")]))
        .toEqual([null, null, "bleibt"]);
    });
  }

  const WITHOUT_ADS = [
    ...PAGES.map((p) => ({ path: p.path, host: new URL(BASE).host })).filter((p) => !AD_PAGES.has(p.path)),
    ...APP_PATHS.map((path) => ({ path, host: APP_HOST })), // die App auf ihrem eigenen Host
  ];
  for (const { path, host } of WITHOUT_ADS) {
    test(`${host}${path}: kein Google-Code, kein Datenschutz-Knopf, strenge CSP ohne fremde Hosts`, async ({ request }) => {
      const res = await request.get(BASE + path, { headers: { host } });
      expect(res.status()).toBe(200);
      const html = await res.text();
      expect(html).not.toMatch(/googlesyndication|adsbygoogle|ca-pub-|privacy-settings/);
      const csp = res.headers()["content-security-policy"] ?? "";
      expect(csp).toContain("default-src 'self'");
      expect(csp).not.toContain("http");
      expect(csp).not.toContain("unsafe-inline' https");
    });
  }

  test("/connexion (App-Host) lädt im Browser nichts von Google", async ({ page }) => {
    const seen = watch(page);
    await page.goto(APP_ORIGIN + "/connexion", { waitUntil: "networkidle" });
    await expect(page.locator("form")).toHaveCount(1);
    expect(seen.foreign).toEqual([]);
  });

  const PRIVACY_PAGES = [
    {
      path: "/confidentialite/", button: "Paramètres de confidentialité", old: /Daftar n'utilise aucun cookie|aucune ressource n'est chargée chez des tiers\./,
      // Fix-Liste 4: Googles Einwilligungsfenster nur für EWR, Vereinigtes Königreich und Schweiz
      region: [/Espace économique européen/, /Royaume-Uni/, /Suisse/, /En dehors de ces pays/],
    },
    {
      path: "/ar/confidentialite/", button: "إعدادات الخصوصية", old: /لا يستعمل دفتر أي ملف تعريف ارتباط: لا في موقع التعريف|ولا يُحمَّل أي شيء من أطراف أخرى\./,
      region: [/المنطقة الاقتصادية الأوروبية/, /المملكة المتحدة/, /سويسرا/, /خارج هذه البلدان/],
    },
    {
      path: "/datenschutz/", button: "Paramètres de confidentialité", old: /Daftar setzt keine Cookies – weder auf der Website|es wird nichts von Dritten geladen\./,
      region: [/Europäischen Wirtschaftsraum/, /Vereinigten Königreich/, /Schweiz/, /Außerhalb dieser Länder/],
    },
  ];
  for (const spec of PRIVACY_PAGES) {
    test(`${spec.path} erklärt die Werbung auf den Startseiten (Google, Einwilligung, Widerruf, USA)`, async ({ page }) => {
      await page.goto(BASE + spec.path);
      const section = page.locator("#publicite");
      await expect(section).toHaveCount(1);
      const text = await page.evaluate(() => {
        // Text vom Titel des Unterabschnitts bis zum nächsten Titel derselben oder einer höheren Ebene
        const start = document.getElementById("publicite")!;
        let all = start.textContent ?? "";
        for (let el = start.nextElementSibling; el && !/^H[23]$/.test(el.tagName); el = el.nextElementSibling) all += " " + el.textContent;
        return all.replace(/\s+/g, " ");
      });
      for (const fact of ["Google Ireland Limited", "Gordon House, Barrow Street, Dublin 4", "Data Privacy Framework", "TDDDG", "RGPD|DSGVO", spec.button]) {
        expect(text).toMatch(new RegExp(fact));
      }
      for (const href of ["https://policies.google.com/privacy", "https://policies.google.com/technologies/ads", "https://adssettings.google.com"]) {
        await expect(page.locator(`#publicite ~ * a[href^="${href}"]`).first()).toBeAttached();
      }
      await expect(page.locator("main")).not.toContainText(spec.old);
      await expect(page.locator(".summary")).toContainText(/AdSense/);
      for (const fact of spec.region) expect(text, String(fact)).toMatch(fact);
      for (const fact of spec.region.slice(0, 3)) await expect(page.locator(".summary"), String(fact)).toContainText(fact);
    });
  }

  for (const [path, old] of [["/", "Sans cookies ni traceurs."], ["/ar/", "دون ملفات تعريف الارتباط ودون تتبّع."]]) {
    test(`${path}: keine Behauptung mehr „ohne Cookies“ für die Seite selbst, die App bleibt ohne Werbung`, async ({ page }) => {
      await page.goto(BASE + path);
      await expect(page.locator(".site-footer")).not.toContainText(old);
      await expect(page.locator("#securite")).toContainText("Google");
    });
  }

  test("llms.txt und Muster-AVV unterscheiden App (ohne Werbung) und Startseiten (Google AdSense)", async ({ page, request }) => {
    const llms = await (await request.get(BASE + "/llms.txt")).text();
    expect(llms).not.toContain("aucun cookie ni traceur.");
    expect(llms).toContain("Google AdSense");
    await page.goto(BASE + "/contrat-sous-traitance/");
    await expect(page.locator("main")).toContainText("Google");
    await expect(page.locator("main")).toContainText("Les pages de l'application, y compris les pages de réservation");
  });
});

// Daftar richtet sich an alle Fachrichtungen (Spezifikation Abschnitt 12) und bietet Online-Buchung (Abschnitt 11).
const HOME = {
  fr: {
    path: "/",
    specialties: ["Médecins généralistes", "Dentistes", "Pédiatres", "Kinésithérapeutes", "Psychologues"],
    bookingUrl: "cabinet-ben-salah.daftar.omarfourati.de",
    img: "/img/",
    features: ["Plusieurs praticiens", "durée et prix", "pause", "congés", "même temps"],
    payment: "Flouci",
  },
  ar: {
    path: "/ar/",
    specialties: ["أطباء الطب العام", "أطباء الأسنان", "أطباء الأطفال", "أخصائيو العلاج الطبيعي", "الأخصائيون النفسيون"],
    bookingUrl: "cabinet-ben-salah.daftar.omarfourati.de",
    img: "/img/ar/",
    features: ["عدّة أطباء", "المدة والسعر", "استراحة", "العطل", "في الوقت نفسه"],
    payment: "Flouci",
  },
};

for (const [lang, home] of Object.entries(HOME)) {
  test.describe(`Alle Fachrichtungen und Online-Buchung (${lang})`, () => {
    test("Titel, Beschreibung, OG und JSON-LD sind nicht zahnarztspezifisch", async ({ page }) => {
      await page.goto(BASE + home.path);
      const texts = [
        await page.title(),
        await page.locator('meta[name="description"]').getAttribute("content"),
        await page.locator('meta[property="og:title"]').getAttribute("content"),
        await page.locator('meta[property="og:description"]').getAttribute("content"),
        JSON.parse((await page.locator('script[type="application/ld+json"]').textContent()) ?? "{}").description,
        await page.locator(".hero h1").textContent(),
        await page.locator(".hero .lead").textContent(),
      ].join(" | ");
      // Zahnärzte dürfen genannt werden, aber nicht als einzige Zielgruppe („cabinet dentaire“).
      expect(texts).not.toMatch(/cabinets? dentaires?|عيادات? الأسنان|عيادة طب الأسنان/i);
      expect(texts).toMatch(/médic|médecin|طبي|أطباء/i);
    });

    test("der Hero nennt mehrere Fachrichtungen, Zahnärzte sind eine davon", async ({ page }) => {
      await page.goto(BASE + home.path);
      const items = page.locator(".hero .specialties li");
      expect(await items.count()).toBeGreaterThanOrEqual(6);
      const list = (await items.allTextContents()).map((t) => t.trim());
      for (const s of home.specialties) expect(list).toContain(s);
    });

    test("eigener Abschnitt Online-Buchung mit Beispieladresse und Handy-Mockup, im Hero verlinkt", async ({ page }) => {
      await page.goto(BASE + home.path);
      const section = page.locator("section#reservation");
      await expect(section.locator("h2")).toBeVisible();
      await expect(section).toContainText(home.bookingUrl);
      const img = section.locator(`img[src="${home.img}screen-booking.png"]`);
      await expect(img).toHaveCount(1);
      await img.scrollIntoViewIfNeeded();
      await expect.poll(() => img.evaluate((i: HTMLImageElement) => i.naturalWidth)).toBeGreaterThan(0);
      await expect(page.locator('.hero a[href="#reservation"]')).toHaveCount(1);
      await expect(page.locator('.main-nav a[href="#reservation"]')).toHaveCount(1);
    });

    test("Funktionsliste nennt mehrere Behandler, Leistungen mit Dauer und Preis, Pause, Urlaub, keine Doppelbuchung", async ({ page }) => {
      await page.goto(BASE + home.path);
      const text = (await page.locator("#journee").innerText()).replace(/\s+/g, " ");
      for (const f of home.features) expect(text).toContain(f);
    });

    test("Preise: Zahlung per Flouci oder Überweisung, Pilotphase ohne Zahlungsmittel", async ({ page }) => {
      await page.goto(BASE + home.path);
      await expect(page.locator("#tarifs .plan").nth(1)).toContainText(home.payment);
      await expect(page.locator("#tarifs .plan-now")).not.toContainText(home.payment);
    });
  });
}

test.describe("Mockups haben die Formate der späteren echten Screenshots", () => {
  const png = async (request: import("@playwright/test").APIRequestContext, url: string) => {
    const res = await request.get(BASE + url);
    expect(res.status(), url).toBe(200);
    const buf = await res.body();
    return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) };
  };
  for (const dir of ["/img/", "/img/ar/"]) {
    test(`${dir}: Desktop 1440 × 900, Handy im Verhältnis 390 : 844`, async ({ request }) => {
      for (const name of ["agenda", "salle", "patient"]) expect(await png(request, `${dir}screen-${name}.png`)).toEqual({ w: 1440, h: 900 });
      for (const name of ["mobile", "booking"]) {
        const { w, h } = await png(request, `${dir}screen-${name}.png`);
        expect(w * 844).toBe(h * 390);
      }
    });
  }
});

test.describe("Rechtstexte: Online-Buchung und Abonnement", () => {
  for (const path of ["/confidentialite/", "/ar/confidentialite/", "/datenschutz/"]) {
    test(`${path} erklärt Online-Buchung und Zahlung der Abos über Flouci`, async ({ page }) => {
      await page.goto(BASE + path);
      const booking = page.locator("#reservation-en-ligne");
      await expect(booking).toHaveCount(1);
      const billing = page.locator("#abonnement");
      await expect(billing).toHaveCount(1);
      const sectionText = async (id: string) =>
        page.evaluate((h2id) => {
          // Text vom Abschnittstitel bis zum nächsten h2
          const start = document.getElementById(h2id)!;
          let text = start.textContent ?? "";
          for (let el = start.nextElementSibling; el && el.tagName !== "H2"; el = el.nextElementSibling) text += " " + el.textContent;
          return text;
        }, id);
      expect(await sectionText("abonnement")).toContain("Flouci");
      expect(await sectionText("reservation-en-ligne")).toMatch(/cookie|cookies|ملفات تعريف الارتباط/i);
      // Fix-Liste 2: 20 Versuche je IP (Mobilfunk-NAT), 3 je Telefonnummer und Praxis
      expect(await sectionText("reservation-en-ligne")).toMatch(/\(20 [^)]*\)/);
      expect(await sectionText("reservation-en-ligne")).toMatch(/\b3\b[^.]*(téléphone|Telefonnummer|الهاتف)/);
      expect(await sectionText("reservation-en-ligne")).not.toMatch(/\(3 (par heure|pro Stunde|في الساعة)\)/);
      await expect(page.locator("main")).not.toContainText(/cabinet dentaire|Zahnarztpraxis|عيادة الأسنان/i);
    });
  }

  test("Muster-AVV beschreibt die Online-Buchung in Anlage 1 und deren Schutz in Anlage 2", async ({ page }) => {
    await page.goto(BASE + "/contrat-sous-traitance/");
    await expect(page.locator("#annexe1 + table")).toContainText("Réservation en ligne");
    const annex2 = await page.evaluate(() => {
      let text = "";
      for (let el = document.getElementById("annexe2")!.nextElementSibling; el; el = el.nextElementSibling) text += " " + el.textContent;
      return text;
    });
    expect(annex2).toContain("réservation en ligne");
    expect(annex2).toContain("deux rendez-vous");
    expect(annex2).toContain("20 tentatives de réservation par heure et par adresse IP");
    expect(annex2).toContain("3 tentatives par heure et par numéro de téléphone");
    await expect(page.locator("main")).not.toContainText(/dentiste titulaire|cabinet dentaire/i);
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

  test("robots.txt: der AdSense-Crawler Mediapartners-Google darf alles crawlen", async ({ request }) => {
    const text = (await (await request.get(BASE + "/robots.txt")).text()).replace(/\r/g, "");
    const groups = text.split(/\n\s*\n/).map((g) => g.trim().split("\n").filter((line) => !line.startsWith("#")));
    const group = groups.find((lines) => lines.includes("User-agent: Mediapartners-Google"));
    expect(group).toEqual(["User-agent: Mediapartners-Google", "Allow: /"]);
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
