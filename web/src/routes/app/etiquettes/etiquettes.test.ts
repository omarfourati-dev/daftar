import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { i18n } from '#lib/i18n.svelte';
import { owner } from '#lib/testing/fixtures';
import { json, mockApi, problem, sentJson } from '#lib/test-utils';
import { assistant, dentist } from '#lib/testing/fixtures';
import type { Cycle, LabelSettings, SpecimenPrint } from '#lib/types/labels';

const settings: LabelSettings = {
	formats: { sterile: 'roll62', specimen: 'a4_3x8' },
	shelfLifeDays: { sachet: 90, double_sachet: 90, conteneur: 90, champ: 90 }
};
const pack = (id: number, seq: number, state: 'usable' | 'used' | 'expired' = 'usable') => ({
	id, seq, code: `A1-0412-0${seq}`, content: seq === 3 ? 'Kit extraction' : 'Kit examen', packaging: 'sachet' as const,
	expiresOn: '2027-01-28', state, use: null
});
const cycle: Cycle = {
	id: 3, equipmentId: 1, equipmentName: 'Autoclave Melag', labelCode: 'A1', number: 412, runAt: '2026-10-30T07:45:00+01:00',
	program: '134 °C – 18 min', result: 'ok', packCount: 3, note: '', performedBy: 'Nisrine Hamza', performedById: 5, initials: 'NH',
	recordedBy: 'Nisrine Hamza', createdAt: '2026-10-30T07:46:00+01:00', cancelledAt: null, cancelledBy: null, cancelReason: null,
	packs: [pack(9, 1), pack(10, 2, 'used'), pack(11, 3)]
};
const print: SpecimenPrint = {
	id: 1042, patient: { id: 77, firstName: 'Sami', lastName: 'Trabelsi', birthDate: '1978-03-12', birthYear: 1978 }, appointmentId: null,
	items: [{ kind: 'edta', count: 2, label: '' }], labelCount: 2,
	labels: [{ code: 'E1042-01', kind: 'edta', label: '' }, { code: 'E1042-02', kind: 'edta', label: '' }],
	collectedAt: '2026-10-30T09:42:00+01:00', collectedBy: 'Nisrine Hamza', printedBy: 'Nisrine Hamza', printedAt: '2026-10-30T09:43:00+01:00'
};

function open(search: string) {
	window.history.replaceState({}, '', `/app/etiquettes${search}`);
	return render(Page);
}
const pageStyle = () => document.head.querySelector('style[data-label-page]')?.textContent ?? '';
const preview = () => within(screen.getByRole('list', { name: 'Aperçu des étiquettes' }));

/** A fake layout for the lines that fit (jsdom has none): a box of 40 characters at any size. */
function narrowLabels() {
	Object.defineProperty(HTMLElement.prototype, 'clientHeight', { configurable: true, get() { return this.dataset.fit ? 20 : 0; } });
	Object.defineProperty(HTMLElement.prototype, 'scrollHeight', {
		configurable: true,
		get() { return this.dataset.fit && (this.textContent ?? '').length > 40 ? 60 : this.dataset.fit ? 20 : 0; }
	});
	return () => {
		// back to the getters of Element.prototype
		delete (HTMLElement.prototype as { clientHeight?: number }).clientHeight;
		delete (HTMLElement.prototype as { scrollHeight?: number }).scrollHeight;
	};
}

