import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { clock } from '#lib/clock';
import { i18n } from '#lib/i18n.svelte';
import { json, mockApi, problem, sentJson, type Handler } from '#lib/test-utils';
import { assistant, NOW, practice } from '#lib/agenda/fixtures';
import type { QueueEntry } from '#lib/types/queue';

function entry(over: Partial<QueueEntry>): QueueEntry {
	return {
		id: 1,
		ticketNo: 1,
		name: 'Sami Trabelsi',
		phone: '+21620123456',
		patientId: 7,
		appointmentId: null,
		appointmentAt: null,
		status: 'waiting',
		arrivedAt: '2026-10-30T09:40:00+01:00',
		calledAt: null,
		doneAt: null,
		ticketToken: 'tk-1',
		position: null,
		peopleAhead: null,
		estimatedWaitMin: null,
		alerts: '',
		...over
	};
}

const inTreatment = entry({ id: 11, ticketNo: 11, name: 'Yassine Ayari', status: 'in_treatment', calledAt: '2026-10-30T09:05:00+01:00', ticketToken: 'tk-11' });
const called = entry({ id: 13, ticketNo: 13, name: 'Leila Karoui', status: 'called', appointmentAt: '2026-10-30T10:45:00+01:00', ticketToken: 'tk-13' });
const first = entry({ id: 14, ticketNo: 14, name: 'Lina Zouari', phone: '+21620000002', position: 1, peopleAhead: 0, estimatedWaitMin: 0, appointmentAt: '2026-10-30T11:00:00+01:00', alerts: 'Allergie pénicilline', ticketToken: 'tk-14' });
const second = entry({ id: 15, ticketNo: 15, name: 'Mohamed Ali Kefi', phone: null, patientId: null, position: 2, peopleAhead: 1, estimatedWaitMin: 20, ticketToken: 'tk-15' });
const finished = entry({ id: 10, ticketNo: 10, name: 'Meriem Mahjoub', status: 'done', doneAt: '2026-10-30T09:50:00+01:00', ticketToken: 'tk-10' });

function salleApi(list: QueueEntry[], extra: Record<string, Handler> = {}) {
	return mockApi({
		'GET /api/queue': () => json(200, list),
		'GET /api/practice': () => json(200, practice),
		'GET /api/badges': () => json(200, { onlineRequests: 0, overdue: 0 }),
		...extra
	});
}

