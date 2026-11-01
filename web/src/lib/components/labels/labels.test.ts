import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { deps } from '../../api';
import { auth } from '../../auth.svelte';
import { clock } from '../../clock';
import { i18n } from '../../i18n.svelte';
import { calls, json, labelInNameProblems, mockApi, noContent, problem, sentJson } from '../../test-utils';
import { assistant, dentist, owner } from '../../testing/fixtures';
import type { Cycle, CycleSetup, LabelSettings, PackFound, PackUse } from '../../types/labels';
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
	contents: ['Kit examen', 'Kit extraction', 'Kit détartrage']
};
const found = (code: string, state: PackFound['state'] = 'usable', extra: Partial<PackFound> = {}): PackFound => ({
	id: Number(code.slice(-2)), seq: Number(code.slice(-2)), code, content: 'Kit examen', packaging: 'sachet', expiresOn: '2027-01-28', state,
	use: null, cycleId: 3, labelCode: 'A1', number: 412, equipmentName: 'Autoclave Melag', runAt: '2026-10-30T07:45:00+01:00', ...extra
});
const used = (code: string, extra: Partial<PackUse> = {}): PackUse => ({
	id: 50, packId: 1, code, content: 'Kit examen', packaging: 'sachet', expiresOn: '2027-01-28',
	cycle: { id: 3, labelCode: 'A1', number: 412, equipmentName: 'Autoclave Melag', runAt: '2026-10-30T07:45:00+01:00', result: 'ok' },
	patientId: 7, patientName: 'Sami Trabelsi', appointmentId: 30, usedAt: '2026-10-30T09:05:00+01:00', usedBy: 'Karim', undoable: true, ...extra
});
const cycle: Cycle = {
	id: 3, equipmentId: 4, equipmentName: 'Autoclave Melag', labelCode: 'A1', number: 412, runAt: '2026-10-30T07:45:00+01:00',
	program: '134 °C – 18 min', result: 'ok', packCount: 2, note: '', performedBy: 'Salma', initials: 'S', createdAt: '2026-10-30T07:46:00+01:00',
	packs: [
		{ id: 1, seq: 1, code: 'A1-0412-01', content: 'Kit examen', packaging: 'sachet', expiresOn: '2027-01-28', state: 'used',
			use: { id: 50, patientId: 7, patientName: 'Sami Trabelsi', appointmentId: 30, usedAt: '2026-10-30T09:05:00+01:00', usedBy: 'Karim' } },
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
		await fireEvent.click(region.getByRole('button', { name: 'Retirer A1-0412-02' }));
		expect(await region.findByText('A1-0412-02 retiré.')).toBeInTheDocument();
		expect(labelInNameProblems()).toEqual([]);
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
		expect(sentJson('POST /api/hygiene/cycles')).toEqual({
			equipmentId: 4, number: 413, runAt: '2026-10-30T10:10:00+01:00', program: '134 °C – 18 min', result: 'ok',
			packs: [{ content: 'Kit examen', packaging: 'sachet', quantity: 2 }, { content: 'Kit extraction', packaging: 'double_sachet', quantity: 1 }],
			packCount: null, note: ''
		});
		expect(labelInNameProblems()).toEqual([]);
	});

	it('records a non conforme cycle without labels and explains a taken number', async () => {
		mockApi({
			'GET /api/hygiene/cycles/setup': () => json(200, setup),
			'POST /api/hygiene/cycles': () => problem(409, 'cycle_number_taken')
		});
		render(CycleDialog, { props: { settings, onsaved: vi.fn(), onclose: vi.fn() } });
		const dialog = within(await screen.findByRole('dialog'));
		await fireEvent.click(await dialog.findByLabelText('Non conforme'));
		expect(dialog.getByText('Pas d’étiquette pour ce cycle : ses paquets ne sont pas stériles. Recommencez le cycle.')).toBeInTheDocument();
		await fireEvent.input(dialog.getByLabelText('Paquets dans la charge'), { target: { value: '6' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer le cycle non conforme' }));
		expect(await dialog.findByRole('alert')).toHaveTextContent('Ce n° de cycle existe déjà pour cet autoclave.');
		expect(sentJson('POST /api/hygiene/cycles')).toMatchObject({ result: 'not_ok', packs: [], packCount: 6 });
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
});
