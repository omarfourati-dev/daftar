import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { clock } from '#lib/clock';
import { i18n } from '#lib/i18n.svelte';
import { json, mockApi, problem, sentJson, type Handler } from '#lib/test-utils';
import { appt, assistant, NOW, practitioners } from '#lib/agenda/fixtures';
import type { QueueEntry } from '#lib/types/queue';

function entry(over: Partial<QueueEntry>): QueueEntry {
	return {
		id: 14,
		ticketNo: 14,
		name: 'Lina Zouari',
		phone: '+21620000002',
		patientId: 9,
		appointmentId: 2,
		appointmentAt: '2026-10-30T10:15:00+01:00',
		status: 'waiting',
		arrivedAt: '2026-10-30T10:00:00+01:00',
		calledAt: null,
		doneAt: null,
		ticketToken: 'tk-14',
		position: 1,
		peopleAhead: 0,
		estimatedWaitMin: 0,
		alerts: 'Allergie pénicilline',
		...over
	};
}
const next = {
	entry: entry({}),
	reason: 'appointment',
	lateAppointments: [appt({ id: 3, startsAt: '2026-10-30T09:45:00+01:00', patient: { id: 4, firstName: 'Hichem', lastName: 'Bouzid', phone: '+21620000007', noShows: 1, lang: 'fr' } })],
	upcoming: [entry({ id: 15, ticketNo: 15, name: 'Mohamed Ali Kefi', appointmentAt: null, alerts: '' }), entry({ id: 16, ticketNo: 16, name: 'Walid Hammami', alerts: '' })]
};

function nextApi(extra: Record<string, Handler> = {}) {
	return mockApi({
		'GET /api/practitioners': () => json(200, practitioners),
		'GET /api/queue/next': () => json(200, next),
		...extra
	});
}

describe('/app/salle/suivant – who is next (section 16.2)', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
		clock.now = () => new Date(NOW);
		localStorage.removeItem('daftar.next.practitioner');
	});

	it('shows now and then, with the reason, the alert and the late appointments', async () => {
		nextApi();
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'Patient suivant' })).toBeInTheDocument();
		const now = within(await screen.findByRole('region', { name: 'Maintenant' }));
		expect(now.getByText('14')).toBeInTheDocument();
		expect(now.getByText('Lina Zouari')).toBeInTheDocument();
		expect(now.getByText('Rendez-vous de 10:15')).toBeInTheDocument();
		expect(now.getByText('Allergie pénicilline')).toBeInTheDocument();
		const then = within(screen.getByRole('region', { name: 'Ensuite' }));
		expect(then.getAllByRole('listitem').map((li) => li.textContent)).toEqual([expect.stringContaining('15'), expect.stringContaining('16')]);
		expect(then.getByText('Liste d’attente (ticket 15)')).toBeInTheDocument();
		const late = within(screen.getByRole('region', { name: 'En retard' }));
		expect(late.getByText('Hichem Bouzid')).toBeInTheDocument();
		expect(late.getByText('09:45')).toBeInTheDocument();
		expect(late.getByRole('link', { name: /Appeler/ })).toHaveAttribute('href', 'tel:+21620000007');
	});

	it('calls the next patient with one big button', async () => {
		nextApi({ 'POST /api/queue/call-next': () => json(200, entry({ status: 'called', calledAt: NOW })) });
		render(Page);
		await fireEvent.click(await screen.findByRole('button', { name: 'Appeler le suivant' }));
		expect(sentJson('POST /api/queue/call-next')).toEqual({});
		expect(await screen.findByRole('status')).toHaveTextContent('Ticket 14 appelé : Lina Zouari.');
	});

	it('works for one practitioner (remembered on this device)', async () => {
		nextApi({
			'GET /api/queue/next?practitionerId=12': () => json(200, { ...next, entry: entry({ id: 16, ticketNo: 16, name: 'Walid Hammami' }) }),
			'POST /api/queue/call-next': () => json(200, entry({ id: 16, ticketNo: 16, name: 'Walid Hammami', status: 'called' }))
		});
		render(Page);
		await fireEvent.click(await screen.findByRole('button', { name: 'Dr Karim Jaziri' }));
		expect(await within(screen.getByRole('region', { name: 'Maintenant' })).findByText('Walid Hammami')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Appeler le suivant' }));
		await vi.waitFor(() => expect(sentJson('POST /api/queue/call-next')).toEqual({ practitionerId: 12 }));
		expect(localStorage.getItem('daftar.next.practitioner')).toBe('12');
	});

	it('says when nobody waits, also when the server finds the queue empty', async () => {
		nextApi({
			'GET /api/queue/next': () => json(200, { entry: null, reason: null, lateAppointments: [], upcoming: [] }),
			'POST /api/queue/call-next': () => problem(409, 'queue_empty')
		});
		render(Page);
		expect(await screen.findByText('Personne n’attend.')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Appeler le suivant' })).toBeDisabled();
		expect(screen.queryByRole('region', { name: 'En retard' })).not.toBeInTheDocument();
	});

	it('explains the server refusal', async () => {
		nextApi({ 'POST /api/queue/call-next': () => problem(409, 'queue_empty') });
		render(Page);
		await fireEvent.click(await screen.findByRole('button', { name: 'Appeler le suivant' }));
		expect(await screen.findByRole('alert')).toHaveTextContent('Personne n’attend pour le moment.');
	});

	it('is translated into Arabic', async () => {
		i18n.setLocale('ar');
		nextApi();
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'المريض التالي' })).toBeInTheDocument();
		expect(await screen.findByRole('region', { name: 'الآن' })).toBeInTheDocument();
	});
});
