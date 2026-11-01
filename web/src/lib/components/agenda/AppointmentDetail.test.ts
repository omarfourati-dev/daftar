import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AppointmentDetail from './AppointmentDetail.svelte';
import { auth } from '../../auth.svelte';
import { clock } from '../../clock';
import { i18n } from '../../i18n.svelte';
import { calls, json, mockApi, problem, sentJson } from '../../test-utils';
import { appt, assistant, NOW, practice, practitioners, services } from '../../agenda/fixtures';
import type { AgendaBase } from '../../agenda/data';
import type { Appointment } from '../../types/agenda';

const base: AgendaBase = { practice, practitioners, services, closures: [] };

function open(a: Appointment) {
	const onchanged = vi.fn();
	const onmove = vi.fn();
	const onclose = vi.fn();
	render(AppointmentDetail, { props: { appointment: a, base, onchanged, onmove, onclose } });
	return { onchanged, onmove, onclose, dialog: within(screen.getByRole('dialog')) };
}

describe('AppointmentDetail – status workflow with big buttons', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
		clock.now = () => new Date(NOW);
	});

	it('shows who, when, the medical alert, the patient note and links to the file', () => {
		mockApi({});
		const a = appt({
			id: 3,
			status: 'requested',
			source: 'online',
			patientNote: 'Toux depuis trois jours',
			patient: { id: 9, firstName: 'Lina', lastName: 'Zouari', phone: '+21620000002', noShows: 2, lang: 'fr', alerts: 'Allergie pénicilline' }
		});
		const { dialog } = open(a);
		expect(screen.getByRole('dialog', { name: 'Lina Zouari' })).toBeInTheDocument();
		expect(dialog.getByText('Allergie pénicilline')).toBeInTheDocument();
		expect(dialog.getByText('2 absences : acompte conseillé.')).toBeInTheDocument();
		expect(dialog.getByText('Toux depuis trois jours')).toBeInTheDocument();
		expect(dialog.getByText('Demandé en ligne')).toBeInTheDocument();
		expect(dialog.getByText(/09:00 – 09:30/)).toBeInTheDocument();
		expect(dialog.getByText(/avec Dr Amira Ben Salem/)).toBeInTheDocument();
		expect(dialog.getByRole('link', { name: 'Ouvrir le dossier' })).toHaveAttribute('href', '/app/patients/9');
		expect(dialog.getByRole('link', { name: 'Appeler' })).toHaveAttribute('href', 'tel:+21620000002');
	});

	it('offers the optional material once the patient is there, never before (spec stock-hygiène 4.2)', () => {
		mockApi({});
		const { dialog } = open(appt({ id: 4, status: 'in_treatment' }));
		expect(dialog.getByRole('button', { name: 'Noter le matériel utilisé' })).toHaveAttribute('aria-expanded', 'false');
		screen.getByRole('dialog').remove();
		const planned = open(appt({ id: 5, status: 'confirmed' }));
		expect(planned.dialog.queryByRole('button', { name: 'Noter le matériel utilisé' })).not.toBeInTheDocument();
	});

	it('confirms an online request and prepares the WhatsApp message in the patient’s language', async () => {
		const a = appt({ id: 3, status: 'requested', patient: { id: 9, firstName: 'Lina', lastName: 'Zouari', phone: '+21620000002', noShows: 0, lang: 'ar' } });
		mockApi({ 'POST /api/appointments/3/status': () => json(200, { ...a, status: 'confirmed' }) });
		const { dialog, onchanged } = open(a);
		await fireEvent.click(dialog.getByRole('button', { name: 'Confirmer' }));
		await vi.waitFor(() => expect(onchanged).toHaveBeenCalledWith(expect.objectContaining({ id: 3, status: 'confirmed' })));
		expect(sentJson('POST /api/appointments/3/status')).toEqual({ status: 'confirmed' });
		expect(await dialog.findByText('Statut : Confirmé.')).toBeInTheDocument();
		const link = dialog.getByRole('link', { name: 'Prévenir par WhatsApp' });
		const href = link.getAttribute('href') ?? '';
		expect(href.startsWith('https://wa.me/21620000002?text=')).toBe(true);
		const text = decodeURIComponent(href.split('text=')[1]);
		expect(text).toContain('مرحبًا Lina');
		expect(text).toContain('Cabinet du Lac');
		expect(text).toContain('30/10/2026');
		expect(text).toContain('09:00');
		expect(link).toHaveAttribute('target', '_blank');
	});

	it('declines an online request with a French message', async () => {
		const a = appt({ id: 3, status: 'requested', patient: { id: 9, firstName: 'Lina', lastName: 'Zouari', phone: '+21620000002', noShows: 0, lang: 'fr' } });
		mockApi({ 'POST /api/appointments/3/status': () => json(200, { ...a, status: 'cancelled' }) });
		const { dialog } = open(a);
		await fireEvent.click(dialog.getByRole('button', { name: 'Refuser' }));
		const link = await dialog.findByRole('link', { name: 'Prévenir par WhatsApp' });
		expect(decodeURIComponent(link.getAttribute('href') ?? '')).toContain('nous ne pouvons pas vous recevoir le 30/10/2026 à 09:00');
	});

	it('follows the patient through the day: arrived, in consultation, done', async () => {
		let current = appt({ id: 5, status: 'confirmed' });
		mockApi({
			'POST /api/appointments/5/status': (init) => {
				current = { ...current, status: JSON.parse(String(init?.body)).status };
				return json(200, current);
			}
		});
		const { dialog, onchanged } = open(current);
		expect(dialog.queryByRole('button', { name: 'Confirmer' })).not.toBeInTheDocument();
		await fireEvent.click(dialog.getByRole('button', { name: 'Arrivé' }));
		await fireEvent.click(await dialog.findByRole('button', { name: 'En consultation' }));
		await fireEvent.click(await dialog.findByRole('button', { name: 'Terminé' }));
		await vi.waitFor(() => expect(onchanged).toHaveBeenCalledTimes(3));
		expect(onchanged.mock.calls.map(([a]) => a.status)).toEqual(['arrived', 'in_treatment', 'done']);
		expect(await dialog.findByText('Statut : Terminé.')).toBeInTheDocument();
		expect(dialog.queryByRole('button', { name: 'Arrivé' })).not.toBeInTheDocument();
	});

	it('marks a no-show and can undo it', async () => {
		let current = appt({ id: 6, status: 'scheduled' });
		mockApi({
			'POST /api/appointments/6/status': (init) => {
				current = { ...current, status: JSON.parse(String(init?.body)).status };
				return json(200, current);
			}
		});
		const { dialog } = open(current);
		await fireEvent.click(dialog.getByRole('button', { name: 'Absent' }));
		await fireEvent.click(await dialog.findByRole('button', { name: 'Remettre à « prévu »' }));
		await vi.waitFor(() => expect(current.status).toBe('scheduled'));
		expect(calls()).toEqual(['POST /api/appointments/6/status', 'POST /api/appointments/6/status']);
	});

	it('says when the slot was taken in between', async () => {
		const a = appt({ id: 6, status: 'no_show' });
		mockApi({ 'POST /api/appointments/6/status': () => problem(409, 'appointment_conflict', 'Ce créneau est déjà pris.') });
		const { dialog } = open(a);
		await fireEvent.click(dialog.getByRole('button', { name: 'Remettre à « prévu »' }));
		expect(await dialog.findByRole('alert')).toHaveTextContent('Ce créneau est déjà pris.');
	});

	it('cancels only after a clear confirmation', async () => {
		const a = appt({ id: 7, status: 'scheduled' });
		mockApi({ 'POST /api/appointments/7/status': () => json(200, { ...a, status: 'cancelled' }) });
		const { dialog, onchanged } = open(a);
		await fireEvent.click(dialog.getByRole('button', { name: 'Annuler le rendez-vous' }));
		expect(dialog.getByText('Annuler le rendez-vous de Sami Trabelsi le 30/10/2026 à 09:00 ?')).toBeInTheDocument();
		await fireEvent.click(dialog.getByRole('button', { name: 'Garder' }));
		expect(calls()).toEqual([]);
		await fireEvent.click(dialog.getByRole('button', { name: 'Annuler le rendez-vous' }));
		await fireEvent.click(dialog.getByRole('button', { name: 'Oui, annuler' }));
		await vi.waitFor(() => expect(onchanged).toHaveBeenCalledWith(expect.objectContaining({ status: 'cancelled' })));
	});

	it('collects the deposit as a deposit payment linked to the appointment', async () => {
		const a = appt({ id: 8, depositRequiredMillimes: 20000, depositPaidMillimes: 5000 });
		mockApi({ 'POST /api/patients/508/payments': () => json(201, { id: 70, amountMillimes: 15000 }) });
		const { dialog, onchanged } = open(a);
		expect(dialog.getByText('5 DT payé sur 20 DT')).toBeInTheDocument();
		await fireEvent.click(dialog.getByRole('button', { name: 'Encaisser l’acompte' }));
		await vi.waitFor(() => expect(onchanged).toHaveBeenCalledWith(expect.objectContaining({ depositPaidMillimes: 20000 })));
		expect(sentJson('POST /api/patients/508/payments')).toEqual({ amountMillimes: 15000, method: 'cash', appointmentId: 8, isDeposit: true });
		expect(await dialog.findByText('Acompte encaissé.')).toBeInTheDocument();
		expect(dialog.getByRole('link', { name: 'Reçu' })).toHaveAttribute('href', '/app/recu/70');
	});

	it('opens the move dialog', async () => {
		mockApi({});
		const a = appt({ id: 9 });
		const { dialog, onmove } = open(a);
		await fireEvent.click(dialog.getByRole('button', { name: 'Déplacer / modifier' }));
		expect(onmove).toHaveBeenCalledWith(a);
	});
});

