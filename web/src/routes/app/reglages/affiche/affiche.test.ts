import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page@app.svelte';
import { auth } from '#lib/auth.svelte';
import { i18n } from '#lib/i18n.svelte';
import { json, mockApi, noContent } from '#lib/test-utils';
import { assistant, owner, practice } from '#lib/testing/fixtures';

describe('/app/reglages/affiche – A4 poster', () => {
	beforeEach(() => {
		i18n.setLocale('fr');
		auth.set('tok', owner);
	});
	afterEach(() => vi.restoreAllMocks());

	it('shows the practice in French and Arabic with the QR code of the booking page', async () => {
		mockApi({ 'GET /api/practice': () => json(200, practice()) });
		render(Page);
		const poster = await screen.findByRole('article', { name: 'Affiche A4' });
		expect(poster).toHaveTextContent('Cabinet du Lac');
		expect(poster).toHaveTextContent('عيادة البحيرة');
		expect(poster).toHaveTextContent('Prenez rendez-vous en ligne');
		expect(poster).toHaveTextContent('احجزوا موعدكم عبر الإنترنت');
		expect(poster).toHaveTextContent(`cabinet-lac.${location.host}`);
		expect(poster).toHaveTextContent('+216 71 123 456');
		expect(await screen.findByRole('img', { name: 'QR code de la page de réservation' })).toBeInTheDocument();
	});

	it('prints and ticks "poster" in the first steps', async () => {
		const print = vi.spyOn(window, 'print').mockImplementation(() => undefined);
		const fetch = mockApi({ 'GET /api/practice': () => json(200, practice()), 'POST /api/onboarding/poster/done': () => noContent() });
		render(Page);
		await screen.findByRole('article', { name: 'Affiche A4' });
		await fireEvent.click(screen.getByRole('button', { name: 'Imprimer l’affiche' }));
		expect(print).toHaveBeenCalledOnce();
		await vi.waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/onboarding/poster/done', expect.objectContaining({ method: 'POST' })));
	});

	it('works for the whole team, also when the onboarding call fails', async () => {
		auth.set('tok', assistant);
		vi.spyOn(window, 'print').mockImplementation(() => undefined);
		mockApi({ 'GET /api/practice': () => json(200, practice({ nameAr: '' })) });
		render(Page);
		await screen.findByRole('article', { name: 'Affiche A4' });
		await fireEvent.click(screen.getByRole('button', { name: 'Imprimer l’affiche' }));
		expect(screen.getByRole('article', { name: 'Affiche A4' })).toHaveTextContent('Cabinet du Lac');
	});
});
