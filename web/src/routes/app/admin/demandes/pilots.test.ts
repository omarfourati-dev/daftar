import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { deps } from '#lib/api';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, mockApi, noContent } from '#lib/test-utils';
import type { PilotRequest } from '#lib/types/admin';

const request: PilotRequest = {
	id: 3,
	name: 'Dr Sami Gharbi',
	practice: 'Cabinet Gharbi',
	city: 'Sfax',
	phone: '+21698111222',
	email: 'sami@gharbi.tn',
	message: 'Nous sommes trois médecins.',
	lang: 'ar',
	createdAt: '2026-10-29T18:20:00+01:00'
};

describe('/app/admin/demandes', () => {
	beforeEach(() => {
		i18n.setLocale('fr');
		sessionStorage.clear();
	});

	it('lists pilot requests with ways to call back', async () => {
		mockApi({ 'GET /api/admin/pilot-requests': () => json(200, [request]) });
		render(Page);
		const card = (await screen.findByRole('heading', { name: 'Cabinet Gharbi' })).closest('article')!;
		expect(within(card).getByText(/Dr Sami Gharbi/)).toBeInTheDocument();
		expect(within(card).getByText('Nous sommes trois médecins.')).toBeInTheDocument();
		expect(within(card).getByText('Reçue le 29/10/2026 18:20')).toBeInTheDocument();
		expect(within(card).getByRole('link', { name: 'Appeler' })).toHaveAttribute('href', 'tel:+21698111222');
		expect(within(card).getByRole('link', { name: 'WhatsApp' }).getAttribute('href')).toMatch(/^https:\/\/wa\.me\/21698111222/);
		expect(within(card).getByRole('link', { name: 'sami@gharbi.tn' })).toHaveAttribute('href', 'mailto:sami@gharbi.tn');
	});

	it('starts the wizard pre-filled from a request', async () => {
		mockApi({ 'GET /api/admin/pilot-requests': () => json(200, [request]) });
		render(Page);
		await fireEvent.click(await screen.findByRole('button', { name: 'Créer le cabinet – Cabinet Gharbi' }));
		expect(JSON.parse(sessionStorage.getItem('daftar.wizardPrefill') ?? '{}')).toMatchObject({ practice: 'Cabinet Gharbi', name: 'Dr Sami Gharbi' });
		expect(deps.goto).toHaveBeenCalledWith('/app/admin/cabinets/nouveau');
	});

	it('deletes a request after confirmation', async () => {
		mockApi({ 'GET /api/admin/pilot-requests': () => json(200, [request]), 'DELETE /api/admin/pilot-requests/3': () => noContent() });
		render(Page);
		await fireEvent.click(await screen.findByRole('button', { name: 'Supprimer – Cabinet Gharbi' }));
		await fireEvent.click(within(screen.getByRole('dialog', { name: 'Supprimer la demande de Dr Sami Gharbi ?' })).getByRole('button', { name: 'Supprimer la demande' }));
		await vi.waitFor(() => expect(screen.queryByRole('heading', { name: 'Cabinet Gharbi' })).not.toBeInTheDocument());
		expect(calls()).toContain('DELETE /api/admin/pilot-requests/3');
		expect(screen.getByText(/Aucune demande pour l’instant/)).toBeInTheDocument();
	});
});
