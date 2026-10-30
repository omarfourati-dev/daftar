import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { clock } from '#lib/clock';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, mockApi, problem, type Handler } from '#lib/test-utils';
import { viewport } from '#lib/viewport.svelte';
import { appt, assistant, NOW, practice, practitioners, services } from '#lib/agenda/fixtures';

/** The four requests every agenda load makes, plus the appointments of the shown range. */
export function agendaApi(extra: Record<string, Handler> = {}) {
	return mockApi({
		'GET /api/practice': () => json(200, practice),
		'GET /api/practitioners': () => json(200, practitioners),
		'GET /api/services': () => json(200, services),
		'GET /api/closures': () => json(200, []),
		...extra
	});
}

const sami = appt({ id: 1, startsAt: '2026-10-30T09:00:00+01:00', durationMin: 30, status: 'arrived' });
const lina = appt({
	id: 2,
	practitionerId: 12,
	practitionerName: 'Karim Jaziri',
	startsAt: '2026-10-30T11:00:00+01:00',
	durationMin: 20,
	status: 'confirmed',
	patient: { id: 9, firstName: 'Lina', lastName: 'Zouari', phone: '+21620000002', noShows: 3, alerts: 'Allergie pénicilline' }
});
const online = appt({
	id: 3,
	startsAt: '2026-10-30T11:45:00+01:00',
	status: 'requested',
	source: 'online',
	patient: { id: 10, firstName: 'Salma', lastName: 'Ben Omar', phone: '+21620000003', noShows: 0 }
});

