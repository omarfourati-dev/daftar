import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join } from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import jsQR from 'jsqr';
import { PNG } from 'pngjs';
import { APP, axe, currentQuarter, newPatient, newPractice, signIn, type Practice } from './daily';

/**
 * Spec stock-hygiène 5.3, 6, 7: a cycle and its labels on the phone, labels that come out right on real printers –
 * each format printed to PDF with its own page size, nothing cut off, the QR code read back from the rendered PDF
 * (the procedure of marketing/shared/lib.mjs `readQr`: render, PNG, jsQR) –, the traceability in the appointment
 * (expired and "non conforme" packs refused with the reason), both searches of the owner, specimen labels with the
 * birth date, Arabic right to left.
 *
 * `LABEL_SHOTS=<folder>` keeps a PNG of the print preview (the rendered PDF) of every format there.
 */

const require = createRequire(import.meta.url);
const PDFJS = readFileSync(require.resolve('pdfjs-dist/build/pdf.mjs'), 'utf8');
const PDFJS_WORKER = readFileSync(require.resolve('pdfjs-dist/build/pdf.worker.mjs'), 'utf8');
const MM = 72 / 25.4;
const PAPER: Record<string, [number, number]> = { roll62: [62, 29], label57x32: [57, 32], a4_3x8: [210, 297] };
/** Ink-free band at the edges of the paper, mm: printers cannot reach it (label printers ~1.5 mm, office printers ~3 mm). */
const MARGIN: Record<string, number> = { roll62: 1.5, label57x32: 1.5, a4_3x8: 3 };

async function noHorizontalScroll(page: Page, label: string) {
	const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
	expect(overflow, `${label} – horizontal overflow in px`).toBeLessThanOrEqual(0);
}

/**
 * Every label of the print area: every line of text (its whole font box, marks included) inside the label – the label
 * clips what sticks out –, no code, date or name shortened, no line hidden, nothing below 7 pt.
 */
async function nothingCut(page: Page) {
	const problems = await page.evaluate(() => {
		const out: string[] = [];
		for (const label of document.querySelectorAll<HTMLElement>('.print-area article')) {
			const box = label.getBoundingClientRect();
			const walker = document.createTreeWalker(label, NodeFilter.SHOW_TEXT);
			for (let node = walker.nextNode(); node; node = walker.nextNode()) {
				if (!node.textContent?.trim()) continue;
				const range = document.createRange();
				range.selectNodeContents(node);
				for (const r of range.getClientRects()) {
					if (r.width === 0) continue;
					if (r.left < box.left - 0.5 || r.right > box.right + 0.5 || r.top < box.top - 0.5 || r.bottom > box.bottom + 0.5)
						out.push(`${label.dataset.label}: "${node.textContent}" outside the label (${Math.round(r.bottom - box.bottom)} px)`);
				}
				const size = parseFloat(getComputedStyle(node.parentElement!).fontSize);
				if (size < 9.33) out.push(`${label.dataset.label}: "${node.textContent}" at ${size}px`);
			}
			for (const el of label.querySelectorAll<HTMLElement>('[data-critical]')) {
				if (el.scrollWidth > el.clientWidth + 1 || el.dataset.overflow === 'true')
					out.push(`${label.dataset.label}: "${el.textContent}" shortened (${el.scrollWidth}×${el.scrollHeight} in ${el.clientWidth}×${el.clientHeight})`);
			}
		}
		return out;
	});
	expect(problems).toEqual([]);
}

interface Rendered {
	pages: { width: number; height: number }[];
	/** Page 1 at 300 dpi. */
	png: Buffer;
	/** The first label alone (an A4 sheet carries several QR codes). */
	first: Buffer;
	inkAtEdges: boolean;
}

