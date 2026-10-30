import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import BookingPage from './BookingPage.svelte';
import Root from '../../../routes/+page.svelte';
import { bookingDeps } from '../../booking';
import { hostDeps } from '../../host';
import { defaultWeeklyHours } from '../../hours';
import { i18n } from '../../i18n.svelte';
import { calls, json, mockApi, problem, sentJson } from '../../test-utils';
import type { PublicPracticeProfile } from '../../types/booking';

const profile: PublicPracticeProfile = {
	slug: 'cabinet-lac',
	name: 'Cabinet Dr Ben Salah',
	nameAr: 'عيادة الدكتورة بن صالح',
	specialty: 'generaliste',
	address: '14 avenue Habib Bourguiba',
	city: 'Sousse',
	governorate: 'sousse',
	phone: '+21673123456',
	whatsapp: '+21620123456',
	mapsUrl: 'https://maps.app.goo.gl/abc',
	descriptionFr: 'Parking gratuit devant le cabinet.',
	descriptionAr: '',
	weeklyHours: defaultWeeklyHours(),
	brandColor: '#0f766e',
	onlineBookingEnabled: true,
	services: [
		{ id: 11, nameFr: 'Consultation', nameAr: 'معاينة', durationMin: 20, priceMillimes: 50000 },
		{ id: 12, nameFr: 'Contrôle', nameAr: 'مراقبة', durationMin: 15, priceMillimes: null }
	],
	practitioners: [
		{ id: 21, name: 'Amira Ben Salah', title: 'Dr.' },
		{ id: 22, name: 'Karim Trabelsi', title: 'Dr.' }
	],
	horizonDays: 14
};

const PROFILE = 'GET /api/public/practices/cabinet-lac';
const slotsUrl = (date: string, service = 11, practitioner?: number) =>
	`GET /api/public/practices/cabinet-lac/slots?date=${date}&serviceId=${service}${practitioner ? `&practitionerId=${practitioner}` : ''}`;

async function chooseConsultationAt(time = '10:20') {
	await fireEvent.click(await screen.findByRole('radio', { name: /Consultation/ }));
	await fireEvent.click(await screen.findByRole('radio', { name: time }));
	await fireEvent.click(screen.getByRole('button', { name: 'Continuer' }));
}

async function fillDetails() {
	await fireEvent.input(screen.getByLabelText('Prénom'), { target: { value: 'Mounia' } });
	await fireEvent.input(screen.getByLabelText('Nom'), { target: { value: 'Chebbi' } });
	await fireEvent.input(screen.getByLabelText('Téléphone'), { target: { value: '20 123 456' } });
}