describe('AppointmentDetail – series', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
	});

	it('cancels this and the following sessions of a series after confirmation', async () => {
		const a = appt({ id: 11, seriesId: 'abc' });
		mockApi({ 'POST /api/appointments/series/abc/cancel': () => json(200, { cancelled: 3 }) });
		const onseries = vi.fn();
		render(AppointmentDetail, { props: { appointment: a, base, onchanged: vi.fn(), onmove: vi.fn(), onclose: vi.fn(), onseriescancelled: onseries } });
		expect(screen.getByText('Série')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Annuler les séances suivantes' }));
		expect(screen.getByText('Annuler cette séance et toutes les suivantes ?')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Oui, annuler' }));
		await vi.waitFor(() => expect(onseries).toHaveBeenCalledWith(3));
		expect(sentJson('POST /api/appointments/series/abc/cancel')).toEqual({ from: '2026-10-30' });
	});
});

describe('AppointmentDetail – only the steps the server accepts', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
		clock.now = () => new Date(NOW);
	});

	it('offers neither arrival nor no-show for a coming day, but moving', () => {
		mockApi({});
		const { dialog } = open(appt({ id: 90, status: 'scheduled', startsAt: '2026-10-31T09:00:00+01:00' }));
		expect(dialog.getByRole('button', { name: 'Confirmer' })).toBeInTheDocument();
		expect(dialog.queryByRole('button', { name: 'Arrivé' })).not.toBeInTheDocument();
		expect(dialog.queryByRole('button', { name: 'Absent' })).not.toBeInTheDocument();
		expect(dialog.getByRole('button', { name: 'Déplacer / modifier' })).toBeInTheDocument();
	});

	it('offers no no-show before the start of today’s appointment', () => {
		mockApi({});
		const { dialog } = open(appt({ id: 91, status: 'confirmed', startsAt: '2026-10-30T11:00:00+01:00' }));
		expect(dialog.getByRole('button', { name: 'Arrivé' })).toBeInTheDocument();
		expect(dialog.queryByRole('button', { name: 'Absent' })).not.toBeInTheDocument();
	});

	it('does not move a patient who is already there', () => {
		mockApi({});
		const { dialog } = open(appt({ id: 92, status: 'arrived' }));
		expect(dialog.queryByRole('button', { name: 'Déplacer / modifier' })).not.toBeInTheDocument();
	});

	it('offers no cancelling during the consultation – the server refuses it (code review N2)', () => {
		mockApi({});
		const { dialog } = open(appt({ id: 94, status: 'in_treatment' }));
		expect(dialog.queryByRole('button', { name: 'Annuler le rendez-vous' })).not.toBeInTheDocument();
		expect(dialog.getByRole('button', { name: 'Terminé' })).toBeInTheDocument();
	});

	it('explains the server’s refusal in plain words', async () => {
		const a = appt({ id: 93, status: 'confirmed' });
		mockApi({ 'POST /api/appointments/93/status': () => problem(409, 'not_today', 'Not today.') });
		const { dialog } = open(a);
		await fireEvent.click(dialog.getByRole('button', { name: 'Arrivé' }));
		expect(await dialog.findByRole('alert')).toHaveTextContent('Ce statut n’est possible que le jour du rendez-vous.');
	});
});