/** Renders page 1 of a PDF with pdf.js in a blank page (300 dpi), and looks for ink in the margin band. */
async function renderPdf(page: Page, pdf: Buffer, marginMm: number, firstLabelMm: [number, number, number, number] | null = null): Promise<Rendered> {
	const viewer = await page.context().newPage();
	try {
		await viewer.goto('about:blank');
		await viewer.addScriptTag({ type: 'module', content: PDFJS_WORKER });
		await viewer.addScriptTag({ type: 'module', content: PDFJS });
		await viewer.waitForFunction(() => 'pdfjsLib' in globalThis && 'pdfjsWorker' in globalThis);
		const result = await viewer.evaluate(
			async ({ data, margin, crop }) => {
				// eslint-disable-next-line @typescript-eslint/no-explicit-any -- pdf.js loaded as a script
				const lib = (globalThis as any).pdfjsLib;
				const bytes = Uint8Array.from(atob(data), (c) => c.charCodeAt(0));
				const doc = await lib.getDocument({ data: bytes }).promise;
				const pages = [];
				for (let i = 1; i <= doc.numPages; i++) {
					const vp = (await doc.getPage(i)).getViewport({ scale: 1 });
					pages.push({ width: vp.width, height: vp.height });
				}
				const first = await doc.getPage(1);
				const scale = 300 / 72;
				const vp = first.getViewport({ scale });
				const canvas = document.createElement('canvas');
				canvas.width = Math.round(vp.width);
				canvas.height = Math.round(vp.height);
				const ctx = canvas.getContext('2d')!;
				ctx.fillStyle = '#fff';
				ctx.fillRect(0, 0, canvas.width, canvas.height);
				await first.render({ canvasContext: ctx, viewport: vp }).promise;
				const band = Math.round((margin / 25.4) * 300);
				const img = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
				let ink = false;
				for (let y = 0; y < canvas.height && !ink; y++) {
					for (let x = 0; x < canvas.width; x++) {
						if (x >= band && x < canvas.width - band && y >= band && y < canvas.height - band) continue;
						const i = (y * canvas.width + x) * 4;
						if (img[i] < 200 || img[i + 1] < 200 || img[i + 2] < 200) {
							ink = true;
							break;
						}
					}
				}
				let label = canvas;
				if (crop) {
					const px = (mm: number) => Math.round((mm / 25.4) * 300);
					label = document.createElement('canvas');
					label.width = px(crop[2]);
					label.height = px(crop[3]);
					label.getContext('2d')!.drawImage(canvas, px(crop[0]), px(crop[1]), label.width, label.height, 0, 0, label.width, label.height);
				}
				const png = (c: HTMLCanvasElement) => c.toDataURL('image/png').split(',')[1];
				return { pages, png: png(canvas), first: png(label), inkAtEdges: ink };
			},
			{ data: pdf.toString('base64'), margin: marginMm, crop: firstLabelMm }
		);
		return { ...result, png: Buffer.from(result.png, 'base64'), first: Buffer.from(result.first, 'base64') };
	} finally {
		await viewer.close();
	}
}

/** `readQr` of marketing/shared/lib.mjs: a QR code read from a PNG. */
function readQr(png: Buffer): string | null {
	const image = PNG.sync.read(png);
	return jsQR(new Uint8ClampedArray(image.data), image.width, image.height)?.data ?? null;
}

/** Prints the open label page to PDF with its own page size and checks paper, pages, edges and the QR code. */
async function checkPrint(page: Page, format: string, expected: { pages: number; qr: string; shot: string }) {
	await page.emulateMedia({ media: 'print' });
	await nothingCut(page);
	const pdf = await page.pdf({ preferCSSPageSize: true, printBackground: true });
	await page.emulateMedia({ media: 'screen' });
	const rendered = await renderPdf(page, pdf, MARGIN[format], format === 'a4_3x8' ? [0, 0.5, 70, 37] : null);
	const [w, h] = PAPER[format];
	expect(rendered.pages, `${format}: pages`).toHaveLength(expected.pages);
	for (const p of rendered.pages) {
		expect(Math.abs(p.width - w * MM), `${format}: width ${p.width}pt`).toBeLessThan(1);
		expect(Math.abs(p.height - h * MM), `${format}: height ${p.height}pt`).toBeLessThan(1);
	}
	expect(rendered.inkAtEdges, `${format}: ink within ${MARGIN[format]} mm of the paper edge`).toBe(false);
	expect(readQr(rendered.first), `${format}: QR code read from the rendered PDF`).toBe(expected.qr);
	const shots = process.env.LABEL_SHOTS;
	if (shots) {
		mkdirSync(shots, { recursive: true });
		writeFileSync(join(shots, `${expected.shot}.png`), rendered.png);
	}
}

