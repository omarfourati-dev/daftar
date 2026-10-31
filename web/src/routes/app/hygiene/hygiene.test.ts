import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { clock } from '#lib/clock';
import { i18n } from '#lib/i18n.svelte';
import { json, mockApi, sentJson, type Handler } from '#lib/test-utils';
import { assistant, NOW } from '#lib/agenda/fixtures';
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
		expect(screen.getByText('1 fait(s), 1 non fait(s)')).toBeInTheDocument();
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
});
