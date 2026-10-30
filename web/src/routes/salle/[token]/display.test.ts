import { render, screen, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { clock } from '#lib/clock';
import { i18n } from '#lib/i18n.svelte';
import { json, mockApi, problem } from '#lib/test-utils';
import { NOW } from '#lib/agenda/fixtures';

const screenData = { practiceName: 'Cabinet du Lac', called: [13, 12], next: [14, 15, 16], waiting: 3 };

describe('/salle/[token] – the waiting-room screen (numbers only)', () => {
	beforeEach(() => {
		auth.clear();
		i18n.setLocale('fr');
		clock.now = () => new Date(NOW);
		history.replaceState(null, '', '/salle/disp-0123');
	});
	afterEach(() => vi.useRealTimers());

	it('shows the called ticket very large, the next ones and how many are waiting, in French and Arabic', async () => {
		mockApi({ 'GET /api/public/display/disp-0123': () => json(200, screenData) });
		render(Page);
		expect(await screen.findByRole('heading', { level: 1, name: 'Cabinet du Lac' })).toBeInTheDocument();
		const called = within(screen.getByRole('region', { name: /Ticket appelé/ }));
		expect(called.getByText('13')).toBeInTheDocument();
		expect(called.getByText('12')).toBeInTheDocument();
		expect(called.getByText('الرقم المنادى')).toBeInTheDocument();
		const next = within(screen.getByRole('region', { name: /Prochains tickets/ }));
		expect(next.getAllByRole('listitem').map((li) => li.textContent?.trim())).toEqual(['14', '15', '16']);
		expect(within(screen.getByRole('region', { name: /Patients en attente/ })).getByText('3')).toBeInTheDocument();
	});

	it('asks the server again every 10 seconds', async () => {
		vi.useFakeTimers({ shouldAdvanceTime: true });
		let data = screenData;
		mockApi({ 'GET /api/public/display/disp-0123': () => json(200, data) });
		render(Page);
		await screen.findByText('13');
		data = { ...screenData, called: [14, 13], next: [15, 16], waiting: 2 };
		await vi.advanceTimersByTimeAsync(10_000);
		expect(await within(screen.getByRole('region', { name: /Ticket appelé/ })).findByText('14')).toBeInTheDocument();
	});

	it('keeps the last numbers when the connection drops', async () => {
		vi.useFakeTimers({ shouldAdvanceTime: true });
		let fail = false;
		mockApi({ 'GET /api/public/display/disp-0123': () => (fail ? problem(503, 'server_error') : json(200, screenData)) });
		render(Page);
		await screen.findByText('13');
		fail = true;
		await vi.advanceTimersByTimeAsync(10_000);
		expect(await screen.findByText('Connexion perdue – nouvel essai dans quelques secondes.')).toBeInTheDocument();
		expect(screen.getByText('13')).toBeInTheDocument();
	});

	it('explains an invalid screen link', async () => {
		mockApi({ 'GET /api/public/display/disp-0123': () => problem(404, 'not_found') });
		render(Page);
		expect(await screen.findByRole('alert')).toHaveTextContent('Ce lien d’écran n’est pas valide.');
	});
});