async function setupCycle(p: Practice) {
	const autoclave = await p.api.post('/api/hygiene/equipment', { name: 'Autoclave Melag 23V', kind: 'autoclave' });
	return p.api.post('/api/hygiene/cycles', {
		equipmentId: autoclave.id,
		number: 412,
		program: '134 °C – 18 min',
		result: 'ok',
		packs: [
			{ content: 'Kit extraction chirurgicale complet', packaging: 'sachet', quantity: 2 },
			{ content: 'Kit examen', packaging: 'double_sachet', quantity: 1 }
		]
	});
}

test('a cycle on the phone: autoclave, packs in taps, labels at their real size', async ({ page, request }) => {
	const p = await newPractice(request);
	await page.setViewportSize({ width: 360, height: 780 });
	await signIn(page, p);
	await page.goto(APP + '/app/hygiene?tab=sterilisation');
	await expect(page.getByText(/Aucun cycle sur cette période/)).toBeVisible();
	await axe(page);
	await noHorizontalScroll(page, 'sterilisation 360');
	await page.getByRole('button', { name: 'Nouveau cycle' }).first().click();
	const dialog = page.getByRole('dialog', { name: 'Nouveau cycle de stérilisation' });
	await dialog.getByLabel('Nom de l’autoclave').fill('Autoclave Melag');
	await dialog.getByRole('button', { name: 'Ajouter l’autoclave' }).click();
	await expect(dialog.getByLabel('N° de cycle')).toHaveValue('1');
	await dialog.getByText('Conforme', { exact: true }).click();
	const quick = dialog.getByRole('group', { name: 'Ajouter un paquet type' });
	await quick.getByRole('button', { name: 'Kit petite chirurgie' }).click();
	await quick.getByRole('button', { name: 'Kit petite chirurgie' }).click();
	await quick.getByRole('button', { name: 'Kit suture' }).click();
	await expect(dialog.getByText('3 paquet(s), une étiquette chacun.')).toBeVisible();
	await axe(page);
	await noHorizontalScroll(page, 'cycle dialog 360');
	await dialog.getByRole('button', { name: 'Enregistrer et imprimer 3 étiquette(s)' }).click();

	await expect(page).toHaveURL(/\/app\/etiquettes\?cycle=\d+$/);
	await expect(page.getByRole('heading', { level: 1, name: 'Étiquettes de stérilisation' })).toBeVisible();
	const preview = page.getByRole('list', { name: 'Aperçu des étiquettes' });
	await expect(preview.getByRole('article')).toHaveCount(3);
	await expect(preview.getByRole('article', { name: 'Étiquette A1-0001-01' })).toContainText('Kit petite chirurgie');
	// the preview is at the real size: 62 mm wide
	const width = await preview.getByRole('article').first().evaluate((el) => el.getBoundingClientRect().width);
	expect(Math.abs(width - (62 * 96) / 25.4)).toBeLessThan(1);
	await axe(page);
	await noHorizontalScroll(page, 'labels 360');
	await page.getByText('Planche A4 de 24').click();
	await page.getByRole('button', { name: 'Commencer à la position 5' }).click();
	await expect(page.getByText('1 planche(s) à imprimer')).toBeVisible();
	await axe(page);
	await noHorizontalScroll(page, 'labels A4 360');
});

