import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { hostDeps } from '#lib/host';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, mockApi, problem } from '#lib/test-utils';
import type { ManagedBooking } from '#lib/types/booking';

const booking: ManagedBooking = {
	status: 'requested',
	startsAt: '2026-11-03T14:20:00+01:00',
	endsAt: '2026-11-03T14:40:00+01:00',
	canCancel: true,
	cancelUntil: '2026-11-03T12:20:00+01:00',
	serviceName: 'Consultation',
	practitionerName: 'Dr. Karim Trabelsi',
	practice: {
		slug: 'cabinet-lac',
		name: 'Cabinet Dr Ben Salah',
		nameAr: 'عيادة الدكتورة بن صالح',
		phone: '+21673123456',
		whatsapp: '+21620123456',
		address: '14 avenue Habib Bourguiba',
		city: 'Sousse',
		mapsUrl: 'https://maps.app.goo.gl/abc'
	}
};
const page = () => render(Page, { props: { data: { token: 'mng-1' } } });

describe('/rdv/[token] – the patient’s own link', () => {
	beforeEach(() => {
		i18n.setLocale('fr');
		vi.useFakeTimers({ toFake: ['Date'] });
		vi.setSystemTime(new Date('2026-11-02T08:00:00+01:00'));
		hostDeps.hostname = () => 'localhost';
	});
	afterEach(() => {
		vi.useRealTimers();
		hostDeps.hostname = () => location.hostname;
	});

	it('shows the appointment, its status and how to reach the practice', async () => {
		mockApi({ 'GET /api/public/bookings/mng-1': () => json(200, booking) });
		page();
		expect(screen.getByRole('heading', { level: 1, name: 'Votre rendez-vous' })).toBeInTheDocument();
		expect(await screen.findByText('En attente de confirmation')).toBeInTheDocument();
		expect(screen.getByText('mardi 3 novembre 2026')).toBeInTheDocument();
		expect(screen.getByText('14:20')).toBeInTheDocument();
		expect(screen.getByText((_, el) => el?.tagName === 'P' && el.textContent === 'Consultation · Dr. Karim Trabelsi')).toBeInTheDocument();
		expect(screen.getByText('Cabinet Dr Ben Salah')).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Appeler' })).toHaveAttribute('href', 'tel:+21673123456');
		expect(screen.getByText('Annulation en ligne possible jusqu’au 03/11/2026 12:20.')).toBeInTheDocument();
	});

	it('cancels after confirmation', async () => {
		mockApi({
			'GET /api/public/bookings/mng-1': () => json(200, booking),
			'POST /api/public/bookings/mng-1/cancel': () => json(200, { ...booking, status: 'cancelled', canCancel: false })
		});
		page();
		await fireEvent.click(await screen.findByRole('button', { name: 'Annuler ce rendez-vous' }));
		await fireEvent.click(within(screen.getByRole('dialog', { name: 'Annuler ce rendez-vous ?' })).getByRole('button', { name: 'Oui, annuler' }));
		expect(await screen.findByText('Votre rendez-vous est annulé.')).toBeInTheDocument();
		expect(screen.getByText('Annulé')).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Annuler ce rendez-vous' })).not.toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Prendre un nouveau rendez-vous' })).toHaveAttribute('href', '/r/cabinet-lac');
	});

	it('asks to call when it is too late to cancel online', async () => {
		mockApi({
			'GET /api/public/bookings/mng-1': () => json(200, booking),
			'POST /api/public/bookings/mng-1/cancel': () => problem(409, 'too_late')
		});
		page();
		await fireEvent.click(await screen.findByRole('button', { name: 'Annuler ce rendez-vous' }));
		await fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Oui, annuler' }));
		expect(await within(screen.getByRole('dialog')).findByRole('alert')).toHaveTextContent('Il est trop tard pour annuler en ligne.');
	});

	it('asks to call once the online cancellation deadline has passed', async () => {
		mockApi({ 'GET /api/public/bookings/mng-1': () => json(200, { ...booking, canCancel: false, cancelUntil: '2026-11-02T07:00:00+01:00' }) });
		page();
		expect(await screen.findByText('Il est trop tard pour annuler en ligne. Merci d’appeler le cabinet.')).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Annuler ce rendez-vous' })).not.toBeInTheDocument();
	});

	it('does not offer to cancel past or cancelled appointments', async () => {
		mockApi({ 'GET /api/public/bookings/mng-1': () => json(200, { ...booking, startsAt: '2026-10-30T10:00:00+01:00', status: 'done', canCancel: false }) });
		page();
		expect(await screen.findByText('Ce rendez-vous est passé.')).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Annuler ce rendez-vous' })).not.toBeInTheDocument();
	});

	it('explains an unknown link', async () => {
		mockApi({ 'GET /api/public/bookings/mng-1': () => problem(404, 'not_found') });
		page();
		expect(await screen.findByRole('alert')).toHaveTextContent('Ce lien n’est pas valide.');
		expect(calls()).toEqual(['GET /api/public/bookings/mng-1']);
	});

	it('links back to the sub-domain booking page there', async () => {
		hostDeps.hostname = () => 'cabinet-lac.daftar.omarfourati.de';
		mockApi({ 'GET /api/public/bookings/mng-1': () => json(200, { ...booking, status: 'cancelled' }) });
		page();
		expect(await screen.findByRole('link', { name: 'Prendre un nouveau rendez-vous' })).toHaveAttribute('href', '/');
	});
});
