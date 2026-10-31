import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { clock } from '#lib/clock';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, mockApi, noContent, problem, sentJson, type Handler } from '#lib/test-utils';
import { appt, assistant, NOW, owner, practice } from '#lib/agenda/fixtures';
import { patientSearch, phoneBooking } from '#lib/agenda/requests.svelte';

const dashboard = {
	today: '2026-10-30',
	appointments: { total: 12, byStatus: { done: 3, arrived: 1, in_treatment: 1, confirmed: 4, scheduled: 2, no_show: 1 } },
	upcoming: [
		appt({ id: 20, startsAt: '2026-10-30T10:45:00+01:00', status: 'arrived', patient: { id: 1, firstName: 'Leila', lastName: 'Karoui', phone: '+21620000004', noShows: 0, lang: 'fr' } }),
		appt({ id: 21, startsAt: '2026-10-30T11:15:00+01:00', status: 'confirmed', patient: { id: 2, firstName: 'Walid', lastName: 'Hammami', phone: '+21620000005', noShows: 0, lang: 'fr' } })
	],
	queue: { waiting: 3, called: 1 },
	cashTodayMillimes: 185000,
	remindersPending: 6,
	dueTotalMillimes: 1240500,
	patientsCount: 230
};
const request = appt({
	id: 30,
	status: 'requested',
	source: 'online',
	startsAt: '2026-11-02T11:45:00+01:00',
	reason: 'Consultation',
	patientNote: 'Toux',
	patient: { id: 3, firstName: 'Salma', lastName: 'Ben Omar', phone: '+21620000006', noShows: 0, lang: 'fr' }
});
const late = appt({ id: 40, startsAt: '2026-10-30T08:30:00+01:00', status: 'confirmed', patient: { id: 4, firstName: 'Hichem', lastName: 'Bouzid', phone: '+21620000007', noShows: 1, lang: 'fr' } });

function dashboardApi(extra: Record<string, Handler> = {}) {
	return mockApi({
		'GET /api/dashboard': () => json(200, { ...dashboard, onlineRequests: [request], onlineRequestsCount: 1 }),
		'GET /api/appointments/overdue': () => json(200, [late]),
		'GET /api/practice': () => json(200, practice),
		'GET /api/badges': () => json(200, { onlineRequests: 0, overdue: 0 }),
		...extra
	});
}