test('every format comes out right: paper size, nothing cut, QR read from the PDF', async ({ page, request }) => {
	const p = await newPractice(request);
	const cycle = await setupCycle(p);
	const patient = await newPatient(p, { firstName: 'Mohamed Amine', lastName: 'Ben Abdallah El Ouerghemmi', birthDate: '1978-03-12' });
	const specimens = await p.api.post('/api/labels/specimens', {
		patientId: patient.id,
		items: [{ kind: 'edta', count: 2 }, { kind: 'autre', count: 1, label: 'Liquide pleural' }],
		collectedBy: 'Dr Amira Ben Salem'
	});
	await signIn(page, p);
	for (const format of ['roll62', 'label57x32', 'a4_3x8']) {
		await page.goto(`${APP}/app/etiquettes?cycle=${cycle.id}&format=${format}`);
		await expect(page.getByRole('list', { name: 'Aperçu des étiquettes' }).getByRole('article')).toHaveCount(3);
		await checkPrint(page, format, { pages: format === 'a4_3x8' ? 1 : 3, qr: 'A1-0412-01', shot: `sterilisation-${format}` });
		if (process.env.LABEL_SHOTS) await page.screenshot({ path: join(process.env.LABEL_SHOTS, `vorschau-${format}.png`), fullPage: true });
		await page.goto(`${APP}/app/etiquettes?specimen=${specimens.id}&format=${format}`);
		await expect(page.getByRole('list', { name: 'Aperçu des étiquettes' }).getByRole('article').first()).toContainText(
			'BEN ABDALLAH EL OUERGHEMMI Mohamed Amine'
		);
		await checkPrint(page, format, { pages: format === 'a4_3x8' ? 1 : 3, qr: `E${specimens.id}-01`, shot: `prelevement-${format}` });
	}
	// a started A4 sheet: the labels move on, the QR code of the first label is on its position
	await page.goto(`${APP}/app/etiquettes?cycle=${cycle.id}&format=a4_3x8`);
	await page.getByRole('button', { name: 'Commencer à la position 23' }).click();
	await expect(page.getByText('2 planche(s) à imprimer')).toBeVisible();
	await page.emulateMedia({ media: 'print' });
	const pdf = await page.pdf({ preferCSSPageSize: true, printBackground: true });
	expect((await renderPdf(page, pdf, 3)).pages).toHaveLength(2);
	await page.emulateMedia({ media: 'screen' });
	// the test page of each format: the edge of the label is printed on purpose
	for (const format of ['roll62', 'label57x32']) {
		await page.goto(`${APP}/app/etiquettes?test=1&format=${format}`);
		await expect(page.getByRole('article', { name: 'Étiquette de test 1' }).first()).toBeVisible();
		await page.emulateMedia({ media: 'print' });
		const rendered = await renderPdf(page, await page.pdf({ preferCSSPageSize: true, printBackground: true }), 0.5);
		await page.emulateMedia({ media: 'screen' });
		expect(rendered.pages).toHaveLength(1);
		expect(readQr(rendered.png)).toBe('TEST');
		if (process.env.LABEL_SHOTS) writeFileSync(join(process.env.LABEL_SHOTS, `test-${format}.png`), rendered.png);
	}
});

test('labels in Arabic stay right to left with codes left to right, and still fit', async ({ page, request }) => {
	const p = await newPractice(request);
	const cycle = await setupCycle(p);
	const patient = await newPatient(p, { firstName: 'سامي', lastName: 'الطرابلسي', birthYear: 1990 });
	const specimens = await p.api.post('/api/labels/specimens', { patientId: patient.id, items: [{ kind: 'urine', count: 1 }] });
	await signIn(page, p, 'ar');
	await page.goto(`${APP}/app/etiquettes?cycle=${cycle.id}&format=roll62`);
	const label = page.getByRole('list', { name: 'معاينة الملصقات' }).getByRole('article').first();
	await expect(label).toHaveAttribute('dir', 'rtl');
	await expect(label.getByText('A1-0412-01')).toHaveAttribute('dir', 'ltr');
	await expect(label).toContainText('يُستعمل قبل');
	await axe(page);
	await page.setViewportSize({ width: 360, height: 780 });
	await noHorizontalScroll(page, 'labels ar 360');
	await checkPrint(page, 'roll62', { pages: 3, qr: 'A1-0412-01', shot: 'sterilisation-roll62-ar' });
	await page.goto(`${APP}/app/etiquettes?specimen=${specimens.id}&format=label57x32`);
	await expect(page.getByRole('list', { name: 'معاينة الملصقات' }).getByRole('article').first()).toContainText('سنة الولادة 1990');
	await checkPrint(page, 'label57x32', { pages: 1, qr: `E${specimens.id}-01`, shot: 'prelevement-57x32-ar' });
});

