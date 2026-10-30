import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, mockApi, problem } from '#lib/test-utils';
import type { AdminPracticeRow } from '#lib/types/admin';

const lac: AdminPracticeRow = {
	id: 7,
	name: 'Cabinet du Lac',
	city: 'Tunis',
	isDemo: false,
	createdAt: '2026-10-01T10:00:00+01:00',
	users: 3,
	patients: 120,
	appointments: 412,
	appointmentsWeek: 23,
	lastActivityAt: '2026-10-30T08:15:00+01:00',
	slug: 'cabinet-lac',
	specialty: 'dentiste',
	status: 'active',
	planCode: 'cabinet_mensuel',
	paidUntil: '2026-11-30'
};
const kine: AdminPracticeRow = {
	id: 8,
	name: 'Kiné Sousse',
	city: 'Sousse',
	isDemo: false,
	createdAt: '2026-10-20T10:00:00+01:00',
	users: 1,
	patients: 0,
	appointments: 0,
	lastActivityAt: null,
	slug: 'kine-sousse',
	specialty: 'kinesitherapeute',
	status: 'pilot',
	planCode: 'pilot',
	paidUntil: '2026-10-01'
};

describe('/app/admin – practices', () => {
	beforeEach(() => i18n.setLocale('fr'));

	it('lists the practices with status, plan, paid-until and last activity', async () => {
		mockApi({ 'GET /api/admin/practices': () => json(200, [lac, kine]) });
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'Administration' })).toBeInTheDocument();
		const tabs = within(screen.getByRole('navigation', { name: 'Rubriques de l’administration' }));
		expect(tabs.getByRole('link', { name: 'Cabinets' })).toHaveAttribute('aria-current', 'page');
		expect(tabs.getByRole('link', { name: 'Abonnements' })).toHaveAttribute('href', '/app/admin/abonnements');
		expect(tabs.getByRole('link', { name: 'Demandes pilotes' })).toHaveAttribute('href', '/app/admin/demandes');
		expect(tabs.getByRole('link', { name: 'Retours' })).toHaveAttribute('href', '/app/admin/retours');

		const row = (await screen.findByRole('link', { name: 'Cabinet du Lac' })).closest('li')!;
		expect(screen.getByRole('link', { name: 'Cabinet du Lac' })).toHaveAttribute('href', '/app/admin/cabinets/7');
		expect(within(row).getByText('Actif')).toBeInTheDocument();
		expect(within(row).getByText('Cabinet – mensuel')).toBeInTheDocument();
		expect(within(row).getByText('30/11/2026')).toBeInTheDocument();
		expect(within(row).getByText('30/10/2026 08:15')).toBeInTheDocument();
		expect(within(row).getByText('3 compte(s) · 120 patients · 412 rendez-vous (23 cette semaine)')).toBeInTheDocument();
		const other = screen.getByRole('link', { name: 'Kiné Sousse' }).closest('li')!;
		expect(within(other).getByText('jamais')).toBeInTheDocument();
		expect(screen.getByText('2 cabinet(s)')).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Nouveau cabinet' })).toHaveAttribute('href', '/app/admin/cabinets/nouveau');
	});

	it('filters by text and status without asking the server again', async () => {
		mockApi({ 'GET /api/admin/practices': () => json(200, [lac, kine]) });
		render(Page);
		await screen.findByRole('link', { name: 'Cabinet du Lac' });
		await fireEvent.input(screen.getByLabelText('Rechercher un cabinet'), { target: { value: 'sous' } });
		expect(screen.queryByRole('link', { name: 'Cabinet du Lac' })).not.toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Kiné Sousse' })).toBeInTheDocument();
		await fireEvent.input(screen.getByLabelText('Rechercher un cabinet'), { target: { value: '' } });
		await fireEvent.change(screen.getByLabelText('Statut'), { target: { value: 'active' } });
		expect(screen.getByRole('link', { name: 'Cabinet du Lac' })).toBeInTheDocument();
		expect(screen.queryByRole('link', { name: 'Kiné Sousse' })).not.toBeInTheDocument();
		await fireEvent.input(screen.getByLabelText('Rechercher un cabinet'), { target: { value: 'zzz' } });
		expect(screen.getByText('Aucun cabinet ne correspond à cette recherche.')).toBeInTheDocument();
		expect(calls()).toEqual(['GET /api/admin/practices']);
	});

	it('shows demo practices on request', async () => {
		const demo = { ...kine, id: 9, name: 'Cabinet Démo', isDemo: true, slug: 'demo-abcdefgh' };
		mockApi({
			'GET /api/admin/practices': () => json(200, [lac]),
			'GET /api/admin/practices?demo=true': () => json(200, [lac, demo])
		});
		render(Page);
		await screen.findByRole('link', { name: 'Cabinet du Lac' });
		await fireEvent.click(screen.getByRole('checkbox', { name: 'Afficher les démos' }));
		const row = (await screen.findByRole('link', { name: 'Cabinet Démo' })).closest('li')!;
		expect(within(row).getByText('Démo')).toBeInTheDocument();
	});

	it('invites to create the first practice when there is none', async () => {
		mockApi({ 'GET /api/admin/practices': () => json(200, []) });
		render(Page);
		expect(await screen.findByText(/Aucun cabinet pour l’instant/)).toBeInTheDocument();
	});

	it('explains a loading error and retries', async () => {
		let fail = true;
		mockApi({ 'GET /api/admin/practices': () => (fail ? problem(500, 'server_error') : json(200, [lac])) });
		render(Page);
		expect(await screen.findByRole('alert')).toHaveTextContent('Une erreur est survenue.');
		fail = false;
		await fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }));
		expect(await screen.findByRole('link', { name: 'Cabinet du Lac' })).toBeInTheDocument();
	});

	it('works in Arabic', async () => {
		i18n.setLocale('ar');
		mockApi({ 'GET /api/admin/practices': () => json(200, [lac]) });
		render(Page);
		const row = (await screen.findByRole('link', { name: 'Cabinet du Lac' })).closest('li')!;
		expect(within(row).getByText('نشط')).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'عيادة جديدة' })).toBeInTheDocument();
		await vi.waitFor(() => expect(screen.getByRole('heading', { level: 1, name: 'الإدارة' })).toBeInTheDocument());
	});
});