describe('/app – today at a glance', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
		clock.now = () => new Date(NOW);
	});

	it('shows the tiles of the day and the next appointments', async () => {
		dashboardApi();
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'Aujourd’hui' })).toBeInTheDocument();
		const tiles = within(await screen.findByRole('list', { name: 'Résumé de la journée' }));
		expect(tiles.getByRole('link', { name: /Rendez-vous 12/ })).toHaveAttribute('href', '/app/agenda');
		expect(tiles.getByRole('link', { name: /Rendez-vous 12/ })).toHaveTextContent('3 terminés, 6 à venir');
		expect(tiles.getByRole('link', { name: /En salle d’attente 3/ })).toHaveAttribute('href', '/app/salle');
		expect(tiles.getByRole('link', { name: /Caisse du jour 185 DT/ })).toHaveAttribute('href', '/app/caisse');
		expect(tiles.getByRole('link', { name: /Rappels de demain 6/ })).toHaveAttribute('href', '/app/rappels');
		expect(tiles.getByRole('link', { name: /Montants dus 1 240,500 DT/ })).toHaveAttribute('href', '/app/caisse#impayes');
		const upcoming = within(screen.getByRole('region', { name: 'Prochains rendez-vous' }));
		expect(upcoming.getByText('Leila Karoui')).toBeInTheDocument();
		expect(upcoming.getByText('Arrivé')).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Nouveau rendez-vous' })).toHaveAttribute('href', '/app/agenda?nouveau=1');
	});

	it('confirms an online request and offers the WhatsApp message', async () => {
		dashboardApi({ 'POST /api/appointments/30/status': () => json(200, { ...request, status: 'confirmed' }) });
		render(Page);
		const requests = within(await screen.findByRole('region', { name: 'Nouvelles demandes en ligne' }));
		expect(await requests.findByText('Salma Ben Omar')).toBeInTheDocument();
		expect(requests.getByText('Toux')).toBeInTheDocument();
		expect(requests.queryByText('Leila Karoui')).not.toBeInTheDocument(); // only requests
		await fireEvent.click(requests.getByRole('button', { name: 'Confirmer' }));
		expect(sentJson('POST /api/appointments/30/status')).toEqual({ status: 'confirmed' });
		const link = await requests.findByRole('link', { name: 'Prévenir par WhatsApp' });
		expect(decodeURIComponent(link.getAttribute('href') ?? '')).toContain('votre rendez-vous au Cabinet du Lac le 02/11/2026 à 11:45 est confirmé');
		expect(requests.getByText('Salma Ben Omar : Confirmé.')).toBeInTheDocument();
	});

	it('has big buttons for the phone appointment and, on phones, the patient search (fixlist 2)', async () => {
		dashboardApi();
		phoneBooking.open = false;
		render(Page);
		await fireEvent.click(screen.getByRole('button', { name: 'Rendez-vous par téléphone' }));
		expect(phoneBooking.open).toBe(true);
		phoneBooking.open = false;
		const search = screen.getByRole('button', { name: 'Rechercher un patient' });
		expect(search).toHaveClass('sm:hidden'); // larger screens have the search in the header
		const show = vi.spyOn(patientSearch, 'show').mockImplementation(() => undefined);
		await fireEvent.click(search);
		expect(show).toHaveBeenCalledOnce();
		show.mockRestore();
	});

	it('writes to the patient in the patient’s language, not the screen’s (fixlist 2)', async () => {
		const arabic = { ...request, patient: { ...request.patient, lang: 'ar' as const } };
		mockApi({
			'GET /api/dashboard': () => json(200, { ...dashboard, onlineRequests: [arabic], onlineRequestsCount: 1 }),
			'GET /api/appointments/overdue': () => json(200, []),
			'GET /api/practice': () => json(200, practice),
			'GET /api/badges': () => json(200, { onlineRequests: 0, overdue: 0 }),
			'POST /api/appointments/30/status': () => json(200, { ...arabic, status: 'cancelled' })
		});
		render(Page);
		const requests = within(await screen.findByRole('region', { name: 'Nouvelles demandes en ligne' }));
		await fireEvent.click(await requests.findByRole('button', { name: 'Refuser' }));
		const link = await requests.findByRole('link', { name: 'Prévenir par WhatsApp' }); // the screen stays French
		const text = decodeURIComponent(link.getAttribute('href') ?? '');
		expect(text).toContain('مرحبًا Salma، لا يمكننا استقبالك يوم 02/11/2026 على الساعة 11:45');
		expect(text).not.toContain('Bonjour');
	});

	it('marks a forgotten appointment as no-show in one click', async () => {
		dashboardApi({ 'POST /api/appointments/40/status': () => json(200, { ...late, status: 'no_show' }) });
		render(Page);
		const overdue = within(await screen.findByRole('region', { name: 'Non venus ?' }));
		expect(await overdue.findByText('Hichem Bouzid')).toBeInTheDocument();
		await fireEvent.click(overdue.getByRole('button', { name: 'Absent' }));
		expect(sentJson('POST /api/appointments/40/status')).toEqual({ status: 'no_show' });
		expect(await screen.findByText('Hichem Bouzid : Absent.')).toBeInTheDocument();
		expect(overdue.queryByRole('button', { name: 'Absent' })).not.toBeInTheDocument();
	});

	it('records that the patient came after all', async () => {
		dashboardApi({ 'POST /api/appointments/40/status': () => json(200, { ...late, status: 'done' }) });
		render(Page);
		const overdue = within(await screen.findByRole('region', { name: 'Non venus ?' }));
		await fireEvent.click(await overdue.findByRole('button', { name: 'Venu' }));
		await vi.waitFor(() => expect(sentJson('POST /api/appointments/40/status')).toEqual({ status: 'done' }));
	});

	it('hides the lists that have nothing to do', async () => {
		dashboardApi({
			'GET /api/appointments/overdue': () => json(200, []),
			'GET /api/dashboard': () => json(200, { ...dashboard, upcoming: [], onlineRequests: [], onlineRequestsCount: 0 })
		});
		render(Page);
		expect(await screen.findByText('Plus aucun rendez-vous prévu aujourd’hui.')).toBeInTheDocument();
		expect(screen.queryByRole('region', { name: 'Non venus ?' })).not.toBeInTheDocument();
		expect(screen.queryByRole('region', { name: 'Nouvelles demandes en ligne' })).not.toBeInTheDocument();
		expect(calls()).not.toContain('GET /api/onboarding'); // the checklist is for the owner
	});

	it('explains when the dashboard cannot be loaded', async () => {
		dashboardApi({ 'GET /api/dashboard': () => problem(500, 'server_error') });
		render(Page);
		expect(await screen.findByRole('alert')).toHaveTextContent('Le tableau de bord n’a pas pu être chargé.');
		expect(screen.getByRole('button', { name: 'Réessayer' })).toBeInTheDocument();
	});

	it('the first steps lead to pages that exist (fixlist 2: no anchors that are not there)', async () => {
		auth.set('tok', owner);
		const KEYS = ['hours', 'services', 'practitioners', 'team', 'booking', 'import', 'install', 'poster'];
		dashboardApi({ 'GET /api/onboarding': () => json(200, { steps: KEYS.map((key) => ({ key, done: false })), dismissed: false }) });
		render(Page);
		const steps = within(await screen.findByRole('region', { name: 'Premiers pas' }));
		const hrefs = steps.getAllByRole('link').map((a) => a.getAttribute('href') ?? '');
		expect(hrefs).toEqual([
			'/app/reglages/horaires',
			'/app/reglages/actes',
			'/app/reglages/praticiens',
			'/app/reglages/equipe',
			'/app/reglages/reservation',
			'/app/import',
			'/app/installer',
			'/app/reglages/affiche'
		]);
		const pages = Object.keys(import.meta.glob('./**/+page*.svelte')).map((f) => '/app' + f.slice(1).replace(/\/\+page(@\w+)?\.svelte$/, ''));
		for (const href of hrefs) expect(pages, href).toContain(href);
	});

	it('shows the first steps to the owner until they are done or hidden', async () => {
		auth.set('tok', owner);
		dashboardApi({
			'GET /api/onboarding': () =>
				json(200, {
					steps: [
						{ key: 'hours', done: true },
						{ key: 'services', done: true },
						{ key: 'practitioners', done: false },
						{ key: 'team', done: false },
						{ key: 'booking', done: false },
						{ key: 'import', done: false },
						{ key: 'install', done: false },
						{ key: 'poster', done: false }
					],
					dismissed: false
				}),
			'POST /api/onboarding/install/done': () => noContent(),
			'POST /api/onboarding/dismiss': () => noContent()
		});
		render(Page);
		const steps = within(await screen.findByRole('region', { name: 'Premiers pas' }));
		expect(steps.getByText('2 sur 8 terminés')).toBeInTheDocument();
		expect(steps.getByRole('link', { name: 'Importer vos patients (Excel)' })).toHaveAttribute('href', '/app/import');
		expect(steps.getByRole('link', { name: 'Installer l’application' })).toHaveAttribute('href', '/app/installer');
		expect(steps.getByRole('link', { name: 'Imprimer l’affiche pour la salle d’attente' })).toHaveAttribute('href', '/app/reglages/affiche');
		await fireEvent.click(steps.getAllByRole('button', { name: 'C’est fait' })[0]);
		expect(await steps.findByText('3 sur 8 terminés')).toBeInTheDocument();
		expect(calls()).toContain('POST /api/onboarding/install/done');
		await fireEvent.click(steps.getByRole('button', { name: 'Masquer' }));
		await vi.waitFor(() => expect(screen.queryByRole('region', { name: 'Premiers pas' })).not.toBeInTheDocument());
		expect(calls()).toContain('POST /api/onboarding/dismiss');
	});

	it('is translated into Arabic', async () => {
		i18n.setLocale('ar');
		dashboardApi();
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'اليوم' })).toBeInTheDocument();
		expect(await screen.findByRole('region', { name: 'لم يحضروا؟' })).toBeInTheDocument();
		expect(await screen.findByRole('region', { name: 'طلبات جديدة عبر الإنترنت' })).toBeInTheDocument();
	});

	it('shows the owner the cash closings still to verify', async () => {
		auth.set('tok', owner);
		dashboardApi({
			'GET /api/dashboard': () =>
				json(200, {
					...dashboard,
					onlineRequests: [],
					unverifiedCashDays: [
						{ day: '2026-10-29', differenceMillimes: -5000 },
						{ day: '2026-10-28', differenceMillimes: 0 }
					]
				}),
			'GET /api/onboarding': () => json(200, { steps: [], dismissed: true })
		});
		render(Page);
		const check = within(await screen.findByRole('region', { name: 'Caisses à vérifier' }));
		expect(check.getByRole('link', { name: /29\/10\/2026/ })).toHaveAttribute('href', '/app/caisse?day=2026-10-29');
		expect(check.getByRole('link', { name: /29\/10\/2026/ })).toHaveTextContent('écart -5 DT');
		expect(check.getByRole('link', { name: /28\/10\/2026/ })).toHaveTextContent('caisse juste');
	});
});
