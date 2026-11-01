import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { clock } from '#lib/clock';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, labelInNameProblems, mockApi, noContent, sentJson, type Handler } from '#lib/test-utils';
import { assistant, NOW, owner } from '#lib/agenda/fixtures';
import { dentist } from '#lib/testing/fixtures';
import type { Equipment, HygieneTask } from '#lib/types/hygiene';

const autoclave: Equipment = { id: 5, name: 'Autoclave', kind: 'autoclave', serialNumber: 'SN-1', note: '', active: true, tasks: 1 };
const bowie: HygieneTask = {
	id: 1, title: 'Test Bowie-Dick', equipmentId: 5, equipmentName: 'Autoclave', frequency: 'weekly', weekday: 1, intervalDays: null,
	startsOn: '2026-10-05', instructions: '', active: true, nextDueOn: '2026-11-02'
};
const today = {
	day: '2026-10-30',
	open: 1,
	items: [{ taskId: 2, title: 'Purge des conduits', equipmentName: null, frequency: 'daily', instructions: '', dueOn: '2026-10-30', state: 'due', done: null }]
};

function hygieneApi(extra: Record<string, Handler> = {}) {
	return mockApi({
		'GET /api/hygiene/today': () => json(200, today),
		'GET /api/hygiene/equipment': () => json(200, [autoclave]),
		'GET /api/hygiene/tasks': () => json(200, [bowie]),
		'GET /api/badges': () => json(200, { onlineRequests: 0, overdue: 0, hygiene: 1 }),
		...extra
	});
}

