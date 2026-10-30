import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { i18n } from '#lib/i18n.svelte';
import { navigation } from '#lib/navigate';
import { calls, json, mockApi } from '#lib/test-utils';
import { assistant, owner } from '#lib/testing/fixtures';
import type { Billing, Invoice } from '#lib/types/billing';

const monthly = { code: 'cabinet_mensuel', nameFr: 'Cabinet – mensuel', nameAr: 'عيادة – شهري', priceMillimes: 49000, periodMonths: 1, active: true };
const yearly = { code: 'cabinet_annuel', nameFr: 'Cabinet – annuel', nameAr: 'عيادة – سنوي', priceMillimes: 490000, periodMonths: 12, active: true };
const open: Invoice = { id: 31, number: 'DAF-2026-0007', planCode: 'cabinet_mensuel', periodStart: '2026-11-01', periodEnd: '2026-11-30', amountMillimes: 49000, status: 'open', dueOn: '2026-11-01', paidAt: null, method: null };
const paid: Invoice = { ...open, id: 30, number: 'DAF-2026-0003', periodStart: '2026-10-01', periodEnd: '2026-10-31', status: 'paid', paidAt: '2026-10-02T10:00:00+01:00', method: 'virement' };
const billing: Billing = { plan: monthly, status: 'past_due', paidUntil: '2026-10-31', plans: [monthly, yearly], invoices: [open, paid], onlinePaymentAvailable: true };

describe('/app/abonnement (I1)', () => {
	beforeEach(() => {
		i18n.setLocale('fr');
		auth.set('tok', owner);
		history.replaceState(null, '', '/app/abonnement');
	});

	it('shows plan, status, paid-until and invoices, and pays an open invoice with Flouci', async () => {
		const assign = vi.fn();
		navigation.assign = assign;
		mockApi({
			'GET /api/billing': () => json(200, billing),
			'POST /api/billing/invoices/31/pay': () => json(200, { paymentUrl: 'https://www.flouci.com/pay/abc' })
		});
		render(Page);
		const plan = within(await screen.findByRole('region', { name: 'Formule' }));
		expect(plan.getByText('Cabinet – mensuel')).toBeInTheDocument();
		expect(plan.getByText('49 DT par mois')).toBeInTheDocument();
		expect(screen.getByText('Paiement en retard')).toBeInTheDocument();
		expect(screen.getByText('31/10/2026')).toBeInTheDocument();
		const openRow = screen.getByText('DAF-2026-0007').closest('li')!;
		expect(within(openRow).getByText('À payer')).toBeInTheDocument();
		expect(within(screen.getByText('DAF-2026-0003').closest('li')!).getByText('Payée le 02/10/2026')).toBeInTheDocument();
		await fireEvent.click(within(openRow).getByRole('button', { name: 'Payer la facture DAF-2026-0007 avec Flouci' }));
		await vi.waitFor(() => expect(assign).toHaveBeenCalledWith('https://www.flouci.com/pay/abc'));
	});

	it('explains the bank transfer when online payment is off', async () => {
		mockApi({ 'GET /api/billing': () => json(200, { ...billing, onlinePaymentAvailable: false }) });
		render(Page);
		expect(await screen.findByText(/Règlement par virement/)).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: /avec Flouci/ })).not.toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Écrire à Daftar' }).getAttribute('href')).toMatch(/^mailto:info@omarfourati\.de\?subject=/);
	});

	it('checks the payment when coming back from Flouci', async () => {
		history.replaceState(null, '', '/app/abonnement?invoice=31&payment=success&payment_id=xyz');
		let verified = false;
		mockApi({
			'POST /api/billing/invoices/31/verify': () => {
				verified = true;
				return json(200, { ...open, status: 'paid', paidAt: '2026-10-30T10:00:00+01:00', method: 'flouci' });
			},
			'GET /api/billing': () => json(200, verified ? { ...billing, status: 'active', paidUntil: '2026-11-30', invoices: [{ ...open, status: 'paid' }, paid] } : billing)
		});
		render(Page);
		expect(await screen.findByText('Paiement reçu, merci ! Votre abonnement est à jour.')).toBeInTheDocument();
		expect(location.search).toBe('');
		expect(await screen.findByText('Actif')).toBeInTheDocument();
	});

	it('shows the pilot phase', async () => {
		mockApi({ 'GET /api/billing': () => json(200, { ...billing, plan: 'pilot', status: 'pilot', paidUntil: '2026-12-31', invoices: [], plans: [monthly] }) });
		render(Page);
		expect(await screen.findByText('Phase pilote : Daftar est gratuit pour votre cabinet jusqu’au 31/12/2026.')).toBeInTheDocument();
		expect(screen.getByText('Aucune facture pour l’instant.')).toBeInTheDocument();
	});

	it('is for the owner only', () => {
		auth.set('tok', assistant);
		mockApi({});
		render(Page);
		expect(screen.getByText('Cette page est réservée au titulaire du cabinet.')).toBeInTheDocument();
		expect(calls()).toEqual([]);
	});
});