test('traceability: the desk notes packs in the appointment, refused ones say why; the owner searches both ways', async ({ page, request }) => {
	const p = await newPractice(request);
	await p.api.patch('/api/labels/settings', { shelfLifeDays: { conteneur: 1 } });
	const autoclave = await p.api.post('/api/hygiene/equipment', { name: 'Autoclave', kind: 'autoclave' });
	const yesterday = new Date(Date.now() - 2 * 86_400_000).toISOString();
	await p.api.post('/api/hygiene/cycles', {
		equipmentId: autoclave.id, number: 7, runAt: yesterday, result: 'ok', packs: [{ content: 'Plateau ancien', packaging: 'conteneur', quantity: 1 }]
	});
	const recalled = await p.api.post('/api/hygiene/cycles', { equipmentId: autoclave.id, number: 8, result: 'ok', packs: [{ content: 'Kit rappelé', quantity: 1 }] });
	await p.api.patch(`/api/hygiene/cycles/${recalled.id}`, { result: 'not_ok', reason: 'Indicateur biologique positif' });
	await p.api.post('/api/hygiene/cycles', { equipmentId: autoclave.id, number: 9, result: 'ok', packs: [{ content: 'Kit examen', quantity: 2 }] });
	const patient = await newPatient(p, { firstName: 'Hela', lastName: 'Tracee' });
	const now = currentQuarter();
	const created = await p.api.post('/api/appointments', {
		patientId: patient.id, startsAt: now.startsAt, durationMin: 10, serviceId: p.services[0].id, reason: 'Consultation',
		practitionerId: p.practitioners[0].id
	});
	await p.api.post(`/api/appointments/${created.appointment.id}/status`, { status: 'arrived' });

	await page.setViewportSize({ width: 360, height: 780 });
	await signIn(page, p);
	await page.goto(APP + '/app/agenda');
	await page.getByRole('button', { name: new RegExp(`${now.time} Hela Tracee`) }).click();
	const dialog = page.getByRole('dialog', { name: 'Hela Tracee' });
	await dialog.getByRole('button', { name: 'Traçabilité stérilisation' }).click();
	const region = dialog.getByRole('region', { name: 'Paquets stérilisés utilisés' });
	await region.getByRole('list', { name: 'Paquets à utiliser' }).getByRole('button', { name: /A1-0009-01/ }).click();
	await expect(region.getByText('A1-0009-01 (Kit examen) noté pour ce patient.')).toBeVisible();
	// an expired pack, typed as on the label
	await region.getByLabel('Code du paquet').fill('a1 0007 01');
	await expect(region.getByText(/Périmé depuis le/)).toBeVisible();
	await region.getByRole('button', { name: 'Noter' }).click();
	await expect(region.getByRole('alert')).toContainText('Paquet périmé (à utiliser avant le');
	// a pack of a cycle found "non conforme" afterwards
	await region.getByLabel('Code du paquet').fill('A1-0008-01');
	await region.getByRole('button', { name: 'Noter' }).click();
	await expect(region.getByRole('alert')).toContainText('Cycle non conforme : ce paquet n’est pas stérile.');
	await axe(page);
	await noHorizontalScroll(page, 'appointment traceability 360');

	// specimen labels from the same appointment
	await dialog.getByRole('button', { name: 'Étiquettes de prélèvement' }).click();
	await dialog.getByRole('button', { name: 'Un de plus – Sang EDTA' }).click();
	await dialog.getByRole('button', { name: 'Préparer 1 étiquette(s)' }).click();
	await expect(page).toHaveURL(/\/app\/etiquettes\?specimen=\d+$/);
	await expect(page.getByRole('list', { name: 'Aperçu des étiquettes' }).getByRole('article')).toContainText('TRACEE Hela');

	// the owner: who got pack X, which packs did patient Y get
	await page.setViewportSize({ width: 1280, height: 900 });
	await page.goto(APP + '/app/hygiene?tab=sterilisation');
	const trace = page.getByRole('region', { name: 'Traçabilité' });
	await trace.getByLabel('Code du paquet').fill('A1-0009-01');
	await trace.getByRole('button', { name: 'Rechercher' }).click();
	await expect(trace.getByRole('link', { name: 'Hela Tracee' })).toBeVisible();
	await trace.getByRole('button', { name: 'Un patient' }).click();
	await trace.getByRole('searchbox').or(trace.getByRole('combobox')).or(trace.getByRole('textbox')).first().fill('Tracee');
	await trace.getByRole('button', { name: /Hela Tracee/ }).click();
	await expect(trace.getByText('Hela Tracee : 1 paquet(s)')).toBeVisible();
	await expect(trace).toContainText('A1-0009-01');
	await axe(page);
	// the cycles: the recalled one says so, the correction is in the journal
	const cycles = page.getByRole('list', { name: 'Cycles de stérilisation' });
	await expect(cycles).toContainText('Ses 1 paquet(s) sont refusés.');
	await page.getByRole('button', { name: 'Historique' }).click();
	await expect(page.getByRole('list', { name: 'Journal des corrections' })).toContainText('a corrigé le cycle A1 n° 8');
});