describe('/app/agenda – day and week', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
		clock.now = () => new Date(NOW);
		viewport.narrow = false;
		history.replaceState(null, '', '/app/agenda');
	});

	it('shows today with one column per practitioner, the pause, the now line and the appointments', async () => {
		agendaApi({ 'GET /api/appointments?from=2026-10-30&to=2026-10-30': () => json(200, [sami, lina, online]) });
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'Agenda' })).toBeInTheDocument();
		expect(await screen.findByText('vendredi 30 octobre 2026')).toBeInTheDocument();
		const amira = within(await screen.findByRole('region', { name: 'Dr Amira Ben Salem' }));
		const karim = within(screen.getByRole('region', { name: 'Dr Karim Jaziri' }));
		expect(amira.getByRole('button', { name: /09:00 Sami Trabelsi/ })).toHaveTextContent('Arrivé');
		expect(karim.getByRole('button', { name: /11:00 Lina Zouari/ })).toHaveTextContent('3 absences');
		expect(karim.getByRole('button', { name: /11:00 Lina Zouari/ })).toHaveTextContent('Alerte médicale');
		expect(amira.getByRole('button', { name: /11:45 Salma Ben Omar/ })).toHaveTextContent('En ligne, à confirmer');
		expect(amira.getByText('Pause')).toBeInTheDocument(); // Friday 12:00–14:30
		expect(screen.getByRole('img', { name: 'Maintenant, 10:10' })).toBeInTheDocument();
		// free slots are offered inside the opening hours only, not where an appointment is
		expect(amira.getByRole('button', { name: 'Nouveau rendez-vous à 08:00 avec Dr Amira Ben Salem' })).toBeInTheDocument();
		expect(amira.queryByRole('button', { name: 'Nouveau rendez-vous à 09:00 avec Dr Amira Ben Salem' })).not.toBeInTheDocument();
		expect(amira.queryByRole('button', { name: 'Nouveau rendez-vous à 13:00 avec Dr Amira Ben Salem' })).not.toBeInTheDocument();
		expect(karim.getByRole('button', { name: 'Nouveau rendez-vous à 09:00 avec Dr Karim Jaziri' })).toBeInTheDocument();
	});

	it('browses days and switches to the week', async () => {
		agendaApi({
			'GET /api/appointments?from=2026-10-30&to=2026-10-30': () => json(200, [sami]),
			'GET /api/appointments?from=2026-10-31&to=2026-10-31': () => json(200, []),
			'GET /api/appointments?from=2026-10-26&to=2026-11-01': () => json(200, [sami, lina])
		});
		render(Page);
		await screen.findByText('vendredi 30 octobre 2026');
		await fireEvent.click(screen.getByRole('button', { name: 'Jour suivant' }));
		expect(await screen.findByText('samedi 31 octobre 2026')).toBeInTheDocument();
		expect(await screen.findByText('Aucun rendez-vous ce jour.')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Aujourd’hui' }));
		expect(await screen.findByText('vendredi 30 octobre 2026')).toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: 'Semaine' }));
		const friday = within(await screen.findByRole('region', { name: /vendredi 30/ }));
		expect(await friday.findByRole('button', { name: /11:00 Lina Zouari/ })).toBeInTheDocument();
		expect(friday.getByRole('button', { name: /09:00 Sami Trabelsi/ })).toBeInTheDocument();
		const sunday = within(screen.getByRole('region', { name: /dimanche 1/ }));
		expect(sunday.getByText('Cabinet fermé')).toBeInTheDocument();
		expect(calls()).toContain('GET /api/appointments?from=2026-10-26&to=2026-11-01');
	});

	it('filters the week by practitioner', async () => {
		agendaApi({
			'GET /api/appointments?from=2026-10-26&to=2026-11-01': () => json(200, [sami, lina])
		});
		history.replaceState(null, '', '/app/agenda?vue=semaine');
		render(Page);
		const friday = () => within(screen.getByRole('region', { name: /vendredi 30/ }));
		await vi.waitFor(() => expect(friday().getByRole('button', { name: /11:00 Lina Zouari/ })).toBeInTheDocument());
		await fireEvent.click(screen.getByRole('button', { name: 'Dr Amira Ben Salem' }));
		expect(friday().queryByRole('button', { name: /11:00 Lina Zouari/ })).not.toBeInTheDocument();
		expect(friday().getByRole('button', { name: /09:00 Sami Trabelsi/ })).toBeInTheDocument();
	});

	it('opens the day given in the address and shows a closure', async () => {
		agendaApi({
			'GET /api/closures': () => json(200, [{ id: 1, startsOn: '2026-11-02', endsOn: '2026-11-06', label: 'Congés' }]),
			'GET /api/appointments?from=2026-11-03&to=2026-11-03': () => json(200, [])
		});
		history.replaceState(null, '', '/app/agenda?date=2026-11-03');
		render(Page);
		expect(await screen.findByText('mardi 3 novembre 2026')).toBeInTheDocument();
		expect(await screen.findByText('Fermé : Congés')).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: /^Nouveau rendez-vous à/ })).not.toBeInTheDocument();
	});

	it('shows a list instead of the grid on phones', async () => {
		viewport.narrow = true;
		agendaApi({ 'GET /api/appointments?from=2026-10-30&to=2026-10-30': () => json(200, [lina, sami]) });
		render(Page);
		const list = within(await screen.findByRole('list', { name: 'vendredi 30 octobre 2026' }));
		const items = await list.findAllByRole('button', { name: /Sami Trabelsi|Lina Zouari/ });
		expect(items.map((b) => b.textContent)).toEqual([expect.stringContaining('Sami Trabelsi'), expect.stringContaining('Lina Zouari')]);
		expect(screen.queryByRole('region', { name: 'Dr Amira Ben Salem' })).not.toBeInTheDocument();
	});

	it('explains when the agenda cannot be loaded and retries', async () => {
		let fail = true;
		agendaApi({
			'GET /api/appointments?from=2026-10-30&to=2026-10-30': () => (fail ? problem(500, 'server_error') : json(200, [sami]))
		});
		render(Page);
		expect(await screen.findByRole('alert')).toHaveTextContent('L’agenda n’a pas pu être chargé.');
		fail = false;
		await fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }));
		expect(await screen.findByRole('button', { name: /09:00 Sami Trabelsi/ })).toBeInTheDocument();
	});

	it('shows the agenda in Arabic', async () => {
		i18n.setLocale('ar');
		agendaApi({ 'GET /api/appointments?from=2026-10-30&to=2026-10-30': () => json(200, [sami]) });
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'المواعيد' })).toBeInTheDocument();
		expect(await screen.findByRole('button', { name: /09:00 Sami Trabelsi/ })).toHaveTextContent('وصل');
		expect(screen.getByRole('button', { name: 'اليوم التالي' })).toBeInTheDocument();
	});
});
