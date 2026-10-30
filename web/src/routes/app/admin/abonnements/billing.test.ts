import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { i18n } from '#lib/i18n.svelte';
import { json, mockApi, sentJson } from '#lib/test-utils';
import type { AdminBillingRow, Invoice } from '#lib/types/billing';

const open: Invoice = {
	id: 31,
	number: 'DAF-2026-0007',
	planCode: 'cabinet_mensuel',
	periodStart: '2026-11-01',
	periodEnd: '2026-11-30',
	amountMillimes: 49000,
	status: 'open',
	dueOn: '2026-11-01',
	paidAt: null,
	method: null
};
const paid: Invoice = { ...open, id: 30, number: 'DAF-2026-0003', periodStart: '2026-10-01', periodEnd: '2026-10-31', status: 'paid', paidAt: '2026-10-02T10:00:00+01:00', method: 'virement' };
const lac: AdminBillingRow = {
	id: 7,
	name: 'Cabinet du Lac',
	slug: 'cabinet-lac',
	planCode: 'cabinet_mensuel',
	status: 'past_due',
	paidUntil: '2026-10-31',
	openMillimes: 49000,
	invoices: [open, paid]
};

describe('/app/admin/abonnements', () => {
	beforeEach(() => i18n.setLocale('fr'));

	it('lists practices with plan, status, paid-until, open amount and invoices', async () => {
		mockApi({ 'GET /api/admin/billing': () => json(200, [lac]) });
		render(Page);
		const card = (await screen.findByRole('heading', { name: 'Cabinet du Lac' })).closest('article')!;
		expect(within(card).getByText('Paiement en retard')).toBeInTheDocument();
		expect(within(card).getByText('Cabinet – mensuel')).toBeInTheDocument();
		expect(within(card).getByText('31/10/2026')).toBeInTheDocument();
		expect(within(card).getAllByText('49 DT').length).toBeGreaterThan(0);
		const rowOpen = within(card).getByText('DAF-2026-0007').closest('li')!;
		expect(within(rowOpen).getByText('À payer')).toBeInTheDocument();
		const rowPaid = within(card).getByText('DAF-2026-0003').closest('li')!;
		expect(within(rowPaid).getByText('Payée le 02/10/2026 (Virement)')).toBeInTheDocument();
		expect(within(card).getByRole('link', { name: 'Statut et formule' })).toHaveAttribute('href', '/app/admin/cabinets/7');
	});

	it('records a bank transfer for an open invoice', async () => {
		let rows = [lac];
		mockApi({
			'GET /api/admin/billing': () => json(200, rows),
			'POST /api/admin/invoices/31/mark-paid': () => {
				rows = [{ ...lac, status: 'active', paidUntil: '2026-11-30', openMillimes: 0, invoices: [{ ...open, status: 'paid', paidAt: '2026-10-30T10:00:00+01:00', method: 'virement' }, paid] }];
				return json(200, rows[0].invoices[0]);
			}
		});
		render(Page);
		await fireEvent.click(await screen.findByRole('button', { name: 'Marquer payée DAF-2026-0007' }));
		const dialog = screen.getByRole('dialog', { name: 'Facture DAF-2026-0007 payée ?' });
		await fireEvent.change(within(dialog).getByLabelText('Moyen de paiement'), { target: { value: 'virement' } });
		await fireEvent.click(within(dialog).getByRole('button', { name: 'Enregistrer le paiement' }));
		await vi.waitFor(() => expect(sentJson('POST /api/admin/invoices/31/mark-paid')).toEqual({ method: 'virement' }));
		expect(await screen.findByText('Paiement enregistré.')).toBeInTheDocument();
		expect(await screen.findByText('Actif')).toBeInTheDocument();
	});

	it('voids an invoice and creates the next one', async () => {
		mockApi({
			'GET /api/admin/billing': () => json(200, [lac]),
			'POST /api/admin/invoices/31/void': () => json(200, { ...open, status: 'void' }),
			'POST /api/admin/practices/7/invoices': () => json(201, { ...open, id: 32, number: 'DAF-2026-0008' })
		});
		render(Page);
		await fireEvent.click(await screen.findByRole('button', { name: 'Annuler la facture DAF-2026-0007' }));
		await fireEvent.click(within(screen.getByRole('dialog', { name: 'Annuler la facture DAF-2026-0007 ?' })).getByRole('button', { name: 'Annuler la facture' }));
		expect(await screen.findByText('Facture annulée.')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Créer la facture suivante – Cabinet du Lac' }));
		expect(await screen.findByText('Facture DAF-2026-0008 créée.')).toBeInTheDocument();
	});

	it('has an empty state', async () => {
		mockApi({ 'GET /api/admin/billing': () => json(200, []) });
		render(Page);
		expect(await screen.findByText('Aucun cabinet avec abonnement pour l’instant.')).toBeInTheDocument();
	});
});
