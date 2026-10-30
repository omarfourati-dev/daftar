import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AppShell from './AppShell.svelte';
import { deps } from '../api';
import { auth } from '../auth.svelte';
import { badges } from '../badges.svelte';
import { i18n } from '../i18n.svelte';
import { calls, json, mockApi } from '../test-utils';
import { assistant, owner, practice, practitioners, services } from '../agenda/fixtures';

/** The daily-work additions to the app frame: patient search, shortcuts, badges, statistics for the owner. */
const children = createRawSnippet(() => ({ render: () => '<p>Contenu</p>' }));
const admin = { id: 1, email: 'omar@daftar.tn', name: 'Admin', role: 'admin', lang: 'fr', practice: null };

describe('AppShell – daily work', () => {
	beforeEach(() => {
		badges.stop();
		badges.onlineRequests = 0;
		badges.overdue = 0;
		i18n.setLocale('fr');
	});

	it('shows what is waiting to be handled next to "Aujourd’hui" in both navigations', async () => {
		auth.set('tok', assistant);
		mockApi({ 'GET /api/auth/me': () => json(200, assistant), 'GET /api/badges': () => json(200, { onlineRequests: 2, overdue: 1 }) });
		render(AppShell, { props: { path: '/app/agenda', children } });
		const main = within(screen.getByRole('navigation', { name: 'Navigation principale' }));
		await vi.waitFor(() => expect(main.getByRole('link', { name: /Aujourd’hui/ })).toHaveTextContent('3 à traiter'));
		const bar = within(screen.getByRole('navigation', { name: 'Navigation rapide' }));
		expect(bar.getByRole('link', { name: /Aujourd’hui/ })).toHaveTextContent('3 à traiter');
		expect(screen.getByRole('combobox', { name: 'Rechercher un patient' })).toBeInTheDocument();
		expect(main.queryByRole('link', { name: 'Statistiques' })).not.toBeInTheDocument();
		badges.stop();
	});

	it('gives the owner the statistics', async () => {
		auth.set('tok', owner);
		mockApi({ 'GET /api/auth/me': () => json(200, owner), 'GET /api/badges': () => json(200, { onlineRequests: 0, overdue: 0 }) });
		render(AppShell, { props: { path: '/app', children } });
		const main = within(screen.getByRole('navigation', { name: 'Navigation principale' }));
		expect(main.getByRole('link', { name: 'Statistiques' })).toHaveAttribute('href', '/app/statistiques');
		expect(main.getByRole('link', { name: 'Aujourd’hui' })).not.toHaveTextContent('à traiter');
		badges.stop();
	});

	it('reacts to the N shortcut', async () => {
		auth.set('tok', assistant);
		mockApi({ 'GET /api/auth/me': () => json(200, assistant), 'GET /api/badges': () => json(200, { onlineRequests: 0, overdue: 0 }) });
		render(AppShell, { props: { path: '/app/patients', children } });
		await fireEvent.keyDown(window, { key: 'n' });
		expect(deps.goto).toHaveBeenCalledWith('/app/agenda?nouveau=1');
		badges.stop();
	});

	it('does not search patients nor count badges for the admin', async () => {
		auth.set('tok', admin);
		mockApi({ 'GET /api/auth/me': () => json(200, admin) });
		render(AppShell, { props: { path: '/app/admin', children } });
		expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
		await vi.waitFor(() => expect(calls()).toContain('GET /api/auth/me'));
		expect(calls()).not.toContain('GET /api/badges');
	});

	it('has the phone booking button in the header', async () => {
		auth.set('tok', assistant);
		mockApi({
			'GET /api/auth/me': () => json(200, assistant),
			'GET /api/badges': () => json(200, { onlineRequests: 0, overdue: 0 }),
			'GET /api/practice': () => json(200, practice),
			'GET /api/practitioners': () => json(200, practitioners),
			'GET /api/services': () => json(200, services),
			'GET /api/closures': () => json(200, [])
		});
		render(AppShell, { props: { path: '/app', children } });
		await fireEvent.click(screen.getByRole('button', { name: 'Rendez-vous par téléphone' }));
		expect(await screen.findByRole('dialog', { name: 'Rendez-vous par téléphone' })).toBeInTheDocument();
		badges.stop();
	});
});

