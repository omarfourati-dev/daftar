import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { deps } from '../../api';
import { auth } from '../../auth.svelte';
import { clock } from '../../clock';
import { i18n } from '../../i18n.svelte';
import { calls, json, labelInNameProblems, mockApi, noContent, problem, sentJson } from '../../test-utils';
import { assistant, dentist, owner } from '../../testing/fixtures';
import type { Cycle, CycleSetup, LabelSettings, PackFound, PackUse } from '../../types/labels';
import CycleCorrection from './CycleCorrection.svelte';
import CycleDialog from './CycleDialog.svelte';
import SpecimenForm from './SpecimenForm.svelte';
import SterileTrace from './SterileTrace.svelte';
import SterilizationTab from './SterilizationTab.svelte';

const settings: LabelSettings = {
	formats: { sterile: 'roll62', specimen: 'roll62' },
	shelfLifeDays: { sachet: 90, double_sachet: 180, conteneur: 90, champ: 90 }
};
const setup: CycleSetup = {
	autoclaves: [{ id: 4, name: 'Autoclave Melag', labelCode: 'A1', nextNumber: 413, lastRunAt: '2026-10-29T17:00:00+01:00' }],
	programs: ['134 °C – 18 min', '121 °C – 20 min'],
	contents: ['Kit examen', 'Kit extraction', 'Kit détartrage'],
	team: [
		{ id: 2, name: 'Amira Ben Salah', initials: 'ABS' },
		{ id: 5, name: 'Salma', initials: 'S' }
	]
};
const found = (code: string, state: PackFound['state'] = 'usable', extra: Partial<PackFound> = {}): PackFound => ({
	id: Number(code.slice(-2)), seq: Number(code.slice(-2)), code, content: 'Kit examen', packaging: 'sachet', expiresOn: '2027-01-28', state,
	use: null, cycleId: 3, labelCode: 'A1', number: 412, equipmentName: 'Autoclave Melag', runAt: '2026-10-30T07:45:00+01:00', cancelReason: null,
	...extra
});
const used = (code: string, extra: Partial<PackUse> = {}): PackUse => ({
	id: 50, packId: 1, code, content: 'Kit examen', packaging: 'sachet', expiresOn: '2027-01-28',
	cycle: { id: 3, labelCode: 'A1', number: 412, equipmentName: 'Autoclave Melag', runAt: '2026-10-30T07:45:00+01:00', result: 'ok' },
	patientId: 7, patientName: 'Sami Trabelsi', patientNo: 7, patientDeleted: false, appointmentId: 30, usedAt: '2026-10-30T09:05:00+01:00',
	usedBy: 'Karim', undoable: true, ...extra
});
const brief = { id: 50, patientId: 7, patientName: 'Sami Trabelsi', patientNo: 7, patientDeleted: false, appointmentId: 30, usedAt: '2026-10-30T09:05:00+01:00', usedBy: 'Karim' };
const cycle: Cycle = {
	id: 3, equipmentId: 4, equipmentName: 'Autoclave Melag', labelCode: 'A1', number: 412, runAt: '2026-10-30T07:45:00+01:00',
	program: '134 °C – 18 min', result: 'ok', packCount: 2, note: '', performedBy: 'Salma', performedById: 5, initials: 'S', recordedBy: 'Salma',
	createdAt: '2026-10-30T07:46:00+01:00', cancelledAt: null, cancelledBy: null, cancelReason: null,
	packs: [
		{ id: 1, seq: 1, code: 'A1-0412-01', content: 'Kit examen', packaging: 'sachet', expiresOn: '2027-01-28', state: 'used', use: brief },
		{ id: 2, seq: 2, code: 'A1-0412-02', content: 'Kit examen', packaging: 'sachet', expiresOn: '2027-01-28', state: 'usable', use: null }
	]
};

beforeEach(() => {
	i18n.setLocale('fr');
	clock.now = () => new Date('2026-10-30T10:10:00+01:00');
});