test('specimen labels from the patient file with the full birth date; Arabic file', async ({ page, request }) => {
	const p = await newPractice(request);
	const patient = await newPatient(p, { firstName: 'Lina', lastName: 'Ayari' });
	await signIn(page, p);
	await page.setViewportSize({ width: 360, height: 780 });
	await page.goto(`${APP}/app/patients/${patient.id}`);
	await page.getByRole('button', { name: 'Modifier' }).click();
	const form = page.getByRole('dialog', { name: 'Modifier le patient' });
	await form.getByLabel('Date de naissance').fill('2015-06-01');
	await form.getByRole('button', { name: 'Enregistrer' }).click();
	await expect(page.getByText('né(e) le 01/06/2015')).toBeVisible();
	const specimens = page.getByRole('region', { name: 'Prélèvements' });
	await specimens.getByRole('button', { name: 'Étiquettes de prélèvement' }).click();
	await specimens.getByRole('button', { name: 'Un de plus – Urine' }).click();
	await axe(page);
	await noHorizontalScroll(page, 'patient specimens 360');
	await specimens.getByRole('button', { name: 'Préparer 1 étiquette(s)' }).click();
	const label = page.getByRole('list', { name: 'Aperçu des étiquettes' }).getByRole('article');
	await expect(label).toContainText('AYARI Lina');
	await expect(label).toContainText('Né(e) le 01/06/2015');
	await expect(label).toContainText('Urine');
	await page.getByRole('link', { name: 'Retour' }).click();
	await expect(page.getByRole('region', { name: 'Prélèvements' }).getByText('1 × Urine', { exact: true })).toBeVisible();

	await page.context().clearCookies();
	await signIn(page, p, 'ar');
	await page.goto(`${APP}/app/patients/${patient.id}`);
	await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
	await expect(page.getByRole('region', { name: 'العيّنات' })).toContainText('1 × بول');
	await axe(page);
	await noHorizontalScroll(page, 'patient ar 360');
});
