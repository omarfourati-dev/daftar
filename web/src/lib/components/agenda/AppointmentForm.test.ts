import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AppointmentForm from './AppointmentForm.svelte';
import { auth } from '../../auth.svelte';
import { clock } from '../../clock';
import { i18n } from '../../i18n.svelte';
import { calls, json, mockApi, problem, sentJson } from '../../test-utils';
import { appt, assistant, NOW, practice, practitioners, services } from '../../agenda/fixtures';
import type { AgendaBase } from '../../agenda/data';
import type { PatientSummary } from '../../types/patients';

const base: AgendaBase = { practice, practitioners, services: services, closures: [] };
const sami: PatientSummary = {
	id: 7,
	firstName: 'Sami',
	lastName: 'Trabelsi',
	phone: '+21620123456',
	birthYear: 1980,
	lang: 'fr',
	reminderConsent: true,
	noShows: 0,
	attended: 4,
	dueMillimes: 0,
	nextAppointmentAt: null,
	hasAlerts: false
};
const lina: PatientSummary = { ...sami, id: 9, firstName: 'Lina', lastName: 'Zouari', phone: '+21620000002', noShows: 3, hasAlerts: true };

function open(props: Record<string, unknown> = {}) {
	const onsaved = vi.fn();
	const onclose = vi.fn();
	render(AppointmentForm, { props: { base, day: '2026-10-30', time: '09:15', practitionerId: 12, onsaved, onclose, ...props } });
	return { onsaved, onclose };
}

async function search(text: string) {
	await fireEvent.input(screen.getByLabelText('Nom ou téléphone'), { target: { value: text } });
}