describe('Traçabilité stérilisation in the appointment (spec stock-hygiène 5.3)', () => {
	beforeEach(() => auth.set('tok', dentist));

	it('stays folded, then notes a pack by a tap or by its code, and takes it back', async () => {
		mockApi({
			'GET /api/hygiene/pack-uses?appointmentId=30': () => json(200, []),
			'GET /api/hygiene/packs': () => json(200, [found('A1-0412-02'), found('A1-0412-03')]),
			'POST /api/hygiene/pack-uses': () => json(201, used('A1-0412-02')),
			'DELETE /api/hygiene/pack-uses/50': () => noContent()
		});
		render(SterileTrace, { props: { appointmentId: 30 } });
		expect(calls()).toEqual([]);
		await fireEvent.click(screen.getByRole('button', { name: 'Traçabilité stérilisation' }));
		const region = within(await screen.findByRole('region', { name: 'Paquets stérilisés utilisés' }));
		const ready = within(await region.findByRole('list', { name: 'Paquets à utiliser' }));
		await fireEvent.click(ready.getByRole('button', { name: /A1-0412-02/ }));
		await vi.waitFor(() => expect(sentJson('POST /api/hygiene/pack-uses')).toEqual({ code: 'A1-0412-02', appointmentId: 30 }));
		expect(await region.findByText('A1-0412-02 (Kit examen) noté pour ce patient.')).toBeInTheDocument();
		expect(within(region.getByRole('list', { name: 'Paquets notés pour ce rendez-vous' })).getByText('A1-0412-02')).toBeInTheDocument();
		// taking it back asks why – the reason goes into the change log (review M1)
		await fireEvent.click(region.getByRole('button', { name: 'Retirer A1-0412-02' }));
		await fireEvent.click(region.getByRole('button', { name: 'Confirmer le retrait' }));
		expect(await region.findByRole('alert')).toHaveTextContent('Indiquez le motif.');
		expect(calls().some((c) => c.startsWith('DELETE'))).toBe(false);
		await fireEvent.click(region.getByRole('button', { name: 'Mauvais paquet' }));
		expect(region.getByLabelText('Motif du retrait')).toHaveValue('Mauvais paquet');
		await fireEvent.click(region.getByRole('button', { name: 'Confirmer le retrait' }));
		expect(await region.findByText('A1-0412-02 retiré.')).toBeInTheDocument();
		expect(sentJson('DELETE /api/hygiene/pack-uses/50')).toEqual({ reason: 'Mauvais paquet' });
		expect(labelInNameProblems()).toEqual([]);
	});

	it('lets the desk keep a pack after all, and says why a pack of a cancelled cycle or a used one is refused', async () => {
		mockApi({
			'GET /api/hygiene/pack-uses?appointmentId=30': () => json(200, [used('A1-0412-02')]),
			'GET /api/hygiene/packs': () => json(200, []),
			'GET /api/hygiene/packs?q=0001': () =>
				json(200, [
					found('A1-0001-01', 'cancelled', { number: 1, cancelReason: 'Saisi deux fois' }),
					found('A1-0001-02', 'used', { number: 1, use: { ...brief, patientId: null, patientName: null, patientNo: null, appointmentId: null } })
				])
		});
		render(SterileTrace, { props: { appointmentId: 30 } });
		await fireEvent.click(screen.getByRole('button', { name: 'Traçabilité stérilisation' }));
		const region = within(await screen.findByRole('region', { name: 'Paquets stérilisés utilisés' }));
		await fireEvent.click(await region.findByRole('button', { name: 'Retirer A1-0412-02' }));
		await fireEvent.input(region.getByLabelText('Motif du retrait'), { target: { value: 'Erreur' } });
		await fireEvent.click(region.getByRole('button', { name: 'Garder' }));
		expect(region.queryByLabelText('Motif du retrait')).toBeNull();
		expect(calls().some((c) => c.startsWith('DELETE'))).toBe(false);
		await fireEvent.input(region.getByLabelText('Code du paquet'), { target: { value: '0001' } });
		expect(await region.findByText('Cycle annulé (Saisi deux fois) : étiquette plus valable.')).toBeInTheDocument();
		expect(region.getByText('Déjà utilisé.')).toBeInTheDocument(); // whom it went to is the owner's to see
	});

	it('refuses an expired pack with the date and says why before a tap', async () => {
		mockApi({
			'GET /api/hygiene/pack-uses?appointmentId=30': () => json(200, []),
			'GET /api/hygiene/packs': () => json(200, []),
			'GET /api/hygiene/packs?q=A1-0380-01': () => json(200, [found('A1-0380-01', 'expired', { expiresOn: '2026-10-20' })]),
			'POST /api/hygiene/pack-uses': () =>
				new Response(JSON.stringify({ status: 422, code: 'pack_expired', title: 'x', detail: 'x', expiresOn: '2026-10-20' }), {
					status: 422,
					headers: { 'Content-Type': 'application/problem+json' }
				})
		});
		render(SterileTrace, { props: { appointmentId: 30 } });
		await fireEvent.click(screen.getByRole('button', { name: 'Traçabilité stérilisation' }));
		const region = within(await screen.findByRole('region', { name: 'Paquets stérilisés utilisés' }));
		const input = await region.findByLabelText('Code du paquet');
		await fireEvent.input(input, { target: { value: 'A1-0380-01' } });
		expect(await region.findByText('Périmé depuis le 20/10/2026 : ne pas l’utiliser, le restériliser.')).toBeInTheDocument();
		await fireEvent.click(region.getByRole('button', { name: 'Noter' }));
		expect(await region.findByRole('alert')).toHaveTextContent('Paquet périmé (à utiliser avant le 20/10/2026) : ne l’utilisez pas, restérilisez-le.');
	});
});

