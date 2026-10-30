import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, mockApi, noContent, sentJson } from '#lib/test-utils';
import { assistant, owner, practice } from '#lib/testing/fixtures';

const closures = [
	{ id: 1, startsOn: '2026-08-01', endsOn: '2026-08-15', label: 'Congés d’été' },
	{ id: 2, startsOn: '2026-12-31', endsOn: '2026-12-31', label: 'Réveillon' }
];

describe('/app/reglages/horaires', () => {
	beforeEach(() => {
		i18n.setLocale('fr');
		auth.set('tok', owner);
		vi.useFakeTimers({ toFake: ['Date'] });
		vi.setSystemTime(new Date('2026-10-30T09:00:00+01:00'));
	});
	afterEach(() => vi.useRealTimers());

	it('saves the weekly hours', async () => {
		mockApi({
			'GET /api/practice': () => json(200, practice()),
			'GET /api/closures': () => json(200, []),
			'PATCH /api/practice': () => json(200, practice())
		});
		render(Page);
		await fireEvent.click(await screen.findByRole('checkbox', { name: 'Samedi' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer les horaires' }));
		expect(await screen.findByText('Modifications enregistrées.')).toBeInTheDocument();
		const body = sentJson('PATCH /api/practice') as { weeklyHours: Record<string, unknown[]> };
		expect(Object.keys(body)).toEqual(['weeklyHours']);
		expect(body.weeklyHours['6']).toEqual([]);
	});

	it('refuses to save overlapping windows', async () => {
		mockApi({ 'GET /api/practice': () => json(200, practice()), 'GET /api/closures': () => json(200, []) });
		render(Page);
		await fireEvent.input(await screen.findByLabelText('Lundi – fin de la plage 1'), { target: { value: '15:00' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer les horaires' }));
		expect(screen.getByRole('alert')).toHaveTextContent('Corrigez les horaires signalés avant d’enregistrer.');
		expect(calls()).not.toContain('PATCH /api/practice');
	});

	it('lists upcoming closures, adds and removes one', async () => {
		let list = [...closures];
		mockApi({
			'GET /api/practice': () => json(200, practice()),
			'GET /api/closures': () => json(200, list),
			'POST /api/closures': () => {
				const created = { id: 3, startsOn: '2027-03-20', endsOn: '2027-03-21', label: 'Aïd' };
				list = [...list, created];
				return json(201, created);
			},
			'DELETE /api/closures/2': () => {
				list = list.filter((c) => c.id !== 2);
				return noContent();
			}
		});
		render(Page);
		const upcoming = within(await screen.findByRole('list', { name: 'Fermetures exceptionnelles' }));
		expect(upcoming.getByText('Le 31/12/2026')).toBeInTheDocument();
		expect(upcoming.getByText('Réveillon')).toBeInTheDocument();
		expect(upcoming.queryByText('Congés d’été')).not.toBeInTheDocument(); // in the past (today is after August)
		expect(screen.getByText('Fermetures passées')).toBeInTheDocument();

		await fireEvent.input(screen.getByLabelText('Du'), { target: { value: '2027-03-21' } });
		await fireEvent.input(screen.getByLabelText('Au'), { target: { value: '2027-03-20' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Ajouter la fermeture' }));
		expect(screen.getByLabelText('Au')).toHaveAccessibleDescription('La date de fin doit être le même jour ou après le début.');
		await fireEvent.input(screen.getByLabelText('Du'), { target: { value: '2027-03-20' } });
		await fireEvent.input(screen.getByLabelText('Au'), { target: { value: '2027-03-21' } });
		await fireEvent.input(screen.getByLabelText(/^Motif/), { target: { value: 'Aïd' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Ajouter la fermeture' }));
		expect(await screen.findByText('Du 20/03/2027 au 21/03/2027')).toBeInTheDocument();
		expect(sentJson('POST /api/closures')).toEqual({ startsOn: '2027-03-20', endsOn: '2027-03-21', label: 'Aïd' });

		await fireEvent.click(screen.getByRole('button', { name: 'Supprimer la fermeture le 31/12/2026' }));
		await vi.waitFor(() => expect(screen.queryByText('Réveillon')).not.toBeInTheDocument());
	});

	it('is reserved to the owner', async () => {
		auth.set('tok', assistant);
		mockApi({});
		render(Page);
		expect(screen.getByText('Cette page est réservée au titulaire du cabinet.')).toBeInTheDocument();
		expect(calls()).toEqual([]);
	});
});
