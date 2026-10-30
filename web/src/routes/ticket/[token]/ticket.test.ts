import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { clock } from '#lib/clock';
import { i18n } from '#lib/i18n.svelte';
import { json, mockApi, problem } from '#lib/test-utils';
import { NOW } from '#lib/agenda/fixtures';

const waiting = { practiceName: 'Cabinet du Lac', practicePhone: '+21671000000', ticketNo: 15, status: 'waiting', peopleAhead: 2, estimatedWaitMin: 40, day: '2026-10-30' };

describe('/ticket/[token] – the patient follows their turn (no names)', () => {
	beforeEach(() => {
		auth.clear();
		i18n.setLocale('fr');
		clock.now = () => new Date(NOW);
		history.replaceState(null, '', '/ticket/tk-15');
	});
	afterEach(() => vi.useRealTimers());

	it('shows the number, the people ahead and the expected wait', async () => {
		mockApi({ 'GET /api/public/ticket/tk-15': () => json(200, waiting) });
		render(Page);
		expect(await screen.findByText('15')).toBeInTheDocument();
		expect(screen.getByText('Cabinet du Lac')).toBeInTheDocument();
		expect(screen.getByText('Personnes avant vous').parentElement).toHaveTextContent('2');
		expect(screen.getByText('Attente estimée : environ 40 min')).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Appeler le cabinet' })).toHaveAttribute('href', 'tel:+21671000000');
	});

	it('tells the patient when it is their turn (checked every 20 seconds)', async () => {
		vi.useFakeTimers({ shouldAdvanceTime: true });
		let data: Record<string, unknown> = { ...waiting, peopleAhead: 0, estimatedWaitMin: 0 };
		mockApi({ 'GET /api/public/ticket/tk-15': () => json(200, data) });
		render(Page);
		expect(await screen.findByText('Vous êtes le prochain.')).toBeInTheDocument();
		data = { ...waiting, status: 'called', peopleAhead: null, estimatedWaitMin: null };
		await vi.advanceTimersByTimeAsync(20_000);
		expect(await screen.findByRole('status')).toHaveTextContent('C’est votre tour ! Présentez-vous à l’accueil.');
	});

	it('says when the ticket is from another day or unknown', async () => {
		mockApi({ 'GET /api/public/ticket/tk-15': () => json(200, { ...waiting, day: '2026-10-29' }) });
		const { unmount } = render(Page);
		expect(await screen.findByText('Ce ticket date du 29/10/2026 et n’est plus valable.')).toBeInTheDocument();
		unmount();
		mockApi({ 'GET /api/public/ticket/tk-15': () => problem(404, 'not_found') });
		render(Page);
		expect(await screen.findByRole('alert')).toHaveTextContent('Ticket introuvable. Vérifiez le lien reçu.');
	});

	it('can be read in Arabic', async () => {
		mockApi({ 'GET /api/public/ticket/tk-15': () => json(200, waiting) });
		render(Page);
		await screen.findByText('15');
		await fireEvent.click(screen.getByRole('button', { name: 'العربية' }));
		expect(screen.getByText('أشخاص قبلك')).toBeInTheDocument();
		expect(document.documentElement.dir).toBe('rtl');
	});
});