describe('online booking page', () => {
	beforeEach(() => {
		i18n.setLocale('fr');
		vi.useFakeTimers({ toFake: ['Date'] });
		vi.setSystemTime(new Date('2026-11-02T08:00:00+01:00')); // a Monday
	});
	afterEach(() => vi.useRealTimers());

	it('shows the practice: names, specialty, contact, directions and opening hours', async () => {
		mockApi({ [PROFILE]: () => json(200, profile) });
		render(BookingPage, { props: { slug: 'cabinet-lac' } });
		expect(await screen.findByRole('heading', { level: 1, name: 'Cabinet Dr Ben Salah' })).toBeInTheDocument();
		expect(screen.getByText('عيادة الدكتورة بن صالح')).toBeInTheDocument();
		expect(screen.getByText('Médecine générale · Sousse')).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Appeler' })).toHaveAttribute('href', 'tel:+21673123456');
		expect(screen.getByRole('link', { name: 'WhatsApp' }).getAttribute('href')).toBe('https://wa.me/21620123456?text=');
		expect(screen.getByRole('link', { name: 'Itinéraire' })).toHaveAttribute('href', 'https://maps.app.goo.gl/abc');
		expect(screen.getByText('Parking gratuit devant le cabinet.')).toBeInTheDocument();
		const hours = within(screen.getByRole('list', { name: 'Horaires d’ouverture' }));
		expect(hours.getByText('Lun. – Sam.')).toBeInTheDocument();
		expect(hours.getByText('08:00–12:30 · 14:00–18:00')).toBeInTheDocument();
		expect(hours.getByText('Fermé')).toBeInTheDocument();
	});

	it('books: act → practitioner → day → free time → details → confirmation with a personal link', async () => {
		mockApi({
			[PROFILE]: () => json(200, profile),
			[slotsUrl('2026-11-02')]: () => json(200, { date: '2026-11-02', slots: ['09:00', '10:20', '11:00'] }),
			[slotsUrl('2026-11-02', 11, 22)]: () => json(200, { date: '2026-11-02', slots: ['16:40'] }),
			[slotsUrl('2026-11-03', 11, 22)]: () => json(200, { date: '2026-11-03', slots: ['14:20', '15:00'] }),
			'POST /api/public/practices/cabinet-lac/bookings': () =>
				json(201, { status: 'requested', startsAt: '2026-11-03T14:20:00+01:00', serviceName: 'Consultation', practitionerName: 'Dr. Karim Trabelsi', manageToken: 'mng-1' })
		});
		render(BookingPage, { props: { slug: 'cabinet-lac' } });
		await fireEvent.click(await screen.findByRole('radio', { name: /Consultation/ }));
		expect(screen.getByRole('radio', { name: /Consultation/ })).toHaveAccessibleName(/20 min/);
		expect(screen.getByRole('radio', { name: /Consultation/ })).toHaveAccessibleName(/50 DT/);
		// today (Monday) is chosen and its free times are shown
		expect(screen.getByRole('radio', { name: /lun\. 2/i })).toBeChecked();
		expect(await screen.findByRole('radio', { name: '10:20' })).toBeInTheDocument();
		// Sunday is closed
		expect(screen.getByRole('radio', { name: /dim\. 8/i })).toBeDisabled();
		// a practitioner, then another day
		await fireEvent.click(screen.getByRole('radio', { name: 'Dr. Karim Trabelsi' }));
		expect(await screen.findByRole('radio', { name: '16:40' })).toBeInTheDocument(); // the same day, for him
		await fireEvent.click(screen.getByRole('radio', { name: /mar\. 3/i }));
		await fireEvent.click(await screen.findByRole('radio', { name: '14:20' }));
		expect(screen.getByText('mar. 3 nov. · 14:20 · Consultation')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Continuer' }));

		expect(screen.getByRole('heading', { name: 'Vos coordonnées' })).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Réserver ce rendez-vous' }));
		expect(screen.getByLabelText('Prénom')).toHaveAccessibleDescription('Ce champ est obligatoire.');
		await fillDetails();
		await fireEvent.click(screen.getByRole('checkbox', { name: /rappel la veille/ }));
		await fireEvent.input(screen.getByLabelText(/^Message pour le cabinet/), { target: { value: 'Première visite' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Réserver ce rendez-vous' }));

		expect(await screen.findByRole('heading', { name: 'Demande envoyée' })).toBeInTheDocument();
		expect(sentJson('POST /api/public/practices/cabinet-lac/bookings')).toEqual({
			serviceId: 11,
			practitionerId: 22,
			startsAt: '2026-11-03T14:20:00+01:00',
			firstName: 'Mounia',
			lastName: 'Chebbi',
			phone: '20 123 456',
			lang: 'fr',
			reminderConsent: true,
			note: 'Première visite',
			website: ''
		});
		expect(screen.getByText('mardi 3 novembre 2026')).toBeInTheDocument();
		expect(screen.getByText('14:20')).toBeInTheDocument();
		// the token stays in the fragment (/rdv#…): it never reaches a server log
		expect(screen.getByRole('textbox', { name: 'Votre lien personnel' })).toHaveValue(`${location.origin}/rdv#mng-1`);
		expect(screen.getByRole('link', { name: 'Voir mon rendez-vous' })).toHaveAttribute('href', '/rdv#mng-1');
	});

	it('says when the booking is confirmed right away and leaves the practitioner to the practice', async () => {
		mockApi({
			[PROFILE]: () => json(200, profile),
			[slotsUrl('2026-11-02')]: () => json(200, { date: '2026-11-02', slots: ['10:20'] }),
			'POST /api/public/practices/cabinet-lac/bookings': () =>
				json(201, { status: 'confirmed', startsAt: '2026-11-02T10:20:00+01:00', serviceName: 'Consultation', practitionerName: null, manageToken: 'mng-2' })
		});
		render(BookingPage, { props: { slug: 'cabinet-lac' } });
		await chooseConsultationAt();
		await fillDetails();
		await fireEvent.click(screen.getByRole('button', { name: 'Réserver ce rendez-vous' }));
		expect(await screen.findByRole('heading', { name: 'Rendez-vous confirmé' })).toBeInTheDocument();
		const body = sentJson('POST /api/public/practices/cabinet-lac/bookings') as Record<string, unknown>;
		expect(body).not.toHaveProperty('practitionerId');
		expect(body.reminderConsent).toBe(false);
	});

	it('moves on to the next open day when today is full', async () => {
		mockApi({
			[PROFILE]: () => json(200, profile),
			[slotsUrl('2026-11-02')]: () => json(200, { date: '2026-11-02', slots: [] }),
			[slotsUrl('2026-11-03')]: () => json(200, { date: '2026-11-03', slots: ['08:40'] })
		});
		render(BookingPage, { props: { slug: 'cabinet-lac' } });
		await fireEvent.click(await screen.findByRole('radio', { name: /Consultation/ }));
		expect(await screen.findByRole('radio', { name: '08:40' })).toBeInTheDocument();
		expect(screen.getByRole('radio', { name: /mar\. 3/i })).toBeChecked();
	});

	it('explains a day without free times when the patient picked it', async () => {
		mockApi({
			[PROFILE]: () => json(200, profile),
			[slotsUrl('2026-11-02')]: () => json(200, { date: '2026-11-02', slots: ['09:00'] }),
			[slotsUrl('2026-11-04')]: () => json(200, { date: '2026-11-04', slots: [] }),
			[slotsUrl('2026-11-05')]: () => json(200, { date: '2026-11-05', slots: ['16:00'] })
		});
		render(BookingPage, { props: { slug: 'cabinet-lac' } });
		await fireEvent.click(await screen.findByRole('radio', { name: /Consultation/ }));
		await screen.findByRole('radio', { name: '09:00' });
		await fireEvent.click(screen.getByRole('radio', { name: /mer\. 4/i }));
		expect(await screen.findByText('Plus d’horaire libre ce jour-là.')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Voir le jour suivant' }));
		expect(await screen.findByRole('radio', { name: '16:00' })).toBeInTheDocument();
	});

	it('handles a time taken in the meantime (409): back to the times, details kept', async () => {
		let taken = false;
		mockApi({
			[PROFILE]: () => json(200, profile),
			[slotsUrl('2026-11-02')]: () => json(200, { date: '2026-11-02', slots: taken ? ['11:00'] : ['10:20', '11:00'] }),
			'POST /api/public/practices/cabinet-lac/bookings': () => {
				taken = true;
				return problem(409, 'slot_unavailable');
			}
		});
		render(BookingPage, { props: { slug: 'cabinet-lac' } });
		await chooseConsultationAt();
		await fillDetails();
		await fireEvent.click(screen.getByRole('button', { name: 'Réserver ce rendez-vous' }));
		expect(await screen.findByRole('alert')).toHaveTextContent('Ce créneau vient d’être pris. Choisissez un autre horaire.');
		await fireEvent.click(await screen.findByRole('radio', { name: '11:00' }));
		expect(screen.queryByRole('radio', { name: '10:20' })).not.toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Continuer' }));
		expect(screen.getByLabelText('Prénom')).toHaveValue('Mounia');
	});

	it('asks blocked patients (422) to call and explains limits (429)', async () => {
		let answer = problem(422, 'blocked');
		mockApi({
			[PROFILE]: () => json(200, profile),
			[slotsUrl('2026-11-02')]: () => json(200, { date: '2026-11-02', slots: ['10:20'] }),
			'POST /api/public/practices/cabinet-lac/bookings': () => answer
		});
		render(BookingPage, { props: { slug: 'cabinet-lac' } });
		await chooseConsultationAt();
		await fillDetails();
		await fireEvent.click(screen.getByRole('button', { name: 'Réserver ce rendez-vous' }));
		const alert = await screen.findByRole('alert');
		expect(alert).toHaveTextContent('Merci d’appeler le cabinet');
		expect(within(alert).getByRole('link', { name: 'Appeler' })).toHaveAttribute('href', 'tel:+21673123456');
		answer = problem(429, 'too_many_requests');
		await fireEvent.click(screen.getByRole('button', { name: 'Réserver ce rendez-vous' }));
		await vi.waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Réessayez dans une heure'));
	});

	it('shows an invalid phone at the field', async () => {
		mockApi({
			[PROFILE]: () => json(200, profile),
			[slotsUrl('2026-11-02')]: () => json(200, { date: '2026-11-02', slots: ['10:20'] })
		});
		render(BookingPage, { props: { slug: 'cabinet-lac' } });
		await chooseConsultationAt();
		await fillDetails();
		await fireEvent.input(screen.getByLabelText('Téléphone'), { target: { value: '123' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Réserver ce rendez-vous' }));
		expect(screen.getByLabelText('Téléphone')).toHaveAccessibleDescription(/Numéro invalide/);
		expect(calls().some((c) => c.startsWith('POST'))).toBe(false);
	});

	it('only shows contact details when online booking is off', async () => {
		mockApi({ [PROFILE]: () => json(200, { ...profile, onlineBookingEnabled: false }) });
		render(BookingPage, { props: { slug: 'cabinet-lac' } });
		expect(await screen.findByText(/ne prend pas de rendez-vous en ligne/)).toBeInTheDocument();
		expect(screen.queryByRole('radio', { name: /Consultation/ })).not.toBeInTheDocument();
	});

	it('says when the practice does not exist', async () => {
		mockApi({ 'GET /api/public/practices/inconnu': () => problem(404, 'not_found') });
		render(BookingPage, { props: { slug: 'inconnu' } });
		expect(await screen.findByRole('alert')).toHaveTextContent('Ce cabinet est introuvable.');
	});

	it('speaks Arabic: names, acts and the request language', async () => {
		i18n.setLocale('ar');
		mockApi({
			[PROFILE]: () => json(200, profile),
			[slotsUrl('2026-11-02')]: () => json(200, { date: '2026-11-02', slots: ['10:20'] }),
			'POST /api/public/practices/cabinet-lac/bookings': () =>
				json(201, { status: 'requested', startsAt: '2026-11-02T10:20:00+01:00', serviceName: 'معاينة', practitionerName: null, manageToken: 'm' })
		});
		render(BookingPage, { props: { slug: 'cabinet-lac' } });
		expect(await screen.findByRole('heading', { level: 1, name: 'عيادة الدكتورة بن صالح' })).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('radio', { name: /معاينة/ }));
		await fireEvent.click(await screen.findByRole('radio', { name: '10:20' }));
		await fireEvent.click(screen.getByRole('button', { name: 'متابعة' }));
		await fireEvent.input(screen.getByLabelText('الاسم'), { target: { value: 'منية' } });
		await fireEvent.input(screen.getByLabelText('اللقب'), { target: { value: 'الشابي' } });
		await fireEvent.input(screen.getByLabelText('الهاتف'), { target: { value: '20123456' } });
		await fireEvent.click(screen.getByRole('button', { name: 'احجز هذا الموعد' }));
		expect(await screen.findByRole('heading', { name: 'تمّ إرسال الطلب' })).toBeInTheDocument();
		expect((sentJson('POST /api/public/practices/cabinet-lac/bookings') as { lang: string }).lang).toBe('ar');
	});
});

describe('/ – the booking page of a practice sub-domain', () => {
	beforeEach(() => {
		i18n.setLocale('fr');
		document.head.innerHTML = '<link rel="manifest" href="/manifest.webmanifest">';
	});
	afterEach(() => {
		hostDeps.hostname = () => location.hostname;
	});

	it('takes the practice from the host name and installs as the booking app', async () => {
		hostDeps.hostname = () => 'cabinet-lac.daftar.omarfourati.de';
		mockApi({ [PROFILE]: () => json(200, profile) });
		render(Root);
		expect(await screen.findByRole('heading', { level: 1, name: 'Cabinet Dr Ben Salah' })).toBeInTheDocument();
		expect(document.querySelector('link[rel=manifest]')?.getAttribute('href')).toBe('/booking.webmanifest');
	});

	it('leaves the main domain to the landing page', () => {
		hostDeps.hostname = () => 'daftar.omarfourati.de';
		const replace = vi.fn();
		bookingDeps.replace = replace;
		mockApi({});
		render(Root);
		expect(replace).toHaveBeenCalledWith('/');
		expect(calls()).toEqual([]);
	});
});
