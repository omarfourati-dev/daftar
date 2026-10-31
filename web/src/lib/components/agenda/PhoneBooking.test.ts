import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PhoneBooking from './PhoneBooking.svelte';
import { auth } from '../../auth.svelte';
import { clock } from '../../clock';
import { i18n } from '../../i18n.svelte';
import { calls, json, mockApi, problem, sentJson, type Handler } from '../../test-utils';
import { appt, assistant, NOW, practice, practitioners, services } from '../../agenda/fixtures';
import { summary } from '../../agenda/patient-fixtures';

const free = [
	{ startsAt: '2026-10-30T10:30:00+01:00', practitionerId: 11 },
	{ startsAt: '2026-10-31T09:00:00+01:00', practitionerId: 12 },
	{ startsAt: '2026-11-03T08:00:00+01:00', practitionerId: null }
];

function phoneApi(extra: Record<string, Handler> = {}) {
	return mockApi({
		'GET /api/practice': () => json(200, practice),
		'GET /api/practitioners': () => json(200, practitioners),
		'GET /api/services': () => json(200, services),
		'GET /api/closures': () => json(200, []),
		...extra
	});
}

function open() {
	const onclose = vi.fn();
	const onbooked = vi.fn();
	render(PhoneBooking, { props: { onclose, onbooked } });
	return { onclose, onbooked, dialog: within(screen.getByRole('dialog', { name: 'Rendez-vous par téléphone' })) };
}