describe('/app/etiquettes – labels at their real size, then the browser prints them (spec stock-hygiène 7)', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
		localStorage.clear();
		window.print = vi.fn();
	});
	afterEach(() => window.history.replaceState({}, '', '/'));

	it('prints the packs of a cycle still to use, on the practice’s roll', async () => {
		mockApi({
			'GET /api/labels/settings': () => json(200, settings),
			'GET /api/hygiene/cycles/3': () => json(200, cycle)
		});
		open('?cycle=3');
		expect(await screen.findByRole('heading', { level: 1, name: 'Étiquettes de stérilisation' })).toBeInTheDocument();
		expect(await screen.findByText('Autoclave Melag (A1), cycle n° 412 du 30/10/2026')).toBeInTheDocument();
		expect(screen.getByLabelText(/Rouleau 62 mm/)).toBeChecked();
		expect(pageStyle()).toContain('size:62mm 29mm;margin:0');
		const labels = preview().getAllByRole('article');
		expect(labels.map((l) => l.getAttribute('aria-label'))).toEqual(['Étiquette A1-0412-01', 'Étiquette A1-0412-03']); // the used one stays out
		const first = within(labels[0]);
		expect(first.getByText('Kit examen')).toBeInTheDocument();
		expect(first.getByText('Cabinet du Lac')).toBeInTheDocument();
		expect(first.getByText('28/01/2027')).toBeInTheDocument();
		expect(first.getByText('Autoclave A1 – NH')).toBeInTheDocument();
		expect(first.getByText('A1-0412-01')).toHaveAttribute('dir', 'ltr');
		expect(labels[0].querySelector('svg[data-qr="A1-0412-01"]')).not.toBeNull();
		await fireEvent.click(screen.getByRole('button', { name: 'Imprimer 2 étiquette(s)' }));
		expect(window.print).toHaveBeenCalledOnce();
		// a reprint: one more pack chosen by hand
		await fireEvent.click(screen.getByRole('button', { name: /2 étiquette\(s\) sur 3/ }));
		await fireEvent.click(screen.getByRole('checkbox', { name: /A1-0412-02/ }));
		expect(preview().getAllByRole('article')).toHaveLength(3);
	});

	it('changes the format, keeps it for next time and continues a started A4 sheet', async () => {
		mockApi({
			'GET /api/labels/settings': () => json(200, settings),
			'GET /api/hygiene/cycles/3': () => json(200, cycle),
			'PATCH /api/labels/settings': () => json(200, { ...settings, formats: { ...settings.formats, sterile: 'a4_3x8' } })
		});
		localStorage.setItem('daftar.labels.sheetStart', '23');
		open('?cycle=3');
		await fireEvent.click(await screen.findByLabelText(/Planche A4 de 24/));
		expect(pageStyle()).toContain('size:210mm 297mm');
		const map = within(screen.getByRole('group', { name: 'Planche A4, 24 positions' }));
		expect(map.getByRole('button', { name: 'Commencer à la position 23' })).toHaveAttribute('aria-pressed', 'true');
		expect(screen.getByText('1 planche(s) à imprimer')).toBeInTheDocument();
		await fireEvent.click(map.getByRole('button', { name: 'Commencer à la position 24' }));
		expect(screen.getByText('2 planche(s) à imprimer')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Imprimer 2 étiquette(s)' }));
		// the sheet moves on only once the labels came out (a print cancelled in the dialog leaves it – review N5)
		expect(await screen.findByText('Les 2 étiquette(s) sont-elles bien sorties de l’imprimante ?')).toBeInTheDocument();
		expect(localStorage.getItem('daftar.labels.sheetStart')).toBe('24');
		await fireEvent.click(screen.getByRole('button', { name: 'Oui, bien sorties' }));
		expect(await screen.findByText('La prochaine impression sur planche commencera à la position 2 (modifiable).')).toBeInTheDocument();
		expect(localStorage.getItem('daftar.labels.sheetStart')).toBe('2');
		await fireEvent.click(screen.getByRole('button', { name: 'Garder ce format pour les prochaines fois' }));
		await vi.waitFor(() => expect(sentJson('PATCH /api/labels/settings')).toEqual({ formats: { sterile: 'a4_3x8' } }));
		expect(await screen.findByText('Format enregistré pour les prochaines fois.')).toBeInTheDocument();
	});

	it('prints the tubes of a specimen print on its format, with NOM Prénom and the birth date', async () => {
		auth.set('tok', dentist);
		mockApi({
			'GET /api/labels/settings': () => json(200, settings),
			'GET /api/labels/specimens/1042': () => json(200, print)
		});
		open('?specimen=1042');
		expect(await screen.findByText('TRABELSI Sami, 2 tube(s)')).toBeInTheDocument();
		expect(screen.getByLabelText(/Planche A4 de 24/)).toBeChecked();
		const label = within(preview().getAllByRole('article')[0]);
		expect(label.getByText('TRABELSI Sami')).toBeInTheDocument();
		expect(label.getByText('Né(e) le 12/03/1978')).toBeInTheDocument(); // no "N° 77": the id means nothing to the lab
		expect(preview().getAllByRole('article')[0]).not.toHaveTextContent('77');
		expect(label.getByText('Sang EDTA')).toBeInTheDocument();
		expect(label.getByText(/^Prél\. le 30\/10\/2026 09:42\s– NH$/)).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Retour' })).toHaveAttribute('href', '/app/patients/77');
		expect(screen.queryByRole('button', { name: /Garder ce format/ })).toBeNull(); // the dentist does not set up the desk
	});

	it('prints a test page and shows the label edge and the smallest text', async () => {
		mockApi({ 'GET /api/labels/settings': () => json(200, settings) });
		open('?test=1&format=label57x32');
		expect(await screen.findByRole('heading', { level: 1, name: 'Page de test' })).toBeInTheDocument();
		await screen.findByRole('list', { name: 'Aperçu des étiquettes' });
		expect(pageStyle()).toContain('size:57mm 32mm');
		const label = within(preview().getByRole('article', { name: 'Étiquette de test 1' }));
		expect(label.getByText('57 × 32 mm')).toBeInTheDocument();
		expect(label.getByText('Aa 0123456789')).toBeInTheDocument();
		await fireEvent.click(screen.getByLabelText(/Planche A4 de 24/));
		expect(preview().getAllByRole('article')).toHaveLength(24);
		await fireEvent.click(screen.getByRole('button', { name: 'Imprimer la page de test' }));
		expect(window.print).toHaveBeenCalledOnce();
	});

	it('says why there is nothing to print', async () => {
		mockApi({
			'GET /api/labels/settings': () => json(200, settings),
			'GET /api/hygiene/cycles/4': () => json(200, { ...cycle, id: 4, result: 'not_ok', packs: [] }),
			'GET /api/hygiene/cycles/5': () => problem(404, 'not_found')
		});
		open('?cycle=4');
		expect(await screen.findByText('Cycle non conforme : aucune étiquette. Recommencez le cycle.')).toBeInTheDocument();
		expect(screen.getByText('Aucune étiquette à imprimer.')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Imprimer 0 étiquette(s)' })).toBeDisabled();
	});

	it('prints nothing for a recalled or a cancelled cycle, also from an old link with its packs (review N1, H1)', async () => {
		const recalled = { ...cycle, id: 4, result: 'not_ok' as const, packs: cycle.packs.map((p) => ({ ...p, state: 'not_sterile' as const })) };
		const cancelled = {
			...cycle, id: 6, cancelledAt: '2026-10-30T09:00:00+01:00', cancelledBy: 'Amira', cancelReason: 'Saisi deux fois',
			packs: cycle.packs.map((p) => ({ ...p, state: 'cancelled' as const }))
		};
		mockApi({
			'GET /api/labels/settings': () => json(200, settings),
			'GET /api/hygiene/cycles/4': () => json(200, recalled),
			'GET /api/hygiene/cycles/6': () => json(200, cancelled)
		});
		const page = open('?cycle=4&packs=9,11');
		expect(await screen.findByText('Cycle non conforme : aucune étiquette. Recommencez le cycle.')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Imprimer 0 étiquette(s)' })).toBeDisabled();
		expect(screen.queryByRole('button', { name: /étiquette\(s\) sur/ })).toBeNull(); // nothing to choose
		page.unmount();
		open('?cycle=6&packs=9');
		expect(await screen.findByText('Cycle annulé (Saisi deux fois) : aucune étiquette. Ses étiquettes déjà imprimées ne sont plus valables.')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Imprimer 0 étiquette(s)' })).toBeDisabled();
	});

	it('leaves the A4 start where it was when nothing came out of the printer (review N5)', async () => {
		mockApi({
			'GET /api/labels/settings': () => json(200, { ...settings, formats: { ...settings.formats, sterile: 'a4_3x8' } }),
			'GET /api/hygiene/cycles/3': () => json(200, cycle)
		});
		open('?cycle=3');
		await fireEvent.click(await screen.findByRole('button', { name: 'Imprimer 2 étiquette(s)' }));
		await fireEvent.click(await screen.findByRole('button', { name: 'Non, pas imprimées' }));
		expect(await screen.findByText('La planche reste à la position 1.')).toBeInTheDocument();
		expect(localStorage.getItem('daftar.labels.sheetStart')).toBeNull();
		expect(screen.queryByRole('button', { name: 'Oui, bien sorties' })).toBeNull();
	});

	it('warns before printing a content too long for the format instead of cutting it silently (review M6)', async () => {
		const restore = narrowLabels();
		try {
			const long = 'Kit extraction chirurgicale complet + élévateurs + davier 17'; // 60 characters
			mockApi({
				'GET /api/labels/settings': () => json(200, settings),
				'GET /api/hygiene/cycles/3': () => json(200, { ...cycle, packs: [{ ...pack(9, 1), content: long }, { ...pack(11, 3), content: long }] })
			});
			open('?cycle=3');
			const alert = await screen.findByRole('alert');
			expect(alert).toHaveTextContent('Texte trop long : il serait coupé sur l’étiquette');
			expect(alert).toHaveTextContent(`Contenu trop long pour ce format – 20 caractère(s) en trop : « ${long} ».`);
			expect(alert).toHaveTextContent('Choisissez un format plus grand (planche A4) ou raccourcissez le texte avant d’imprimer.');
			expect(within(alert).getAllByRole('listitem')).toHaveLength(1); // the same content once
		} finally {
			restore();
		}
	});

	it('writes the first names as initials when the name is too long, and says so', async () => {
		const restore = narrowLabels();
		try {
			mockApi({
				'GET /api/labels/settings': () => json(200, settings),
				'GET /api/labels/specimens/1042': () =>
					json(200, { ...print, patient: { ...print.patient, firstName: 'Mohamed Amine Fatma', lastName: 'Ben Hadj Abdallah El Ouerghemmi' } })
			});
			open('?specimen=1042');
			// 51 characters in full, 40 with the initials
			const label = within(await screen.findByRole('article', { name: 'Étiquette E1042-01' }));
			expect(label.getByText('BEN HADJ ABDALLAH EL OUERGHEMMI M. A. F.')).toBeInTheDocument();
			expect(screen.getByText('Prénom(s) en initiales pour tenir sur ce format : « BEN HADJ ABDALLAH EL OUERGHEMMI M. A. F. ».')).toBeInTheDocument();
			expect(screen.queryByRole('alert')).toBeNull();
		} finally {
			restore();
		}
	});

	it('prints specimen labels in French on an Arabic screen; sterilisation labels follow the screen (review M3)', async () => {
		auth.set('tok', owner);
		i18n.setLocale('ar');
		mockApi({
			'GET /api/labels/settings': () => json(200, settings),
			'GET /api/labels/specimens/1042': () => json(200, { ...print, labels: [{ code: 'E1042-01', kind: 'urine', label: '' }], labelCount: 1 }),
			'GET /api/hygiene/cycles/3': () => json(200, cycle)
		});
		const page = open('?specimen=1042');
		expect(await screen.findByRole('heading', { level: 1, name: 'ملصقات العيّنات' })).toBeInTheDocument();
		const tube = await screen.findByRole('article', { name: 'Étiquette E1042-01' });
		expect(tube).toHaveAttribute('lang', 'fr');
		expect(tube).toHaveAttribute('dir', 'ltr');
		expect(tube).toHaveTextContent('Urine');
		expect(tube).toHaveTextContent('Né(e) le 12/03/1978');
		expect(tube).toHaveTextContent('Prél. le 30/10/2026 09:42 – NH');
		page.unmount();
		open('?cycle=3');
		const pack = await screen.findByRole('article', { name: 'ملصق A1-0412-01' });
		expect(pack).toHaveAttribute('lang', 'ar');
		expect(pack).toHaveAttribute('dir', 'rtl');
	});

	it('explains a print that does not exist', async () => {
		mockApi({
			'GET /api/labels/settings': () => json(200, settings),
			'GET /api/hygiene/cycles/5': () => problem(404, 'not_found')
		});
		open('?cycle=5');
		expect(await screen.findByText('Ces étiquettes n’existent pas ou plus.')).toBeInTheDocument();
	});
});