describe('/app/salle – the waiting room at the desk', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
		clock.now = () => new Date(NOW);
	});

	it('shows the tickets by step with numbers, names, appointment and expected wait', async () => {
		salleApi([first, inTreatment, finished, called, second]);
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'Salle d’attente' })).toBeInTheDocument();
		const waiting = within(await screen.findByRole('region', { name: 'En attente' }));
		const cards = waiting.getAllByRole('listitem');
		expect(cards[0]).toHaveTextContent('14');
		expect(cards[0]).toHaveTextContent('Lina Zouari');
		expect(cards[0]).toHaveTextContent('RDV 11:00');
		expect(cards[0]).toHaveTextContent('Allergie pénicilline');
		expect(cards[1]).toHaveTextContent('Sans rendez-vous');
		expect(cards[1]).toHaveTextContent('Position 2');
		expect(cards[1]).toHaveTextContent('env. 20 min');
		expect(within(screen.getByRole('region', { name: 'En consultation' })).getByText('Yassine Ayari')).toBeInTheDocument();
		expect(within(screen.getByRole('region', { name: 'Appelés' })).getByText('Leila Karoui')).toBeInTheDocument();
		expect(within(screen.getByRole('region', { name: 'Terminés aujourd’hui' })).getByText('Meriem Mahjoub')).toBeInTheDocument();
		// the screen preview: numbers only
		const preview = within(screen.getByRole('region', { name: 'Écran de la salle d’attente' }));
		expect(preview.getByText('13')).toBeInTheDocument();
		expect(preview.queryByText(/Leila/)).not.toBeInTheDocument();
		expect(screen.getByRole('link', { name: /Écran de la salle/ })).toHaveAttribute('href', '/salle/ecran-0123456789abcdef');
		expect(screen.getByRole('link', { name: 'Patient suivant' })).toHaveAttribute('href', '/app/salle/suivant');
	});

	it('calls the next patient, then starts and ends the consultation', async () => {
		let list = [first];
		salleApi(list, {
			'GET /api/queue': () => json(200, list),
			'POST /api/queue/14/status': (init) => {
				const status = JSON.parse(String(init?.body)).status;
				list = [{ ...first, status, position: null }];
				return json(200, list[0]);
			}
		});
		render(Page);
		const card = async () => within((await screen.findByText('Lina Zouari')).closest('li') as HTMLElement);
		await fireEvent.click((await card()).getByRole('button', { name: 'Appeler' }));
		expect(sentJson('POST /api/queue/14/status')).toEqual({ status: 'called' });
		expect(await screen.findByText('Ticket 14 : Appelé.')).toBeInTheDocument();
		await fireEvent.click(await (await card()).findByRole('button', { name: 'En consultation' }));
		expect(await screen.findByText('Ticket 14 : En soins.')).toBeInTheDocument();
		await fireEvent.click(await (await card()).findByRole('button', { name: 'Terminé' }));
		expect(await screen.findByText('Ticket 14 : Terminé.')).toBeInTheDocument();
	});

	it('records that a patient left', async () => {
		salleApi([second], { 'POST /api/queue/15/status': () => json(200, { ...second, status: 'left' }) });
		render(Page);
		const card = within((await screen.findByText('Mohamed Ali Kefi')).closest('li') as HTMLElement);
		await fireEvent.click(card.getByRole('button', { name: 'Parti' }));
		await vi.waitFor(() => expect(sentJson('POST /api/queue/15/status')).toEqual({ status: 'left' }));
	});

	it('gives each ticket a WhatsApp link and a QR code to its page (numbers only)', async () => {
		salleApi([first, second]);
		render(Page);
		const card = within((await screen.findByText('Lina Zouari')).closest('li') as HTMLElement);
		const link = card.getByRole('link', { name: 'WhatsApp' });
		const href = decodeURIComponent(link.getAttribute('href') ?? '');
		expect(href).toContain('https://wa.me/21620000002?text=');
		expect(href).toContain(`${location.origin}/ticket/tk-14`);
		expect(href).toContain('n° 14');
		expect(within((screen.getByText('Mohamed Ali Kefi')).closest('li') as HTMLElement).queryByRole('link', { name: 'WhatsApp' })).not.toBeInTheDocument();
		await fireEvent.click(card.getByRole('button', { name: 'QR code' }));
		const dialog = within(await screen.findByRole('dialog', { name: 'Ticket 14' }));
		const qr = await dialog.findByRole('img', { name: 'QR code du ticket 14' });
		expect(qr.querySelector('svg')).not.toBeNull();
		expect(dialog.getByRole('link', { name: 'Ouvrir la page du ticket' })).toHaveAttribute('href', '/ticket/tk-14');
	});

	it('gives a ticket to a known patient and shows the QR code right away', async () => {
		const created = entry({ id: 17, ticketNo: 17, name: 'Sami Trabelsi', position: 3, ticketToken: 'tk-17' });
		salleApi([], {
			'GET /api/patients?q=Sami&limit=8': () =>
				json(200, { items: [{ id: 7, firstName: 'Sami', lastName: 'Trabelsi', phone: '+21620123456', birthYear: null, lang: 'fr', reminderConsent: true, noShows: 0, attended: 2, dueMillimes: 0, nextAppointmentAt: null }], total: 1 }),
			'POST /api/queue': () => json(201, created)
		});
		render(Page);
		expect(await screen.findByText('Personne en salle d’attente.')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Nouveau ticket' }));
		const dialog = within(screen.getByRole('dialog', { name: 'Nouveau ticket' }));
		await fireEvent.input(dialog.getByLabelText('Nom ou téléphone'), { target: { value: 'Sami' } });
		await fireEvent.click(await dialog.findByRole('button', { name: /Sami Trabelsi/ }));
		await fireEvent.click(dialog.getByRole('button', { name: 'Donner le ticket' }));
		await vi.waitFor(() => expect(sentJson('POST /api/queue')).toEqual({ patientId: 7 }));
		expect(await dialog.findByText('Ticket 17 pour Sami Trabelsi')).toBeInTheDocument();
		expect(await dialog.findByRole('img', { name: 'QR code du ticket 17' })).toBeInTheDocument();
		expect(dialog.getByRole('link', { name: 'WhatsApp' })).toBeInTheDocument();
	});

	it('gives a ticket with just a name and phone', async () => {
		salleApi([], { 'POST /api/queue': () => json(201, entry({ id: 18, ticketNo: 18, name: 'Mme Gharbi', phone: null, patientId: null, ticketToken: 'tk-18' })) });
		render(Page);
		await fireEvent.click(await screen.findByRole('button', { name: 'Nouveau ticket' }));
		const dialog = within(screen.getByRole('dialog', { name: 'Nouveau ticket' }));
		await fireEvent.click(dialog.getByRole('radio', { name: 'Juste un nom' }));
		await fireEvent.click(dialog.getByRole('button', { name: 'Donner le ticket' }));
		expect(await dialog.findByRole('alert')).toHaveTextContent('Indiquez un nom ou choisissez un patient.');
		await fireEvent.input(dialog.getByLabelText('Nom'), { target: { value: 'Mme Gharbi' } });
		await fireEvent.input(dialog.getByLabelText('Téléphone (facultatif)'), { target: { value: '20 111 222' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Donner le ticket' }));
		await vi.waitFor(() => expect(sentJson('POST /api/queue')).toEqual({ name: 'Mme Gharbi', phone: '20 111 222' }));
	});

	it('refreshes by itself every 20 seconds', async () => {
		vi.useFakeTimers({ shouldAdvanceTime: true });
		const fetch = salleApi([first]);
		render(Page);
		await screen.findByText('Lina Zouari');
		const before = fetch.mock.calls.filter(([url]) => url === '/api/queue').length;
		await vi.advanceTimersByTimeAsync(20_000);
		expect(fetch.mock.calls.filter(([url]) => url === '/api/queue').length).toBe(before + 1);
		vi.useRealTimers();
	});

	it('explains a loading problem and works in Arabic', async () => {
		i18n.setLocale('ar');
		salleApi([], { 'GET /api/queue': () => problem(500, 'server_error') });
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'قاعة الانتظار' })).toBeInTheDocument();
		expect(await screen.findByRole('alert')).toHaveTextContent('تعذّر تحميل قاعة الانتظار.');
	});
});