describe('PhoneBooking – appointment on the phone (section 16.1)', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
		clock.now = () => new Date(NOW);
	});

	it('starts with the number, proposes the next free times and books in one click', async () => {
		const booked = appt({ id: 60, startsAt: '2026-10-30T10:30:00+01:00', serviceId: 22, reason: 'Contrôle' });
		phoneApi({
			'GET /api/patients?q=20123&limit=8': () => json(200, { items: [summary()], total: 1 }),
			'GET /api/availability/next?patientId=7&limit=8': () => json(200, free),
			'GET /api/availability/next?serviceId=22&patientId=7&limit=8': () => json(200, free),
			'POST /api/appointments': () => json(201, { appointment: booked, conflicts: [] })
		});
		const writeText = vi.fn(async () => undefined);
		Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
		const { dialog, onbooked } = open();
		await fireEvent.input(dialog.getByLabelText('Numéro de l’appelant'), { target: { value: '20 123' } });
		await fireEvent.click(await dialog.findByRole('button', { name: /Sami Trabelsi/ }));
		await fireEvent.change(await dialog.findByLabelText('Acte / consultation'), { target: { value: '22' } });
		const list = within(await dialog.findByRole('region', { name: 'Prochains créneaux libres' }));
		expect(await list.findByRole('heading', { name: 'Aujourd’hui' })).toBeInTheDocument();
		expect(list.getByRole('heading', { name: 'Demain' })).toBeInTheDocument();
		expect(list.getByRole('heading', { name: /mar\. 3 nov\./ })).toBeInTheDocument();
		await fireEvent.click(list.getByRole('button', { name: '10:30 – Dr Amira Ben Salem' }));
		await vi.waitFor(() => expect(onbooked).toHaveBeenCalledWith(booked));
		expect(sentJson('POST /api/appointments')).toEqual({
			patientId: 7,
			startsAt: '2026-10-30T10:30:00+01:00',
			reason: 'Contrôle',
			serviceId: 22,
			practitionerId: 11,
			notes: '',
			depositRequiredMillimes: 0
		});
		expect(await dialog.findByText(/Rendez-vous enregistré/)).toBeInTheDocument();
		const message = dialog.getByLabelText('Message de confirmation') as HTMLTextAreaElement;
		expect(message.value).toContain('Bonjour Sami, votre rendez-vous au Cabinet du Lac le 30/10/2026 à 10:30 est confirmé.');
		await fireEvent.click(dialog.getByRole('button', { name: 'Copier le texte' }));
		expect(writeText).toHaveBeenCalledWith(message.value);
		expect(await dialog.findByText('Texte copié.')).toBeInTheDocument();
		expect(dialog.getByRole('link', { name: 'WhatsApp' }).getAttribute('href')).toContain('https://wa.me/21620123456?text=');
		expect(dialog.getByRole('link', { name: 'SMS' }).getAttribute('href')).toContain('sms:+21620123456?&body=');
	});

	it('writes the confirmation in the caller’s language, not the screen’s (fixlist 2)', async () => {
		const caller = summary({ lang: 'ar' });
		const booked = appt({ id: 62, startsAt: '2026-10-30T10:30:00+01:00', patient: { id: 7, firstName: 'Sami', lastName: 'Trabelsi', phone: '+21620123456', noShows: 0, lang: 'ar' } });
		phoneApi({
			'GET /api/patients?q=20123&limit=8': () => json(200, { items: [caller], total: 1 }),
			'GET /api/availability/next?patientId=7&limit=8': () => json(200, free),
			'POST /api/appointments': () => json(201, { appointment: booked, conflicts: [] })
		});
		const { dialog } = open();
		await fireEvent.input(dialog.getByLabelText('Numéro de l’appelant'), { target: { value: '20 123' } });
		await fireEvent.click(await dialog.findByRole('button', { name: /Sami Trabelsi/ }));
		const list = within(await dialog.findByRole('region', { name: 'Prochains créneaux libres' }));
		await fireEvent.click(await list.findByRole('button', { name: '10:30 – Dr Amira Ben Salem' }));
		const message = (await dialog.findByLabelText('Message de confirmation')) as HTMLTextAreaElement;
		expect(message.value).toContain('مرحبًا Sami، تم تأكيد موعدك');
		expect(message.value).toContain('30/10/2026');
	});

	it('creates a new caller with this number when booking', async () => {
		phoneApi({
			'GET /api/patients?q=20555666&limit=8': () => json(200, { items: [], total: 0 }),
			'GET /api/availability/next?limit=8': () => json(200, free),
			'POST /api/patients': () => json(201, { ...summary({ id: 77, firstName: 'Amel', lastName: 'Gharbi', phone: '+21620555666' }) }),
			'POST /api/appointments': () => json(201, { appointment: appt({ id: 61 }), conflicts: [] })
		});
		const { dialog } = open();
		await fireEvent.input(dialog.getByLabelText('Numéro de l’appelant'), { target: { value: '20 555 666' } });
		await fireEvent.click(await dialog.findByRole('button', { name: 'Nouveau patient avec ce numéro' }));
		await fireEvent.input(dialog.getByLabelText('Prénom'), { target: { value: 'Amel' } });
		await fireEvent.input(dialog.getByLabelText('Nom'), { target: { value: 'Gharbi' } });
		const list = within(await dialog.findByRole('region', { name: 'Prochains créneaux libres' }));
		await fireEvent.click(await list.findByRole('button', { name: '10:30 – Dr Amira Ben Salem' }));
		await vi.waitFor(() => expect(sentJson('POST /api/appointments')).toMatchObject({ patientId: 77, practitionerId: 11 }));
		expect(sentJson('POST /api/patients')).toEqual({ firstName: 'Amel', lastName: 'Gharbi', phone: '20 555 666', lang: 'fr', reminderConsent: false });
	});

	it('when the time was taken in between, says so and shows fresh times', async () => {
		let round = 0;
		phoneApi({
			'GET /api/patients?q=20123&limit=8': () => json(200, { items: [summary()], total: 1 }),
			'GET /api/availability/next?patientId=7&limit=8': () => json(200, round++ === 0 ? free : free.slice(1)),
			'POST /api/appointments': () => problem(409, 'appointment_conflict')
		});
		const { dialog } = open();
		await fireEvent.input(dialog.getByLabelText('Numéro de l’appelant'), { target: { value: '20 123' } });
		await fireEvent.click(await dialog.findByRole('button', { name: /Sami Trabelsi/ }));
		const list = within(await dialog.findByRole('region', { name: 'Prochains créneaux libres' }));
		await fireEvent.click(await list.findByRole('button', { name: '10:30 – Dr Amira Ben Salem' }));
		expect(await dialog.findByRole('alert')).toHaveTextContent('Ce créneau vient d’être pris.');
		await vi.waitFor(() => expect(list.queryByRole('button', { name: '10:30 – Dr Amira Ben Salem' })).not.toBeInTheDocument());
		expect(calls().filter((c) => c.startsWith('GET /api/availability/next'))).toHaveLength(2);
	});

	it('says when nothing is free', async () => {
		phoneApi({
			'GET /api/patients?q=20123&limit=8': () => json(200, { items: [summary()], total: 1 }),
			'GET /api/availability/next?patientId=7&limit=8': () => json(200, [])
		});
		const { dialog } = open();
		await fireEvent.input(dialog.getByLabelText('Numéro de l’appelant'), { target: { value: '20123' } });
		await fireEvent.click(await dialog.findByRole('button', { name: /Sami Trabelsi/ }));
		expect(await dialog.findByText('Aucun créneau libre dans les 14 prochains jours.')).toBeInTheDocument();
	});

	it('works in Arabic', () => {
		i18n.setLocale('ar');
		phoneApi();
		render(PhoneBooking, { props: { onclose: vi.fn(), onbooked: vi.fn() } });
		expect(screen.getByRole('dialog', { name: 'موعد بالهاتف' })).toBeInTheDocument();
		expect(screen.getByLabelText('رقم المتّصل')).toBeInTheDocument();
	});
});
