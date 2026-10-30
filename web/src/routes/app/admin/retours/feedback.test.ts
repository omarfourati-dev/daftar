import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, mockApi, noContent } from '#lib/test-utils';
import type { FeedbackItem } from '#lib/types/admin';

const item: FeedbackItem = {
	id: 4,
	practiceId: 7,
	practiceName: 'Cabinet du Lac',
	userName: 'Salma',
	message: 'Pouvez-vous ajouter les SMS ?',
	page: '/app/rappels',
	createdAt: '2026-10-30T11:05:00+01:00'
};

describe('/app/admin/retours', () => {
	beforeEach(() => i18n.setLocale('fr'));

	it('shows feedback with practice, author, page and date', async () => {
		mockApi({ 'GET /api/admin/feedback': () => json(200, [item]) });
		render(Page);
		const card = (await screen.findByText('Pouvez-vous ajouter les SMS ?')).closest('article')!;
		expect(within(card).getByText('Cabinet du Lac · Salma')).toBeInTheDocument();
		expect(within(card).getByText('Page : /app/rappels')).toBeInTheDocument();
		expect(within(card).getByText('30/10/2026 11:05')).toBeInTheDocument();
	});

	it('deletes feedback', async () => {
		mockApi({ 'GET /api/admin/feedback': () => json(200, [item]), 'DELETE /api/admin/feedback/4': () => noContent() });
		render(Page);
		await fireEvent.click(await screen.findByRole('button', { name: 'Supprimer le retour du 30/10/2026 11:05' }));
		await fireEvent.click(within(screen.getByRole('dialog', { name: 'Supprimer ce retour ?' })).getByRole('button', { name: 'Supprimer le retour' }));
		await vi.waitFor(() => expect(calls()).toContain('DELETE /api/admin/feedback/4'));
		expect(await screen.findByText('Aucun retour pour l’instant.')).toBeInTheDocument();
	});
});
