import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AppShell from './AppShell.svelte';
import { ApiError, apiErrorMessage, deps } from '../api';
import { auth } from '../auth.svelte';
import { i18n } from '../i18n.svelte';
import { pwa } from '../pwa.svelte';
import { calls, json, mockApi, noContent, sentJson } from '../test-utils';
import type { Me } from '../types';

const children = createRawSnippet(() => ({ render: () => '<p>Contenu de la page</p>' }));
const practice = { id: 1, name: 'Cabinet du Lac', slug: 'cabinet-lac', specialty: 'generaliste', status: 'pilot', brandColor: '#0f766e', isDemo: false, demoExpiresAt: null };
const assistant: Me = { id: 5, email: 'salma@cabinet.tn', name: 'Salma', role: 'assistant', lang: 'fr', practice };
const admin: Me = { id: 1, email: 'omar@daftar.tn', name: 'Admin', role: 'admin', lang: 'fr', practice: null };

function shell(path: string) {
	return render(AppShell, { props: { path, children } });
}
const mainNav = () => within(screen.getByRole('navigation', { name: 'Navigation principale' }));

describe('AppShell', () => {
	beforeEach(() => {
		auth.clear();
		i18n.setLocale('fr');
		pwa.offline = false;
	});

	it('sends visitors without a session to /connexion and shows nothing', () => {
		mockApi({});
		shell('/app/agenda');
		expect(deps.goto).toHaveBeenCalledWith('/connexion');
		expect(screen.queryByText('Contenu de la page')).not.toBeInTheDocument();
	});

	it('shows the practice navigation, marks the current page and refreshes the account', async () => {
		auth.set('tok', { ...assistant, name: 'Ancien nom' });
		mockApi({ 'GET /api/auth/me': () => json(200, assistant) });
		shell('/app/agenda/semaine');
		expect(screen.getByText('Contenu de la page')).toBeInTheDocument();
		const links = mainNav().getAllByRole('link');
		expect(links.map((a) => [a.textContent?.trim(), a.getAttribute('href')])).toEqual([
			['Aujourd’hui', '/app'],
			['Agenda', '/app/agenda'],
			['Salle d’attente', '/app/salle'],
			['Patients', '/app/patients'],
			['Caisse', '/app/caisse'],
			['Rappels', '/app/rappels'],
			['Stock', '/app/stock'],
			['Réglages', '/app/reglages']
		]);
		expect(mainNav().getByRole('link', { name: 'Agenda' })).toHaveAttribute('aria-current', 'page');
		expect(mainNav().getByRole('link', { name: 'Aujourd’hui' })).not.toHaveAttribute('aria-current');
		await vi.waitFor(() => expect(auth.user?.name).toBe('Salma'));
		expect(await screen.findByText('Cabinet du Lac')).toBeInTheDocument();
	});

	it('has a bottom bar for phones with the four main pages and more', async () => {
		auth.set('tok', assistant);
		mockApi({ 'GET /api/auth/me': () => json(200, assistant) });
		shell('/app');
		const bar = within(screen.getByRole('navigation', { name: 'Navigation rapide' }));
		expect(bar.getAllByRole('link').map((a) => a.getAttribute('href'))).toEqual(['/app', '/app/agenda', '/app/salle', '/app/patients']);
		await fireEvent.click(bar.getByRole('button', { name: 'Plus' }));
		const more = within(screen.getByRole('dialog', { name: 'Plus' }));
		expect(more.getAllByRole('link').map((a) => a.getAttribute('href'))).toEqual(['/app/caisse', '/app/rappels', '/app/stock', '/app/reglages', '/app/import', '/app/installer']);
	});

	it('gives the admin the administration and sends him there from /app', async () => {
		auth.set('tok', admin);
		mockApi({ 'GET /api/auth/me': () => json(200, admin) });
		shell('/app');
		expect(mainNav().getAllByRole('link').map((a) => a.getAttribute('href'))).toEqual(['/app/admin', '/app/reglages']);
		expect(deps.goto).toHaveBeenCalledWith('/app/admin');
	});

	it('shows the demo banner in demo practices', async () => {
		const demo = { ...assistant, practice: { ...practice, isDemo: true, demoExpiresAt: '2026-10-31T09:00:00+01:00' } };
		auth.set('tok', demo);
		mockApi({ 'GET /api/auth/me': () => json(200, demo) });
		shell('/app');
		expect(screen.getByText('Démo – données fictives, supprimées après 24 h')).toBeInTheDocument();
	});

	it('warns when the subscription is suspended and when offline', async () => {
		const suspended = { ...assistant, practice: { ...practice, status: 'suspended' } };
		auth.set('tok', suspended);
		pwa.offline = true;
		mockApi({ 'GET /api/auth/me': () => json(200, suspended) });
		shell('/app');
		expect(screen.getByText(/Abonnement suspendu/)).toBeInTheDocument();
		expect(screen.getByText('Hors ligne')).toBeInTheDocument();
	});

	it('says that a canceled subscription only reads and exports (402 subscription_canceled)', async () => {
		const canceled = { ...assistant, practice: { ...practice, status: 'canceled' } };
		auth.set('tok', canceled);
		mockApi({ 'GET /api/auth/me': () => json(200, canceled) });
		shell('/app');
		expect(screen.getByText('Abonnement résilié – vous pouvez consulter et exporter vos données, mais plus les modifier.')).toBeInTheDocument();
		expect(apiErrorMessage(new ApiError(402, '', 'subscription_canceled'))).toBe(
			'Abonnement résilié : vous pouvez consulter et exporter vos données, mais plus les modifier.'
		);
	});

	it('switches the language and saves it on the account', async () => {
		auth.set('tok', assistant);
		mockApi({
			'GET /api/auth/me': () => json(200, assistant),
			'PATCH /api/auth/me': () => json(200, { ...assistant, lang: 'ar' })
		});
		shell('/app');
		await fireEvent.click(screen.getByRole('button', { name: 'ع العربية' }));
		expect(document.documentElement.dir).toBe('rtl');
		expect(await screen.findByRole('navigation', { name: 'القائمة الرئيسية' })).toBeInTheDocument();
		await vi.waitFor(() => expect(calls()).toContain('PATCH /api/auth/me'));
		expect(sentJson('PATCH /api/auth/me')).toEqual({ lang: 'ar' });
	});

	it('signs out', async () => {
		auth.set('tok', assistant);
		mockApi({ 'GET /api/auth/me': () => json(200, assistant), 'POST /api/auth/logout-all': () => noContent() });
		shell('/app');
		await fireEvent.click(screen.getByRole('button', { name: 'Se déconnecter' }));
		expect(auth.token).toBeNull();
		expect(deps.goto).toHaveBeenCalledWith('/connexion');
	});
});
