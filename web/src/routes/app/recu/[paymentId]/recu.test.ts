import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { i18n } from '#lib/i18n.svelte';
import { json, mockApi, problem } from '#lib/test-utils';
import { assistant } from '#lib/agenda/fixtures';

const receipt = {
	id: 72,
	patientId: 7,
	patientName: 'Sami Trabelsi',
	amountMillimes: 150500,
	method: 'cash',
	paidAt: '2026-10-24T11:20:00+01:00',
	appointmentId: 80,
	isDeposit: true,
	note: 'Deuxième versement',
	receivedByName: 'Salma',
	practice: { name: 'Cabinet du Lac', nameAr: 'عيادة البحيرة', address: '12 rue du Lac', city: 'Tunis', phone: '+21671000000', taxId: '1234567/A/M/000' }
};

describe('/app/recu/[paymentId] – printable receipt', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
	});

	it('shows the practice, the patient, the amount, the method and who received it', async () => {
		mockApi({ 'GET /api/payments/72': () => json(200, receipt) });
		render(Page, { props: { data: { paymentId: 72 } } });
		expect(await screen.findByRole('heading', { level: 1, name: 'Reçu n° 72' })).toBeInTheDocument();
		expect(screen.getByText('Cabinet du Lac')).toBeInTheDocument();
		expect(screen.getByText('12 rue du Lac, Tunis')).toBeInTheDocument();
		expect(screen.getByText('+216 71 000 000')).toBeInTheDocument();
		expect(screen.getByText(/1234567\/A\/M\/000/)).toBeInTheDocument();
		expect(screen.getByText('Patient').nextElementSibling).toHaveTextContent('Sami Trabelsi');
		expect(screen.getByText('Montant reçu').nextElementSibling).toHaveTextContent('150,500 DT');
		expect(screen.getByText('Mode de paiement').nextElementSibling).toHaveTextContent('Espèces');
		expect(screen.getByText('Date').nextElementSibling).toHaveTextContent('24/10/2026');
		expect(screen.getByText('Reçu par').nextElementSibling).toHaveTextContent('Salma');
		expect(screen.getByText('Acompte')).toBeInTheDocument();
		expect(screen.getByText('Deuxième versement')).toBeInTheDocument();
	});

	it('prints and goes back to the patient file', async () => {
		mockApi({ 'GET /api/payments/72': () => json(200, receipt) });
		const print = vi.spyOn(window, 'print').mockImplementation(() => undefined);
		render(Page, { props: { data: { paymentId: 72 } } });
		await fireEvent.click(await screen.findByRole('button', { name: 'Imprimer' }));
		expect(print).toHaveBeenCalled();
		expect(screen.getByRole('link', { name: 'Retour au dossier' })).toHaveAttribute('href', '/app/patients/7');
	});

	it('explains a deleted payment', async () => {
		mockApi({ 'GET /api/payments/72': () => problem(404, 'not_found') });
		render(Page, { props: { data: { paymentId: 72 } } });
		expect(await screen.findByRole('alert')).toHaveTextContent('Ce paiement n’existe pas ou a été supprimé.');
	});

	it('is printed in Arabic with the Arabic practice name', async () => {
		i18n.setLocale('ar');
		mockApi({ 'GET /api/payments/72': () => json(200, receipt) });
		render(Page, { props: { data: { paymentId: 72 } } });
		expect(await screen.findByRole('heading', { level: 1, name: 'وصل رقم 72' })).toBeInTheDocument();
		expect(screen.getByText('عيادة البحيرة')).toBeInTheDocument();
	});
});
