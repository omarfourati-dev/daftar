import { render, screen } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { beforeEach, describe, expect, it } from 'vitest';
import AppShell from './AppShell.svelte';
import { auth } from '../auth.svelte';
import { i18n } from '../i18n.svelte';
import { json, mockApi } from '../test-utils';
import { adminUser, assistant, owner } from '../testing/fixtures';

const children = createRawSnippet(() => ({ render: () => '<p>Contenu</p>' }));
const shell = (path = '/app') => render(AppShell, { props: { path, children } });

describe('app shell – customer additions', () => {
	beforeEach(() => i18n.setLocale('fr'));

	it('offers the feedback button to practice staff but not to the admin', async () => {
		auth.set('tok', assistant);
		mockApi({ 'GET /api/auth/me': () => json(200, assistant) });
		const { unmount } = shell();
		expect(screen.getByRole('button', { name: 'Une idée ? Un problème ?' })).toBeInTheDocument();
		unmount();
		auth.set('tok', adminUser);
		mockApi({ 'GET /api/auth/me': () => json(200, adminUser) });
		shell('/app/admin');
		expect(screen.queryByRole('button', { name: 'Une idée ? Un problème ?' })).not.toBeInTheDocument();
	});

	it('warns about an overdue subscription and sends the owner to the subscription page', async () => {
		const late = { ...owner, practice: { ...owner.practice!, status: 'past_due' } };
		auth.set('tok', late);
		mockApi({ 'GET /api/auth/me': () => json(200, late) });
		shell();
		expect(screen.getByText(/Paiement de l’abonnement en retard/)).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Voir l’abonnement' })).toHaveAttribute('href', '/app/abonnement');
	});

	it('tells other roles to see the owner', async () => {
		const late = { ...assistant, practice: { ...assistant.practice!, status: 'past_due' } };
		auth.set('tok', late);
		mockApi({ 'GET /api/auth/me': () => json(200, late) });
		shell();
		expect(screen.getByText(/Paiement de l’abonnement en retard/)).toBeInTheDocument();
		expect(screen.queryByRole('link', { name: 'Voir l’abonnement' })).not.toBeInTheDocument();
	});
});