describe('AppointmentForm – new appointment in a few clicks', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
		clock.now = () => new Date(NOW);
	});

	it('finds the patient by phone, takes the duration from the service and saves', async () => {
		const created = appt({ id: 40 });
		mockApi({
			'GET /api/patients?q=2012&limit=8': () => json(200, { items: [sami], total: 1 }),
			'POST /api/appointments': () => json(201, { appointment: created, conflicts: [] })
		});
		const { onsaved } = open();
		const dialog = within(screen.getByRole('dialog', { name: 'Nouveau rendez-vous' }));
		expect(dialog.getByLabelText('Heure')).toHaveValue('09:15');
		expect(dialog.getByLabelText('Praticien')).toHaveValue('12');
		await search('2012');
		await fireEvent.click(await dialog.findByRole('button', { name: /Sami Trabelsi/ }));
		expect(dialog.getByText('+216 20 123 456')).toBeInTheDocument();
		await fireEvent.change(dialog.getByLabelText('Acte / consultation'), { target: { value: '22' } });
		expect(dialog.getByLabelText('Durée (min)')).toHaveValue(20);
		expect(dialog.getByLabelText('Motif')).toHaveValue('Contrôle');
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer le rendez-vous' }));
		await vi.waitFor(() => expect(onsaved).toHaveBeenCalledWith(created));
		expect(sentJson('POST /api/appointments')).toEqual({
			patientId: 7,
			startsAt: '2026-10-30T09:15:00+01:00',
			durationMin: 20,
			reason: 'Contrôle',
			serviceId: 22,
			practitionerId: 12,
			notes: '',
			depositRequiredMillimes: 0
		});
	});

	it('asks for a patient before saving', async () => {
		mockApi({});
		open();
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le rendez-vous' }));
		expect(await screen.findByRole('alert')).toHaveTextContent('Choisissez un patient ou créez-en un.');
		expect(calls()).toEqual([]);
	});

	it('creates a new patient in the same dialog (name typed in the search is taken over)', async () => {
		const created = appt({ id: 41 });
		mockApi({
			'GET /api/patients?q=Amel%20Gharbi&limit=8': () => json(200, { items: [], total: 0 }),
			'POST /api/patients': () => json(201, { ...sami, id: 77, firstName: 'Amel', lastName: 'Gharbi' }),
			'POST /api/appointments': () => json(201, created)
		});
		const { onsaved } = open();
		await search('Amel Gharbi');
		expect(await screen.findByText('Aucun patient trouvé.')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Nouveau patient' }));
		expect(screen.getByLabelText('Prénom')).toHaveValue('Amel');
		expect(screen.getByLabelText('Nom')).toHaveValue('Gharbi');
		await fireEvent.input(screen.getByLabelText('Téléphone'), { target: { value: '20 555 666' } });
		await fireEvent.click(screen.getByLabelText('Accepte les rappels par WhatsApp ou SMS'));
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le rendez-vous' }));
		await vi.waitFor(() => expect(onsaved).toHaveBeenCalledWith(created));
		expect(sentJson('POST /api/patients')).toEqual({
			firstName: 'Amel',
			lastName: 'Gharbi',
			phone: '20 555 666',
			lang: 'fr',
			reminderConsent: true
		});
		expect(sentJson('POST /api/appointments')).toMatchObject({ patientId: 77 });
	});

	it('explains an invalid phone number of the new patient', async () => {
		mockApi({ 'POST /api/patients': () => problem(422, 'invalid_phone', 'Numéro de téléphone invalide.') });
		open();
		await fireEvent.click(screen.getByRole('button', { name: 'Nouveau patient' }));
		await fireEvent.input(screen.getByLabelText('Prénom'), { target: { value: 'Amel' } });
		await fireEvent.input(screen.getByLabelText('Nom'), { target: { value: 'Gharbi' } });
		await fireEvent.input(screen.getByLabelText('Téléphone'), { target: { value: '123' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le rendez-vous' }));
		expect(await screen.findByRole('alert')).toHaveTextContent('Numéro de téléphone invalide.');
		expect(calls()).not.toContain('POST /api/appointments');
	});

	it('warns about repeated no-shows, suggests a deposit and shows the medical alert in red', async () => {
		mockApi({
			'GET /api/patients?q=Lina&limit=8': () => json(200, { items: [lina], total: 1 }),
			'GET /api/patients/9': () => json(200, { ...lina, alerts: 'Allergie pénicilline', notes: '', createdAt: '', cancelled: 0, totalMillimes: 0, paidMillimes: 0 }),
			'POST /api/appointments': () => json(201, appt({ id: 42 }))
		});
		open();
		await search('Lina');
		await fireEvent.click(await screen.findByRole('button', { name: /Lina Zouari/ }));
		expect(await screen.findByText('Allergie pénicilline')).toBeInTheDocument();
		expect(screen.getByText('3 absences : acompte conseillé.')).toBeInTheDocument();
		await fireEvent.change(screen.getByLabelText('Acte / consultation'), { target: { value: '21' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Demander 40 DT' }));
		expect(screen.getByLabelText('Acompte demandé (DT)')).toHaveValue('40');
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le rendez-vous' }));
		await vi.waitFor(() => expect(sentJson('POST /api/appointments')).toMatchObject({ depositRequiredMillimes: 40000, serviceId: 21, durationMin: 30 }));
	});

	it('on a taken slot shows the conflict and books a suggested time in one click', async () => {
		let attempt = 0;
		mockApi({
			'GET /api/patients?q=Sami&limit=8': () => json(200, { items: [sami], total: 1 }),
			'POST /api/appointments': () =>
				++attempt === 1
					? json(409, {
							title: 'Conflict',
							detail: 'Créneau déjà pris.',
							code: 'appointment_conflict',
							conflicts: [{ id: 3, startsAt: '2026-10-30T09:00:00+01:00', endsAt: '2026-10-30T09:30:00+01:00', patientName: 'Hichem Bouzid' }],
							suggestions: ['2026-10-30T09:30:00+01:00', '2026-11-02T08:00:00+01:00']
						})
					: json(201, appt({ id: 43, startsAt: '2026-11-02T08:00:00+01:00' }))
		});
		const { onsaved } = open();
		await search('Sami');
		await fireEvent.click(await screen.findByRole('button', { name: /Sami Trabelsi/ }));
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le rendez-vous' }));
		const alert = await screen.findByRole('alert');
		expect(alert).toHaveTextContent('Ce créneau est déjà pris.');
		expect(alert).toHaveTextContent('09:00 · Hichem Bouzid');
		await fireEvent.click(within(alert).getByRole('button', { name: /lun\. 2 nov\. 08:00/ }));
		await vi.waitFor(() => expect(onsaved).toHaveBeenCalled());
		const sent = calls().filter((c) => c === 'POST /api/appointments');
		expect(sent).toHaveLength(2);
		expect(screen.getByLabelText('Date')).toHaveValue('2026-11-02');
	});

	it('moves an existing appointment with PATCH', async () => {
		const existing = appt({ id: 50, practitionerId: 11, startsAt: '2026-10-30T14:00:00+01:00', durationMin: 30, serviceId: 21, reason: 'Consultation' });
		mockApi({ 'PATCH /api/appointments/50': () => json(200, { appointment: { ...existing, startsAt: '2026-10-31T09:00:00+01:00' } }) });
		const { onsaved } = open({ appointment: existing, day: undefined, time: undefined, practitionerId: undefined });
		const dialog = within(screen.getByRole('dialog', { name: 'Modifier le rendez-vous' }));
		expect(dialog.getByText('Sami Trabelsi')).toBeInTheDocument();
		expect(dialog.getByLabelText('Heure')).toHaveValue('14:00');
		await fireEvent.input(dialog.getByLabelText('Date'), { target: { value: '2026-10-31' } });
		await fireEvent.input(dialog.getByLabelText('Heure'), { target: { value: '09:00' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer le rendez-vous' }));
		await vi.waitFor(() => expect(onsaved).toHaveBeenCalled());
		expect(sentJson('PATCH /api/appointments/50')).toMatchObject({ startsAt: '2026-10-31T09:00:00+01:00', practitionerId: 11, durationMin: 30 });
	});

	it('works in Arabic', async () => {
		i18n.setLocale('ar');
		mockApi({});
		open();
		expect(screen.getByRole('dialog', { name: 'موعد جديد' })).toBeInTheDocument();
		expect(screen.getByLabelText('الاسم أو الهاتف')).toBeInTheDocument();
		expect(screen.getByRole('option', { name: 'استشارة' })).toBeInTheDocument();
	});
});

describe('AppointmentForm – series of sessions (kiné, psy)', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
		clock.now = () => new Date(NOW);
	});

	async function choosePatient() {
		await fireEvent.input(screen.getByLabelText('Nom ou téléphone'), { target: { value: 'Sami' } });
		await fireEvent.click(await screen.findByRole('button', { name: /Sami Trabelsi/ }));
	}

	it('checks every session first, lists the taken dates and creates only the free ones', async () => {
		const created = [appt({ id: 60, seriesId: 's1' }), appt({ id: 61, seriesId: 's1' })];
		mockApi({
			'GET /api/patients?q=Sami&limit=8': () => json(200, { items: [sami], total: 1 }),
			'POST /api/appointments/series/preview': () =>
				json(200, {
					occurrences: [
						{ startsAt: '2026-10-30T09:15:00+01:00', endsAt: '2026-10-30T09:45:00+01:00', conflict: null, closed: false },
						{ startsAt: '2026-11-03T09:15:00+01:00', endsAt: '2026-11-03T09:45:00+01:00', conflict: { id: 3, startsAt: '2026-11-03T09:00:00+01:00', patientName: 'Hichem Bouzid' }, closed: false },
						{ startsAt: '2026-11-06T09:15:00+01:00', endsAt: '2026-11-06T09:45:00+01:00', conflict: null, closed: true },
						{ startsAt: '2026-11-10T09:15:00+01:00', endsAt: '2026-11-10T09:45:00+01:00', conflict: null, closed: false }
					]
				}),
			'POST /api/appointments/series': () => json(201, { seriesId: 's1', created, skipped: [{ startsAt: '2026-11-03T09:15:00+01:00', reason: 'conflict' }, { startsAt: '2026-11-06T09:15:00+01:00', reason: 'closed' }] })
		});
		const { onsaved } = open();
		await choosePatient();
		await fireEvent.click(screen.getByLabelText('Répéter (séances)'));
		expect(screen.getByRole('button', { name: 'vendredi' })).toHaveAttribute('aria-pressed', 'true');
		await fireEvent.click(screen.getByRole('button', { name: 'mardi' }));
		await fireEvent.input(screen.getByLabelText('Nombre de séances'), { target: { value: '4' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Vérifier les dates' }));
		expect(await screen.findByText('2 séance(s) impossible(s).')).toBeInTheDocument();
		expect(sentJson('POST /api/appointments/series/preview')).toEqual({
			patientId: 7,
			startsAt: '2026-10-30T09:15:00+01:00',
			durationMin: 30,
			reason: '',
			serviceId: null,
			practitionerId: 12,
			notes: '',
			rule: { weekdays: [2, 5], count: 4 }
		});
		const list = within(screen.getByRole('list', { name: 'Séances régulières' }));
		expect(list.getAllByRole('listitem')).toHaveLength(4);
		expect(list.getByText('Pris : Hichem Bouzid')).toBeInTheDocument();
		expect(list.getByText('Cabinet fermé')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Créer 2 rendez-vous sans les dates prises' }));
		await vi.waitFor(() => expect(onsaved).toHaveBeenCalledWith(created[0], 'Rendez-vous créés : 2. Dates ignorées : 2.'));
		expect(sentJson('POST /api/appointments/series')).toMatchObject({ rule: { weekdays: [2, 5], count: 4 }, skipConflicts: true, patientId: 7 });
	});

	it('creates all sessions when every date is free', async () => {
		const created = [appt({ id: 62, seriesId: 's2' })];
		mockApi({
			'GET /api/patients?q=Sami&limit=8': () => json(200, { items: [sami], total: 1 }),
			'POST /api/appointments/series/preview': () =>
				json(200, { occurrences: [{ startsAt: '2026-10-30T09:15:00+01:00', endsAt: '2026-10-30T09:45:00+01:00', conflict: null, closed: false }] }),
			'POST /api/appointments/series': () => json(201, { seriesId: 's2', created, skipped: [] })
		});
		const { onsaved } = open();
		await choosePatient();
		await fireEvent.click(screen.getByLabelText('Répéter (séances)'));
		await fireEvent.input(screen.getByLabelText('Nombre de séances'), { target: { value: '1' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Vérifier les dates' }));
		expect(await screen.findByText('Toutes les séances sont libres.')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Créer 1 rendez-vous' }));
		await vi.waitFor(() => expect(onsaved).toHaveBeenCalledWith(created[0], 'Rendez-vous créés : 1.'));
		expect(sentJson('POST /api/appointments/series')).toMatchObject({ skipConflicts: false });
	});

	it('checks the dates again after a change', async () => {
		mockApi({
			'GET /api/patients?q=Sami&limit=8': () => json(200, { items: [sami], total: 1 }),
			'POST /api/appointments/series/preview': () =>
				json(200, { occurrences: [{ startsAt: '2026-10-30T09:15:00+01:00', endsAt: '2026-10-30T09:45:00+01:00', conflict: null, closed: false }] })
		});
		open();
		await choosePatient();
		await fireEvent.click(screen.getByLabelText('Répéter (séances)'));
		await fireEvent.click(screen.getByRole('button', { name: 'Vérifier les dates' }));
		await screen.findByText('Toutes les séances sont libres.');
		await fireEvent.click(screen.getByRole('button', { name: 'lundi' }));
		expect(screen.queryByText('Toutes les séances sont libres.')).not.toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Vérifier les dates' })).toBeInTheDocument();
	});
});

describe('AppointmentForm – refusals of the server in plain words', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
		clock.now = () => new Date(NOW);
	});

	it.each([
		['outside_hours', 'Ce rendez-vous sort des heures d’ouverture'],
		['in_past', 'Cette heure est déjà passée.'],
		['closed', 'Le cabinet est fermé ce jour-là.']
	])('%s', async (code, text) => {
		mockApi({
			'GET /api/patients?q=Sami&limit=8': () => json(200, { items: [sami], total: 1 }),
			'POST /api/appointments': () => problem(422, code, 'detail')
		});
		open();
		await fireEvent.input(screen.getByLabelText('Nom ou téléphone'), { target: { value: 'Sami' } });
		await fireEvent.click(await screen.findByRole('button', { name: /Sami Trabelsi/ }));
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le rendez-vous' }));
		expect(await screen.findByRole('alert')).toHaveTextContent(text);
	});
});

