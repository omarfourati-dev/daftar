import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, labelInNameProblems, mockApi, noContent, sentJson } from '#lib/test-utils';
import { owner } from '#lib/testing/fixtures';

const staff = [
	{ id: 2, name: 'Amira Ben Salah', email: 'amira@cabinet.tn', role: 'owner', createdAt: '2026-10-01T10:00:00+01:00' },
	{ id: 5, name: 'Salma', email: 'salma@cabinet.tn', role: 'assistant', createdAt: '2026-10-02T10:00:00+01:00' }
];
const invitations = [{ id: 9, role: 'dentist', createdAt: '2026-10-29T10:00:00+01:00', expiresAt: '2026-11-05T10:00:00+01:00' }];

function team(extra: Record<string, () => Response> = {}) {
	return mockApi({ 'GET /api/staff': () => json(200, staff), 'GET /api/staff/invitations': () => json(200, invitations), ...extra });
}

describe('/app/reglages/equipe', () => {
	beforeEach(() => {
		i18n.setLocale('fr');
		auth.set('tok', owner);
	});

	it('lists the accounts and pending invitations', async () => {
		team();
		render(Page);
		const me = (await screen.findByText('Amira Ben Salah')).closest('li')!;
		expect(within(me).getByText('vous')).toBeInTheDocument();
		expect(within(me).queryByRole('button')).not.toBeInTheDocument(); // nobody removes or resets the owner here
		const salma = screen.getByText('Salma').closest('li')!;
		expect(within(salma).getByLabelText('Rôle de Salma')).toHaveValue('assistant');
		expect(screen.getByText('Praticien(ne) – expire le 05/11/2026')).toBeInTheDocument();
	});

	it('changes a role', async () => {
		team({ 'PATCH /api/staff/5': () => json(200, { ...staff[1], role: 'dentist' }) });
		render(Page);
		await fireEvent.change(await screen.findByLabelText('Rôle de Salma'), { target: { value: 'dentist' } });
		await vi.waitFor(() => expect(sentJson('PATCH /api/staff/5')).toEqual({ role: 'dentist' }));
		expect(await screen.findByText('Rôle enregistré.')).toBeInTheDocument();
	});

	it('creates a password reset link for a team member', async () => {
		team({ 'POST /api/staff/5/reset-link': () => json(201, { token: 'rst', expiresAt: '2026-10-31T10:00:00+01:00' }) });
		render(Page);
		await fireEvent.click(await screen.findByRole('button', { name: 'Mot de passe oublié de Salma' }));
		expect(await screen.findByRole('textbox', { name: 'Lien de réinitialisation pour Salma' })).toHaveValue(
			`http://cabinet-lac.${location.host}/reinitialiser#rst`
		);
		expect(screen.getByRole('link', { name: 'Envoyer par WhatsApp' }).getAttribute('href')).toContain('Bonjour%20Salma');
	});

	it('invites an assistant with a link to send on WhatsApp', async () => {
		team({ 'POST /api/staff/invitations': () => json(201, { id: 10, token: 'inv', expiresAt: '2026-11-06T10:00:00+01:00' }) });
		render(Page);
		await fireEvent.change(await screen.findByLabelText('Rôle'), { target: { value: 'assistant' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Créer le lien d’invitation' }));
		expect(await screen.findByRole('textbox', { name: 'Lien d’invitation (Assistant(e))' })).toHaveValue(
			`http://cabinet-lac.${location.host}/invitation#inv`
		);
		expect(sentJson('POST /api/staff/invitations')).toEqual({ role: 'assistant' });
		expect(screen.getByText('Assistant(e) – expire le 06/11/2026')).toBeInTheDocument();
	});

	it('cancels an invitation and removes a member after confirmation', async () => {
		team({ 'DELETE /api/staff/invitations/9': () => noContent(), 'DELETE /api/staff/5': () => noContent() });
		render(Page);
		await fireEvent.click(await screen.findByRole('button', { name: 'Annuler l’invitation Praticien(ne) du 29/10/2026' }));
		await vi.waitFor(() => expect(screen.getByText('Aucune invitation en attente.')).toBeInTheDocument());
		await fireEvent.click(screen.getByRole('button', { name: 'Retirer Salma' }));
		await fireEvent.click(within(screen.getByRole('dialog', { name: 'Retirer Salma de l’équipe ?' })).getByRole('button', { name: 'Retirer de l’équipe' }));
		await vi.waitFor(() => expect(screen.queryByText('Salma')).not.toBeInTheDocument());
		expect(calls()).toEqual(expect.arrayContaining(['DELETE /api/staff/invitations/9', 'DELETE /api/staff/5']));
	});

	it('starts every button name with its visible text, in French and Arabic (WCAG 2.5.3)', async () => {
		for (const locale of ['fr', 'ar'] as const) {
			i18n.setLocale(locale);
			team();
			const { unmount } = render(Page);
			await screen.findByText('Salma');
			expect(labelInNameProblems()).toEqual([]);
			unmount();
		}
		i18n.setLocale('fr');
	});
});
