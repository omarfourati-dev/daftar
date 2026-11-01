import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import HygieneToday from './HygieneToday.svelte';
import { auth } from '../../auth.svelte';
import { i18n } from '../../i18n.svelte';
import { calls, json, labelInNameProblems, mockApi, noContent, problem, sentJson } from '../../test-utils';
import { assistant, owner } from '../../agenda/fixtures';
import type { HygieneItem, HygieneToday as Today } from '../../types/hygiene';

const overdue: HygieneItem = {
	taskId: 1, title: 'Test Bowie-Dick', equipmentName: 'Autoclave', frequency: 'weekly', instructions: 'Premier cycle, à vide.',
	dueOn: '2026-10-26', state: 'overdue', done: null
};
const due: HygieneItem = { taskId: 2, title: 'Purge des conduits', equipmentName: 'Fauteuil', frequency: 'daily', instructions: '', dueOn: '2026-10-30', state: 'due', done: null };
const data: Today = { day: '2026-10-30', open: 2, items: [overdue, due] };

describe('HygieneToday – big rows to tick (spec stock-hygiène 5.2)', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
	});

	it('shows the overdue task in red on top and ticks a task in one tap', async () => {
		const onchange = vi.fn();
		mockApi({
			'POST /api/hygiene/tasks/2/done': () =>
				json(201, { ...due, state: 'done', done: { id: 40, doneBy: 'Salma', doneAt: '2026-10-30T09:12:00+01:00', result: 'ok', note: '', undoable: true } }),
			'GET /api/badges': () => json(200, { onlineRequests: 0, overdue: 0, hygiene: 1 })
		});
		render(HygieneToday, { props: { data, onchange } });
		const list = within(screen.getByRole('list', { name: 'Tâches du jour' }));
		const rows = list.getAllByRole('listitem');
		expect(rows[0]).toHaveTextContent('Test Bowie-Dick');
		expect(rows[0]).toHaveTextContent('En retard depuis le 26/10/2026');
		expect(rows[0]).toHaveTextContent('Premier cycle, à vide.');
		expect(rows[1]).toHaveTextContent('À faire aujourd’hui');
		await fireEvent.click(within(rows[1]).getByRole('button', { name: 'Fait – Purge des conduits' }));
		expect(sentJson('POST /api/hygiene/tasks/2/done')).toEqual({ dueOn: '2026-10-30', result: 'ok', note: '' });
		expect(await list.findByText(/Fait par Salma à 09:12/)).toBeInTheDocument();
		expect(onchange).toHaveBeenLastCalledWith(expect.objectContaining({ open: 1 }));
		expect(labelInNameProblems()).toEqual([]);
	});

	it('records a failed check with its note, and undoes a wrong tap', async () => {
		mockApi({
			'POST /api/hygiene/tasks/1/done': () =>
				json(201, { ...overdue, state: 'done', done: { id: 41, doneBy: 'Salma', doneAt: '2026-10-30T09:15:00+01:00', result: 'not_ok', note: 'Indicateur non viré', undoable: true } }),
			'DELETE /api/hygiene/done/41': () => noContent(),
			'GET /api/badges': () => json(200, { onlineRequests: 0, overdue: 0, hygiene: 2 })
		});
		render(HygieneToday, { props: { data } });
		const first = within(screen.getAllByRole('listitem')[0]);
		await fireEvent.click(first.getByRole('button', { name: 'Résultat et note – Test Bowie-Dick' }));
		await fireEvent.click(first.getByLabelText('Non conforme'));
		await fireEvent.input(first.getByLabelText('Note'), { target: { value: 'Indicateur non viré' } });
		await fireEvent.click(first.getByRole('button', { name: 'Enregistrer' }));
		expect(sentJson('POST /api/hygiene/tasks/1/done')).toEqual({ dueOn: '2026-10-26', result: 'not_ok', note: 'Indicateur non viré' });
		const undo = await first.findByRole('button', { name: 'Annuler – Test Bowie-Dick' });
		expect(first.getByText('Non conforme')).toBeInTheDocument(); // the badge of the failed check
		expect(first.getByText('Indicateur non viré')).toBeInTheDocument();
		await fireEvent.click(undo);
		expect(await screen.findByText('Annulé : « Test Bowie-Dick » est de nouveau à faire.')).toBeInTheDocument();
		expect(first.getByText(/En retard depuis le 26\/10\/2026/)).toBeInTheDocument();
	});

	it('says when somebody else was quicker, and when everything is done', async () => {
		mockApi({ 'POST /api/hygiene/tasks/2/done': () => problem(409, 'already_done') });
		render(HygieneToday, { props: { data: { ...data, open: 1, items: [due] } } });
		await fireEvent.click(screen.getByRole('button', { name: 'Fait – Purge des conduits' }));
		expect(await screen.findByRole('alert')).toHaveTextContent('Quelqu’un l’a déjà marquée comme faite.');
	});

	it('celebrates nothing but says it plainly when all is done, and guides an empty plan', () => {
		mockApi({});
		const done: HygieneItem = { ...due, state: 'done', done: { id: 3, doneBy: 'Salma', doneAt: '2026-10-30T08:10:00+01:00', result: 'ok', note: '', undoable: false } };
		const { unmount } = render(HygieneToday, { props: { data: { ...data, open: 0, items: [done] } } });
		expect(screen.getByText('Tout est fait pour aujourd’hui.')).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: /Annuler/ })).not.toBeInTheDocument();
		unmount();
		render(HygieneToday, { props: { data: { ...data, open: 0, items: [] } } });
		expect(screen.getByText('Aucune tâche prévue. Créez votre plan d’hygiène dans « Équipements et tâches ».')).toBeInTheDocument();
	});

	it('loads the list again when a colleague was quicker (review N4)', async () => {
		const ticked: HygieneItem = { ...due, state: 'done', done: { id: 44, doneBy: 'Karim', doneAt: '2026-10-30T09:01:00+01:00', result: 'ok', note: '', undoable: false } };
		const onchange = vi.fn();
		mockApi({
			'POST /api/hygiene/tasks/2/done': () => problem(409, 'already_done'),
			'GET /api/hygiene/today': () => json(200, { day: '2026-10-30', open: 0, items: [ticked] }),
			'GET /api/badges': () => json(200, { onlineRequests: 0, overdue: 0, hygiene: 0 })
		});
		render(HygieneToday, { props: { data: { ...data, open: 1, items: [due] }, onchange } });
		await fireEvent.click(screen.getByRole('button', { name: 'Fait – Purge des conduits' }));
		expect(await screen.findByRole('alert')).toHaveTextContent('Quelqu’un l’a déjà marquée comme faite.');
		expect(await screen.findByText(/Fait par Karim à 09:01/)).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Fait – Purge des conduits' })).not.toBeInTheDocument();
		expect(onchange).toHaveBeenLastCalledWith(expect.objectContaining({ open: 0 }));
	});

	it('asks the owner for a reason to undo somebody else’s proof', async () => {
		auth.set('tok', owner);
		const ticked: HygieneItem = { ...due, state: 'done', done: { id: 45, doneBy: 'Karim', doneAt: '2026-10-30T08:01:00+01:00', result: 'ok', note: '', undoable: true } };
		let asked = false;
		mockApi({
			'DELETE /api/hygiene/done/45': (init) => {
				if (!init?.body) {
					asked = true;
					return problem(422, 'reason_required');
				}
				return noContent();
			},
			'GET /api/hygiene/today': () => json(200, { day: '2026-10-30', open: 1, items: [due] }),
			'GET /api/badges': () => json(200, { onlineRequests: 0, overdue: 0, hygiene: 1 })
		});
		render(HygieneToday, { props: { data: { ...data, open: 0, items: [ticked] } } });
		await fireEvent.click(screen.getByRole('button', { name: 'Annuler – Purge des conduits' }));
		const reason = await screen.findByLabelText('Motif de l’annulation');
		expect(asked).toBe(true);
		await fireEvent.input(reason, { target: { value: 'Pas fait en réalité' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Confirmer l’annulation' }));
		await vi.waitFor(() => expect(calls().filter((c) => c === 'DELETE /api/hygiene/done/45')).toHaveLength(2));
		expect(await screen.findByText('Annulé : « Purge des conduits » est de nouveau à faire.')).toBeInTheDocument();
	});
});
