import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { clock } from '#lib/clock';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, mockApi, problem, type Handler } from '#lib/test-utils';
import { viewport } from '#lib/viewport.svelte';
import { appt, assistant, NOW, practice, practitioners, services } from '#lib/agenda/fixtures';
import { newAppointment } from '#lib/agenda/requests.svelte';

/** The four requests every agenda load makes, plus the appointments of the shown range. */
export function agendaApi(extra: Record<string, Handler> = {}) {
	return mockApi({
		'GET /api/practice': () => json(200, practice),
		'GET /api/practitioners': () => json(200, practitioners),
		'GET /api/services': () => json(200, services),
		'GET /api/closures': () => json(200, []),
		'GET /api/badges': () => json(200, { onlineRequests: 0, overdue: 0 }),
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
	patient: { id: 9, firstName: 'Lina', lastName: 'Zouari', phone: '+21620000002', noShows: 3, lang: 'fr', alerts: 'Allergie pénicilline' }
});
const online = appt({
	id: 3,
	startsAt: '2026-10-30T11:45:00+01:00',
	status: 'requested',
	source: 'online',
	patient: { id: 10, firstName: 'Salma', lastName: 'Ben Omar', phone: '+21620000003', noShows: 0, lang: 'fr' }
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
		expect(amira.getByRole('button', { name: 'Nouveau rendez-vous à 10:00 avec Dr Amira Ben Salem' })).toBeInTheDocument(); // running quarter
		expect(amira.queryByRole('button', { name: 'Nouveau rendez-vous à 09:45 avec Dr Amira Ben Salem' })).not.toBeInTheDocument(); // past (422 in_past)
		expect(amira.queryByRole('button', { name: 'Nouveau rendez-vous à 11:45 avec Dr Amira Ben Salem' })).not.toBeInTheDocument(); // taken
		expect(amira.queryByRole('button', { name: 'Nouveau rendez-vous à 13:00 avec Dr Amira Ben Salem' })).not.toBeInTheDocument(); // pause
		expect(karim.getByRole('button', { name: 'Nouveau rendez-vous à 10:15 avec Dr Karim Jaziri' })).toBeInTheDocument();
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
		expect(within(screen.getByRole('region', { name: /mardi 27/ })).queryByRole('button', { name: /^Nouveau rendez-vous à/ })).not.toBeInTheDocument(); // past day
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

	it('opens the appointment dialog from a free slot and shows the saved appointment', async () => {
		let saved = false;
		agendaApi({
			'GET /api/appointments?from=2026-10-30&to=2026-10-30': () => json(200, saved ? [sami, appt({ id: 9, practitionerId: 12, startsAt: '2026-10-30T10:15:00+01:00' })] : [sami]),
			'GET /api/patients?q=Sami&limit=8': () => json(200, { items: [{ ...sami.patient, birthYear: null, lang: 'fr', reminderConsent: true, attended: 1, dueMillimes: 0, nextAppointmentAt: null }], total: 1 }),
			'POST /api/appointments': () => {
				saved = true;
				return json(201, { appointment: appt({ id: 9, practitionerId: 12, startsAt: '2026-10-30T10:15:00+01:00' }), conflicts: [] });
			}
		});
		render(Page);
		const karim = within(await screen.findByRole('region', { name: 'Dr Karim Jaziri' }));
		await fireEvent.click(karim.getByRole('button', { name: 'Nouveau rendez-vous à 10:15 avec Dr Karim Jaziri' }));
		const dialog = within(screen.getByRole('dialog', { name: 'Nouveau rendez-vous' }));
		expect(dialog.getByLabelText('Heure')).toHaveValue('10:15');
		expect(dialog.getByLabelText('Praticien')).toHaveValue('12');
		await fireEvent.input(dialog.getByLabelText('Nom ou téléphone'), { target: { value: 'Sami' } });
		await fireEvent.click(await dialog.findByRole('button', { name: /Sami Trabelsi/ }));
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer le rendez-vous' }));
		expect(await screen.findByRole('status')).toHaveTextContent('Rendez-vous enregistré.');
		expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
		expect(await karim.findByRole('button', { name: /10:15 Sami Trabelsi/ })).toBeInTheDocument();
	});

	it('"Nouveau rendez-vous" proposes the next slot from now', async () => {
		agendaApi({ 'GET /api/appointments?from=2026-10-30&to=2026-10-30': () => json(200, []) });
		render(Page);
		await screen.findByText('Aucun rendez-vous ce jour.');
		await fireEvent.click(screen.getByRole('button', { name: 'Nouveau rendez-vous' }));
		const dialog = within(screen.getByRole('dialog', { name: 'Nouveau rendez-vous' }));
		expect(dialog.getByLabelText('Date')).toHaveValue('2026-10-30');
		expect(dialog.getByLabelText('Heure')).toHaveValue('10:15');
		expect(dialog.getByLabelText('Praticien')).toHaveValue('');
	});

	it('opens a new appointment for the patient given in the address (from the patient file)', async () => {
		agendaApi({
			'GET /api/appointments?from=2026-10-30&to=2026-10-30': () => json(200, []),
			'GET /api/patients/7': () =>
				json(200, { id: 7, firstName: 'Amel', lastName: 'Gharbi', phone: '+21620555666', noShows: 0, alerts: '', birthYear: null, lang: 'fr', reminderConsent: true, attended: 0, dueMillimes: 0, nextAppointmentAt: null, notes: '', createdAt: '', cancelled: 0, totalMillimes: 0, paidMillimes: 0 })
		});
		history.replaceState(null, '', '/app/agenda?nouveau=1&patient=7');
		render(Page);
		const dialog = within(await screen.findByRole('dialog', { name: 'Nouveau rendez-vous' }));
		expect(await dialog.findByText('Amel Gharbi')).toBeInTheDocument();
	});

	it('opens an appointment, changes its status in place and moves it', async () => {
		agendaApi({
			'GET /api/appointments?from=2026-10-30&to=2026-10-30': () => json(200, [lina]),
			'POST /api/appointments/2/status': () => json(200, { ...lina, status: 'arrived' })
		});
		render(Page);
		await fireEvent.click(await screen.findByRole('button', { name: /11:00 Lina Zouari/ }));
		await fireEvent.click(within(screen.getByRole('dialog', { name: 'Lina Zouari' })).getByRole('button', { name: 'Déplacer / modifier' }));
		const move = within(screen.getByRole('dialog', { name: 'Modifier le rendez-vous' }));
		expect(move.getByLabelText('Heure')).toHaveValue('11:00');
		expect(screen.queryByRole('dialog', { name: 'Lina Zouari' })).not.toBeInTheDocument();
		await fireEvent.click(move.getByRole('button', { name: 'Annuler' }));

		const karim = within(screen.getByRole('region', { name: 'Dr Karim Jaziri' }));
		await fireEvent.click(karim.getByRole('button', { name: /11:00 Lina Zouari/ }));
		const dialog = within(screen.getByRole('dialog', { name: 'Lina Zouari' }));
		await fireEvent.click(dialog.getByRole('button', { name: 'Arrivé' }));
		await vi.waitFor(() => expect(karim.getByRole('button', { name: /11:00 Lina Zouari/ })).toHaveTextContent('Arrivé'));
		expect(dialog.queryByRole('button', { name: 'Déplacer / modifier' })).not.toBeInTheDocument(); // 409 appointment_locked
	});

	it('opens a new appointment when the N shortcut is pressed on the agenda', async () => {
		agendaApi({ 'GET /api/appointments?from=2026-10-30&to=2026-10-30': () => json(200, []) });
		render(Page);
		await screen.findByText('Aucun rendez-vous ce jour.');
		expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
		newAppointment.request();
		expect(await screen.findByRole('dialog', { name: 'Nouveau rendez-vous' })).toBeInTheDocument();
	});
});