describe('/app/hygiene – tasks of the day, plan, history', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
		clock.now = () => new Date(NOW);
		history.replaceState(null, '', '/app/hygiene');
	});

	it('opens on the tasks of the day', async () => {
		hygieneApi();
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'Hygiène' })).toBeInTheDocument();
		const list = within(await screen.findByRole('list', { name: 'Tâches du jour' }));
		expect(list.getByText('Purge des conduits')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Aujourd’hui' })).toHaveAttribute('aria-pressed', 'true');
	});

	it('sets up the plan: equipment and a weekly task', async () => {
		hygieneApi({
			'POST /api/hygiene/tasks': () => json(201, { ...bowie, id: 3, title: 'Purge du compresseur', weekday: 5, equipmentId: null, equipmentName: null, nextDueOn: '2026-10-30' })
		});
		history.replaceState(null, '', '/app/hygiene?tab=taches');
		render(Page);
		const tasks = within(await screen.findByRole('list', { name: 'Tâches' }));
		expect(tasks.getByText('Test Bowie-Dick')).toBeInTheDocument();
		expect(tasks.getByText(/Chaque lundi/)).toBeInTheDocument();
		expect(tasks.getByText(/Prochaine fois : 02\/11\/2026/)).toBeInTheDocument();
		expect(within(screen.getByRole('list', { name: 'Équipements' })).getByText('Autoclave')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Nouvelle tâche' }));
		const dialog = within(screen.getByRole('dialog', { name: 'Nouvelle tâche' }));
		await fireEvent.input(dialog.getByLabelText('Tâche'), { target: { value: 'Purge du compresseur' } });
		await fireEvent.change(dialog.getByLabelText('Fréquence'), { target: { value: 'weekly' } });
		await fireEvent.change(dialog.getByLabelText('Jour'), { target: { value: '5' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer la tâche' }));
		expect(sentJson('POST /api/hygiene/tasks')).toEqual({
			title: 'Purge du compresseur',
			equipmentId: null,
			frequency: 'weekly',
			weekday: 5,
			intervalDays: null,
			startsOn: '2026-10-30',
			instructions: ''
		});
		expect(await tasks.findByText('Purge du compresseur')).toBeInTheDocument();
	});

	it('proposes the plan of the specialty when there is none', async () => {
		let listed: HygieneTask[] = [];
		hygieneApi({
			'GET /api/hygiene/tasks': () => json(200, listed),
			'GET /api/hygiene/equipment': () => json(200, []),
			'POST /api/hygiene/starter': () => {
				listed = [bowie];
				return json(200, { equipment: 6, tasks: 9 });
			}
		});
		history.replaceState(null, '', '/app/hygiene?tab=taches');
		render(Page);
		await fireEvent.click(await screen.findByRole('button', { name: 'Proposer un plan d’hygiène' }));
		expect(await screen.findByText('6 équipement(s) et 9 tâche(s) ajoutés.')).toBeInTheDocument();
		expect(await screen.findByText('Test Bowie-Dick')).toBeInTheDocument();
	});

	it('shows the history as a register that can be printed', async () => {
		const print = vi.spyOn(window, 'print').mockImplementation(() => undefined);
		hygieneApi({
			'GET /api/hygiene/history?from=2026-10-01&to=2026-10-30': () =>
				json(200, {
					from: '2026-10-01',
					to: '2026-10-30',
					rows: [
						{ dueOn: '2026-10-29', taskId: 2, title: 'Purge des conduits', equipmentName: null, status: 'missed', late: false, done: null },
						{ dueOn: '2026-10-26', taskId: 1, title: 'Test Bowie-Dick', equipmentName: 'Autoclave', status: 'done', late: true, done: { id: 9, doneBy: 'Nisrine', doneAt: '2026-10-27T08:10:00+01:00', result: 'not_ok', note: 'Indicateur non viré' } }
					]
				})
		});
		history.replaceState(null, '', '/app/hygiene?tab=historique');
		render(Page);
		const table = within(await screen.findByRole('table', { name: 'Registre d’hygiène' }));
		const missed = table.getByRole('row', { name: /Purge des conduits/ });
		expect(missed).toHaveTextContent('Non fait');
		const done = table.getByRole('row', { name: /Test Bowie-Dick/ });
		expect(done).toHaveTextContent('Non conforme');
		expect(done).toHaveTextContent('Nisrine');
		expect(done).toHaveTextContent('fait le 27/10/2026');
		expect(done).toHaveTextContent('Indicateur non viré');
		expect(screen.getByText('1 fait(s), 1 non fait(s), 0 en retard')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Imprimer' }));
		expect(print).toHaveBeenCalled();
		print.mockRestore();
	});

	it('lets the dentist tick but not change the plan', async () => {
		auth.set('tok', dentist);
		hygieneApi();
		history.replaceState(null, '', '/app/hygiene?tab=taches');
		render(Page);
		expect(await screen.findByText('Les équipements et les tâches sont réglés par l’assistante ou le titulaire.')).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Nouvelle tâche' })).not.toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Proposer un plan d’hygiène' })).not.toBeInTheDocument();
	});

	it('lets the owner correct a proof of the register and reads the change log in words (review N8, M3)', async () => {
		auth.set('tok', owner);
		const rows = [
			{ dueOn: '2026-10-30', taskId: 2, title: 'Purge des conduits', equipmentName: null, status: 'due', late: false, done: null },
			{ dueOn: '2026-10-26', taskId: 1, title: 'Test Bowie-Dick', equipmentName: 'Autoclave', status: 'done', late: false, done: { id: 9, doneBy: 'Karim', doneAt: '2026-10-26T08:10:00+01:00', result: 'ok', note: '' } },
			{ dueOn: '2026-10-19', taskId: 1, title: 'Test Bowie-Dick', equipmentName: 'Autoclave', status: 'overdue', late: false, done: null }
		];
		hygieneApi({
			'GET /api/hygiene/history?from=2026-10-01&to=2026-10-30': () => json(200, { from: '2026-10-01', to: '2026-10-30', rows }),
			'GET /api/audit-log?entity=hygiene_task,equipment,hygiene_task_done,sterilization_cycle,sterile_pack_use,label_settings&limit=50': () =>
				json(200, [
					{ id: 2, at: '2026-10-30T10:00:00+01:00', userName: 'Amira', entity: 'hygiene_task_done', entityId: 8, action: 'delete',
						before: { task: 'Purge des conduits', dueOn: '2026-10-29', doneBy: 'Salma', result: 'ok', note: '' }, after: null, reason: 'Pas fait en réalité' },
					{ id: 1, at: '2026-10-30T09:00:00+01:00', userName: 'Salma', entity: 'hygiene_task', entityId: 2, action: 'update',
						before: { task: 'Purge des conduits', frequency: 'daily', weekday: null, active: true }, after: { frequency: 'weekly', weekday: 1, active: false }, reason: '' }
				]),
			'PATCH /api/hygiene/done/9': () => json(200, rows[1])
		});
		history.replaceState(null, '', '/app/hygiene?tab=historique');
		render(Page);
		const cards = within(await screen.findByRole('list', { name: 'Registre d’hygiène, une carte par date' }));
		expect(cards.getAllByRole('listitem')).toHaveLength(3);
		expect(cards.getAllByRole('listitem')[2]).toHaveTextContent('En retard');
		expect(screen.getByRole('table', { name: 'Registre d’hygiène' })).toBeInTheDocument(); // tablet and paper
		expect(screen.getByText('1 fait(s), 0 non fait(s), 1 en retard')).toBeInTheDocument();
		const log = within(await screen.findByRole('list', { name: 'Journal des corrections' }));
		expect(log.getByText('30/10/2026 10:00 – Amira a annulé « Purge des conduits » du 29/10/2026 (fait par Salma)')).toBeInTheDocument();
		expect(log.getByText('Motif : Pas fait en réalité')).toBeInTheDocument();
		expect(log.getByText('30/10/2026 09:00 – Salma a modifié la tâche « Purge des conduits »')).toBeInTheDocument();
		expect(log.getByText('Fréquence : Chaque jour d’ouverture → Chaque semaine')).toBeInTheDocument();
		expect(log.getByText('Jour : – → lundi')).toBeInTheDocument();
		expect(log.getByText('Actif : oui → non')).toBeInTheDocument();
		expect(document.body.textContent).not.toMatch(/weekly|daily|not_ok/);
		await fireEvent.click(screen.getAllByRole('button', { name: 'Corriger – Test Bowie-Dick du 26/10/2026' })[0]);
		const dialog = within(screen.getByRole('dialog', { name: 'Corriger la preuve' }));
		await fireEvent.click(dialog.getByLabelText('Non conforme'));
		await fireEvent.input(dialog.getByLabelText('Note'), { target: { value: 'Indicateur non viré' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer la correction' }));
		expect(await dialog.findByRole('alert')).toHaveTextContent('Indiquez le motif.');
		await fireEvent.input(dialog.getByLabelText('Motif'), { target: { value: 'Vu le lendemain' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer la correction' }));
		await vi.waitFor(() => expect(calls()).toContain('PATCH /api/hygiene/done/9'));
		expect(sentJson('PATCH /api/hygiene/done/9')).toEqual({ result: 'not_ok', note: 'Indicateur non viré', reason: 'Vu le lendemain' });
		expect(await screen.findByText('Preuve corrigée.')).toBeInTheDocument();
		expect(labelInNameProblems()).toEqual([]);
	});

	it('takes a proof back with a reason – the date stays in the register', async () => {
		auth.set('tok', owner);
		const done = { dueOn: '2026-10-26', taskId: 1, title: 'Test Bowie-Dick', equipmentName: 'Autoclave', status: 'done', late: false, done: { id: 9, doneBy: 'Karim', doneAt: '2026-10-26T08:10:00+01:00', result: 'ok', note: '' } };
		hygieneApi({
			'GET /api/hygiene/history?from=2026-10-01&to=2026-10-30': () => json(200, { from: '2026-10-01', to: '2026-10-30', rows: [done] }),
			'GET /api/audit-log?entity=hygiene_task,equipment,hygiene_task_done,sterilization_cycle,sterile_pack_use,label_settings&limit=50': () => json(200, []),
			'DELETE /api/hygiene/done/9': () => noContent()
		});
		history.replaceState(null, '', '/app/hygiene?tab=historique');
		render(Page);
		await fireEvent.click((await screen.findAllByRole('button', { name: 'Corriger – Test Bowie-Dick du 26/10/2026' }))[0]);
		const dialog = within(screen.getByRole('dialog', { name: 'Corriger la preuve' }));
		await fireEvent.input(dialog.getByLabelText('Motif'), { target: { value: 'Pas fait en réalité' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Annuler la preuve' }));
		await vi.waitFor(() => expect(calls()).toContain('DELETE /api/hygiene/done/9'));
		expect(sentJson('DELETE /api/hygiene/done/9')).toEqual({ reason: 'Pas fait en réalité' });
		expect(await screen.findByText('Preuve annulée : la date reste dans le registre.')).toBeInTheDocument();
		expect(screen.getByText('Aucune correction pour l’instant.')).toBeInTheDocument();
	});

	it('explains on the task that a change counts from today', async () => {
		hygieneApi();
		history.replaceState(null, '', '/app/hygiene?tab=taches');
		render(Page);
		await fireEvent.click(await screen.findByRole('button', { name: 'Modifier Test Bowie-Dick' }));
		const dialog = within(screen.getByRole('dialog', { name: 'Modifier la tâche' }));
		expect(dialog.getByLabelText('Première fois')).toHaveAccessibleDescription(
			'Une modification compte à partir d’aujourd’hui : ce qui est déjà dans le registre ne change pas.'
		);
	});
});