describe('a new sterilisation cycle', () => {
	beforeEach(() => auth.set('tok', assistant));

	it('fills in the autoclave and its number, adds packs in taps and sends the cycle', async () => {
		mockApi({
			'GET /api/hygiene/cycles/setup': () => json(200, setup),
			'POST /api/hygiene/cycles': () => json(201, cycle)
		});
		const onsaved = vi.fn();
		render(CycleDialog, { props: { settings, onsaved, onclose: vi.fn() } });
		const dialog = within(await screen.findByRole('dialog', { name: 'Nouveau cycle de stérilisation' }));
		expect(await dialog.findByText('Autoclave Melag')).toBeInTheDocument();
		expect(dialog.getByLabelText('N° de cycle')).toHaveValue(413);
		expect(dialog.getByLabelText('Programme')).toHaveValue('134 °C – 18 min');
		await fireEvent.click(dialog.getByLabelText('Conforme'));
		const quick = within(dialog.getByRole('group', { name: 'Ajouter un paquet type' }));
		await fireEvent.click(quick.getByRole('button', { name: 'Kit examen' }));
		await fireEvent.click(quick.getByRole('button', { name: 'Kit examen' }));
		await fireEvent.click(quick.getByRole('button', { name: 'Kit extraction' }));
		await fireEvent.change(dialog.getAllByLabelText('Emballage')[1], { target: { value: 'double_sachet' } });
		expect(dialog.getByText('3 paquet(s), une étiquette chacun.')).toBeInTheDocument();
		expect(dialog.getByText('Double sachet : à utiliser avant le 28/04/2027')).toBeInTheDocument();
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer et imprimer 3 étiquette(s)' }));
		await vi.waitFor(() => expect(onsaved).toHaveBeenCalledWith(cycle));
		// the proposed number untouched: the server gives the next one under its lock (review Ni1)
		expect(sentJson('POST /api/hygiene/cycles')).toEqual({
			equipmentId: 4, number: null, runAt: '2026-10-30T10:10:00+01:00', program: '134 °C – 18 min', result: 'ok',
			packs: [{ content: 'Kit examen', packaging: 'sachet', quantity: 2 }, { content: 'Kit extraction', packaging: 'double_sachet', quantity: 1 }],
			packCount: null, note: '', performedById: 5
		});
		expect(labelInNameProblems()).toEqual([]);
	});

	it('names who ran the cycle – by default the signed-in person (review N6)', async () => {
		mockApi({
			'GET /api/hygiene/cycles/setup': () => json(200, setup),
			'POST /api/hygiene/cycles': () => json(201, cycle)
		});
		render(CycleDialog, { props: { settings, onsaved: vi.fn(), onclose: vi.fn() } });
		const dialog = within(await screen.findByRole('dialog'));
		const who = await dialog.findByLabelText('Fait par');
		expect(who).toHaveValue('5');
		await fireEvent.change(who, { target: { value: '2' } });
		await fireEvent.click(dialog.getByLabelText('Conforme'));
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer le cycle' }));
		await vi.waitFor(() => expect(sentJson('POST /api/hygiene/cycles')).toMatchObject({ performedById: 2, packs: [] }));
	});

	it('never drops a pack line without a content: it asks for it, and counts only the packs it will print (review N2)', async () => {
		mockApi({
			'GET /api/hygiene/cycles/setup': () => json(200, setup),
			'POST /api/hygiene/cycles': () => json(201, cycle)
		});
		render(CycleDialog, { props: { settings, onsaved: vi.fn(), onclose: vi.fn() } });
		const dialog = within(await screen.findByRole('dialog'));
		await fireEvent.click(await dialog.findByLabelText('Conforme'));
		await fireEvent.click(dialog.getByRole('group', { name: 'Ajouter un paquet type' }).querySelector('button')!);
		await fireEvent.click(dialog.getByRole('button', { name: 'Autre contenu' }));
		expect(dialog.getByRole('button', { name: 'Enregistrer et imprimer 1 étiquette(s)' })).toBeInTheDocument();
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer et imprimer 1 étiquette(s)' }));
		expect(await dialog.findByRole('alert')).toHaveTextContent('Indiquez le contenu du paquet 2, ou retirez la ligne.');
		expect(calls().some((c) => c.startsWith('POST'))).toBe(false);
		await fireEvent.input(dialog.getByLabelText('Contenu du paquet 2'), { target: { value: 'Plateau ortho' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer et imprimer 2 étiquette(s)' }));
		await vi.waitFor(() => expect(sentJson('POST /api/hygiene/cycles')).toMatchObject({ packs: [{ content: 'Kit examen' }, { content: 'Plateau ortho' }] }));
	});

	it('records a non conforme cycle without labels; a number taken meanwhile brings the new proposal (review Ni1)', async () => {
		let taken = false;
		const fetch = mockApi({
			'GET /api/hygiene/cycles/setup': () => json(200, taken ? { ...setup, autoclaves: [{ ...setup.autoclaves[0], nextNumber: 415 }] } : setup),
			'POST /api/hygiene/cycles': () => (taken ? json(201, cycle) : ((taken = true), problem(409, 'cycle_number_taken')))
		});
		const onsaved = vi.fn();
		render(CycleDialog, { props: { settings, onsaved, onclose: vi.fn() } });
		const dialog = within(await screen.findByRole('dialog'));
		const field = await dialog.findByLabelText('N° de cycle');
		await fireEvent.input(field, { target: { value: '414' } }); // read on the autoclave – somebody entered it meanwhile
		await fireEvent.click(dialog.getByLabelText('Non conforme'));
		expect(dialog.getByText('Pas d’étiquette pour ce cycle : ses paquets ne sont pas stériles. Recommencez le cycle.')).toBeInTheDocument();
		await fireEvent.input(dialog.getByLabelText('Paquets dans la charge'), { target: { value: '6' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer le cycle non conforme' }));
		expect(await dialog.findByRole('status')).toHaveTextContent(
			'Le n° 414 existe déjà pour cet autoclave. Nouveau n° proposé : 415 – vérifiez-le sur l’autoclave, puis enregistrez.'
		);
		expect(field).toHaveValue(415);
		expect(sentJson('POST /api/hygiene/cycles')).toMatchObject({ number: 414, result: 'not_ok', packs: [], packCount: 6 });
		const again = dialog.getByRole('button', { name: 'Enregistrer le cycle non conforme' });
		await vi.waitFor(() => expect(again).toBeEnabled());
		await fireEvent.click(again);
		await vi.waitFor(() => expect(onsaved).toHaveBeenCalledWith(cycle));
		const posts = fetch.mock.calls.filter(([url, init]) => url === '/api/hygiene/cycles' && init?.method === 'POST');
		expect(JSON.parse(posts[1][1]!.body as string)).toMatchObject({ number: null, packCount: 6 });
	});

	it('asks before saving a number far from the proposal – a cancel goes back to the field (review Mi2)', async () => {
		mockApi({
			'GET /api/hygiene/cycles/setup': () => json(200, setup),
			'POST /api/hygiene/cycles': () => json(201, cycle)
		});
		render(CycleDialog, { props: { settings, onsaved: vi.fn(), onclose: vi.fn() } });
		const dialog = within(await screen.findByRole('dialog'));
		const field = await dialog.findByLabelText('N° de cycle');
		await fireEvent.input(field, { target: { value: '4130' } });
		await fireEvent.click(dialog.getByLabelText('Conforme'));
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer le cycle' }));
		const question = await dialog.findByRole('group', { name: 'N° 4130 – le prochain attendu est 413. Confirmer ?' });
		expect(within(question).getByRole('button', { name: 'Oui, n° 4130' })).toHaveFocus();
		expect(calls().some((c) => c.startsWith('POST'))).toBe(false);
		await fireEvent.click(within(question).getByRole('button', { name: 'Corriger le n°' }));
		expect(field).toHaveFocus();
		expect(dialog.queryByRole('group', { name: /le prochain attendu/ })).toBeNull();
		// downwards as well
		await fireEvent.input(field, { target: { value: '407' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer le cycle' }));
		expect(await dialog.findByRole('group', { name: 'N° 407 – le prochain attendu est 413. Confirmer ?' })).toBeInTheDocument();
		// typing again closes the question; 5 away from the proposal is a plain cycle forgotten or skipped
		await fireEvent.input(field, { target: { value: '408' } });
		expect(dialog.queryByRole('group', { name: /le prochain attendu/ })).toBeNull();
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer le cycle' }));
		await vi.waitFor(() => expect(sentJson('POST /api/hygiene/cycles')).toMatchObject({ number: 408 }));
	});

	it('saves a number far from the proposal once it is confirmed (review Mi2)', async () => {
		mockApi({
			'GET /api/hygiene/cycles/setup': () => json(200, setup),
			'POST /api/hygiene/cycles': () => json(201, cycle)
		});
		const onsaved = vi.fn();
		render(CycleDialog, { props: { settings, onsaved, onclose: vi.fn() } });
		const dialog = within(await screen.findByRole('dialog'));
		await fireEvent.input(await dialog.findByLabelText('N° de cycle'), { target: { value: '4130' } });
		await fireEvent.click(dialog.getByLabelText('Conforme'));
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer le cycle' }));
		await fireEvent.click(await dialog.findByRole('button', { name: 'Oui, n° 4130' }));
		await vi.waitFor(() => expect(onsaved).toHaveBeenCalledWith(cycle));
		expect(sentJson('POST /api/hygiene/cycles')).toMatchObject({ number: 4130 });
		expect(calls().filter((c) => c.startsWith('POST'))).toHaveLength(1);
		expect(labelInNameProblems()).toEqual([]);
	});

	it('asks to check the number of the first cycle of an autoclave, from which the next ones count (review Mi2)', async () => {
		mockApi({
			'GET /api/hygiene/cycles/setup': () =>
				json(200, { ...setup, autoclaves: [{ id: 4, name: 'Autoclave Melag', labelCode: null, nextNumber: 1, lastRunAt: null }] }),
			'POST /api/hygiene/cycles': () => json(201, cycle)
		});
		render(CycleDialog, { props: { settings, onsaved: vi.fn(), onclose: vi.fn() } });
		const dialog = within(await screen.findByRole('dialog'));
		const field = await dialog.findByLabelText('N° de cycle');
		expect(field).toHaveValue(1);
		await fireEvent.input(field, { target: { value: '412' } });
		await fireEvent.click(dialog.getByLabelText('Conforme'));
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer le cycle' }));
		const question = await dialog.findByRole('group', {
			name: 'N° 412 : premier cycle de cet autoclave dans Daftar, les suivants partiront de ce numéro. Est-ce bien le n° affiché par l’autoclave ?'
		});
		await fireEvent.click(within(question).getByRole('button', { name: 'Oui, n° 412' }));
		await vi.waitFor(() => expect(sentJson('POST /api/hygiene/cycles')).toMatchObject({ number: 412 }));
	});

	it('adds the first autoclave of the practice from the dialog', async () => {
		let first = true;
		mockApi({
			'GET /api/hygiene/cycles/setup': () => json(200, first ? ((first = false), { ...setup, autoclaves: [] }) : setup),
			'POST /api/hygiene/equipment': () => json(201, { id: 4 })
		});
		render(CycleDialog, { props: { settings, onsaved: vi.fn(), onclose: vi.fn() } });
		const dialog = within(await screen.findByRole('dialog'));
		await fireEvent.input(await dialog.findByLabelText('Nom de l’autoclave'), { target: { value: 'Autoclave Melag' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Ajouter l’autoclave' }));
		expect(await dialog.findByLabelText('N° de cycle')).toHaveValue(413);
		expect(sentJson('POST /api/hygiene/equipment')).toEqual({ name: 'Autoclave Melag', kind: 'autoclave' });
	});
});

describe('specimen labels', () => {
	beforeEach(() => auth.set('tok', assistant));

	it('counts the tubes and opens the label page', async () => {
		mockApi({ 'POST /api/labels/specimens': () => json(201, { id: 1042 }) });
		render(SpecimenForm, { props: { patientId: 7, birthDate: null } });
		await fireEvent.click(screen.getByRole('button', { name: 'Étiquettes de prélèvement' }));
		expect(screen.getByText(/Date de naissance non renseignée/)).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Un de plus – Sang EDTA' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Un de plus – Sang EDTA' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Un de plus – Autre' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Préparer 3 étiquette(s)' }));
		expect(await screen.findByRole('alert')).toHaveTextContent('Nommez le prélèvement « Autre ».');
		await fireEvent.input(screen.getByLabelText('Nom du prélèvement « Autre »'), { target: { value: 'Pus' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Préparer 3 étiquette(s)' }));
		await vi.waitFor(() => expect(deps.goto).toHaveBeenCalledWith('/app/etiquettes?specimen=1042'));
		expect(sentJson('POST /api/labels/specimens')).toEqual({
			patientId: 7, appointmentId: null,
			items: [{ kind: 'edta', count: 2, label: '' }, { kind: 'autre', count: 1, label: 'Pus' }],
			collectedAt: '2026-10-30T10:10:00+01:00', collectedBy: 'Salma'
		});
		expect(labelInNameProblems()).toEqual([]);
	});

	it('takes "now" when the tubes are prepared, not when the file was opened (review M2)', async () => {
		mockApi({ 'POST /api/labels/specimens': () => json(201, { id: 1043 }) });
		clock.now = () => new Date('2026-10-30T08:40:00+01:00');
		render(SpecimenForm, { props: { patientId: 7, birthDate: '1978-03-12' } });
		clock.now = () => new Date('2026-10-30T09:25:00+01:00'); // the blood is taken 45 minutes later
		await fireEvent.click(screen.getByRole('button', { name: 'Étiquettes de prélèvement' }));
		expect(screen.getByLabelText('Heure')).toHaveValue('09:25');
		await fireEvent.click(screen.getByRole('button', { name: 'Un de plus – Sang EDTA' }));
		clock.now = () => new Date('2026-10-30T09:31:00+01:00');
		await fireEvent.click(screen.getByRole('button', { name: 'Préparer 1 étiquette(s)' }));
		await vi.waitFor(() => expect(sentJson('POST /api/labels/specimens')).toMatchObject({ collectedAt: '2026-10-30T09:31:00+01:00' }));
	});

	it('keeps a time the user typed, and shows "now" moving on while the form stays open', async () => {
		vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
		try {
			mockApi({ 'POST /api/labels/specimens': () => json(201, { id: 1044 }) });
			clock.now = () => new Date('2026-10-30T23:59:00+01:00');
			render(SpecimenForm, { props: { patientId: 7, birthDate: '1978-03-12' } });
			await fireEvent.click(screen.getByRole('button', { name: 'Étiquettes de prélèvement' }));
			clock.now = () => new Date('2026-10-31T00:02:00+01:00'); // a tab left open over midnight
			await vi.advanceTimersByTimeAsync(30_000);
			expect(screen.getByLabelText('Date du prélèvement')).toHaveValue('2026-10-31');
			expect(screen.getByLabelText('Heure')).toHaveValue('00:02');
			await fireEvent.input(screen.getByLabelText('Heure'), { target: { value: '07:15' } });
			clock.now = () => new Date('2026-10-31T09:00:00+01:00');
			await vi.advanceTimersByTimeAsync(30_000);
			expect(screen.getByLabelText('Heure')).toHaveValue('07:15');
			await fireEvent.click(screen.getByRole('button', { name: 'Un de plus – Urine' }));
			await fireEvent.click(screen.getByRole('button', { name: 'Préparer 1 étiquette(s)' }));
			await vi.waitFor(() => expect(sentJson('POST /api/labels/specimens')).toMatchObject({ collectedAt: '2026-10-31T07:15:00+01:00' }));
		} finally {
			vi.useRealTimers();
		}
	});
});

describe('the owner cancels a cycle entered by mistake (review H1)', () => {
	beforeEach(() => auth.set('tok', owner));

	it('asks once more, with the reason, and says to throw its labels away', async () => {
		const cancelled = { ...cycle, packs: [cycle.packs[1]], cancelledAt: '2026-10-30T10:10:00+01:00', cancelledBy: 'Amira Ben Salah', cancelReason: 'Saisi deux fois' };
		mockApi({ 'POST /api/hygiene/cycles/3/cancel': () => json(200, cancelled) });
		const onsaved = vi.fn();
		render(CycleCorrection, { props: { cycle: { ...cycle, packs: [cycle.packs[1]] }, onsaved, onclose: vi.fn() } });
		const dialog = within(await screen.findByRole('dialog', { name: 'Corriger le cycle' }));
		await fireEvent.click(dialog.getByRole('button', { name: 'Annuler ce cycle (saisi par erreur)…' }));
		expect(dialog.getByText(/Retirez des paquets les étiquettes déjà imprimées et jetez-les/)).toBeInTheDocument();
		await fireEvent.click(dialog.getByRole('button', { name: 'Oui, annuler le cycle' }));
		expect(await dialog.findByRole('alert')).toHaveTextContent('Indiquez le motif.');
		await fireEvent.input(dialog.getByLabelText('Motif'), { target: { value: 'Saisi deux fois' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Oui, annuler le cycle' }));
		await vi.waitFor(() => expect(onsaved).toHaveBeenCalledWith('Cycle annulé. Jetez ses étiquettes déjà imprimées.', cancelled));
		expect(sentJson('POST /api/hygiene/cycles/3/cancel')).toEqual({ reason: 'Saisi deux fois' });
		expect(screen.getByRole('button', { name: 'Retour' })).toBeInTheDocument(); // never two buttons called "Annuler"
	});

	it('offers no cancellation once a pack of the cycle was used', async () => {
		render(CycleCorrection, { props: { cycle, onsaved: vi.fn(), onclose: vi.fn() } });
		const dialog = within(await screen.findByRole('dialog', { name: 'Corriger le cycle' }));
		expect(dialog.queryByRole('button', { name: /Annuler ce cycle/ })).toBeNull();
		expect(dialog.getByText(/le cycle ne peut plus être annulé/)).toBeInTheDocument();
	});
});

describe('tab Stérilisation of /app/hygiene', () => {
	it('lists the cycles with their packs and lets the owner trace a pack and correct a cycle', async () => {
		auth.set('tok', owner);
		mockApi({
			'GET /api/labels/settings': () => json(200, settings),
			'GET /api/hygiene/cycles?from=2026-10-01&to=2026-10-30': () => json(200, { from: '2026-10-01', to: '2026-10-30', cycles: [cycle] }),
			'GET /api/hygiene/trace?code=A1-0412-01': () => json(200, { pack: found('A1-0412-01', 'used'), use: used('A1-0412-01') })
		});
		render(SterilizationTab);
		const list = within(await screen.findByRole('list', { name: 'Cycles de stérilisation' }));
		expect(list.getByText('2 paquet(s) : 1 à utiliser, 1 utilisé(s), 0 périmé(s)')).toBeInTheDocument();
		expect(list.getByRole('link', { name: 'Étiquettes' })).toHaveAttribute('href', '/app/etiquettes?cycle=3');
		await fireEvent.click(list.getByRole('button', { name: 'Voir les paquets' }));
		const packs = within(list.getByRole('list', { name: 'Paquets du cycle A1 n° 412' }));
		expect(packs.getByRole('link', { name: 'Sami Trabelsi' })).toHaveAttribute('href', '/app/patients/7');
		expect(list.getByRole('button', { name: 'Corriger – cycle A1 n° 412' })).toBeInTheDocument();
		const trace = within(screen.getByRole('region', { name: 'Traçabilité' }));
		await fireEvent.input(trace.getByLabelText('Code du paquet'), { target: { value: 'A1-0412-01' } });
		await fireEvent.click(trace.getByRole('button', { name: 'Rechercher' }));
		expect(await trace.findByRole('link', { name: 'Sami Trabelsi' })).toHaveAttribute('href', '/app/patients/7');
		expect(trace.getByText('le 30/10/2026 09:05, noté par Karim')).toBeInTheDocument();
		expect(labelInNameProblems()).toEqual([]);
	});

	it('shows no traceability search and no correction to the assistant', async () => {
		auth.set('tok', assistant);
		mockApi({
			'GET /api/labels/settings': () => json(200, settings),
			'GET /api/hygiene/cycles?from=2026-10-01&to=2026-10-30': () => json(200, { from: '2026-10-01', to: '2026-10-30', cycles: [] })
		});
		render(SterilizationTab);
		expect(await screen.findByText(/Aucun cycle sur cette période/)).toBeInTheDocument();
		expect(screen.queryByRole('region', { name: 'Traçabilité' })).toBeNull();
		expect(screen.getByRole('button', { name: 'Réglages des étiquettes' })).toBeInTheDocument();
	});

	it('keeps a cancelled cycle in the list, marked, without labels; the desk sees a pack used, not for whom', async () => {
		auth.set('tok', assistant);
		const hidden = { ...brief, patientId: null, patientName: null, patientNo: null, appointmentId: null };
		const gone: Cycle = {
			...cycle, id: 4, number: 413, cancelledAt: '2026-10-30T09:30:00+01:00', cancelledBy: 'Amira Ben Salah', cancelReason: 'Saisi deux fois',
			packs: cycle.packs.map((p) => ({ ...p, id: p.id + 10, code: p.code.replace('0412', '0413'), state: 'cancelled' as const, use: null }))
		};
		const real: Cycle = { ...cycle, performedBy: 'Salma', recordedBy: 'Amira Ben Salah', packs: [{ ...cycle.packs[0], use: hidden }, cycle.packs[1]] };
		mockApi({
			'GET /api/labels/settings': () => json(200, settings),
			'GET /api/hygiene/cycles?from=2026-10-01&to=2026-10-30': () => json(200, { from: '2026-10-01', to: '2026-10-30', cycles: [gone, real] })
		});
		render(SterilizationTab);
		const list = within(await screen.findByRole('list', { name: 'Cycles de stérilisation' }));
		expect(screen.getByText('1 cycle(s), dont 0 non conforme(s) – 2 paquet(s)')).toBeInTheDocument();
		expect(screen.getByText('1 cycle(s) annulé(s), hors total')).toBeInTheDocument();
		expect(list.getByText('Annulé le 30/10/2026 09:30 par Amira Ben Salah : Saisi deux fois')).toBeInTheDocument();
		expect(list.getAllByRole('link', { name: 'Étiquettes' })).toHaveLength(1); // only the real cycle prints
		expect(list.getByText(/saisi par Amira Ben Salah/)).toBeInTheDocument();
		await fireEvent.click(list.getAllByRole('button', { name: 'Voir les paquets' })[1]);
		const packs = within(list.getByRole('list', { name: 'Paquets du cycle A1 n° 412' }));
		expect(packs.queryByRole('link')).toBeNull();
		expect(packs.getByText(/utilisé le 30\/10\/2026/)).toBeInTheDocument();
		expect(labelInNameProblems()).toEqual([]);
	});
});
