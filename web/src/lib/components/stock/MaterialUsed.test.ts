import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import MaterialUsed from './MaterialUsed.svelte';
import { auth } from '../../auth.svelte';
import { i18n } from '../../i18n.svelte';
import { calls, json, mockApi, sentJson } from '../../test-utils';
import { dentist } from '../../testing/fixtures';
import type { Movement, Product } from '../../types/stock';

const carpules: Product = {
	id: 2, name: 'Carpules d’articaïne', category: 'anesthesie', unit: 'carpule', supplierId: null, supplierName: null, minQuantity: 50,
	note: '', ean: null, active: true, quantity: 40, status: 'low', expiresOn: null, expiry: null, averageCostMillimes: null,
	lastUsedAt: '2026-10-30T08:00:00+01:00'
};
const composite: Product = { ...carpules, id: 3, name: 'Composite', unit: 'piece', lastUsedAt: null };
const earlier: Movement = {
	id: 70, productId: 3, productName: 'Composite', unit: 'piece', kind: 'use', quantity: -1, serviceId: 11, serviceName: 'Soin',
	appointmentId: 30, patientName: 'Lina Zouari', receiptId: null, reason: '', unitCostMillimes: null, createdBy: 'Karim', createdAt: '2026-10-30T09:00:00+01:00'
};

describe('MaterialUsed – optional material of an appointment (spec stock-hygiène 4.2)', () => {
	beforeEach(() => {
		auth.set('tok', dentist);
		i18n.setLocale('fr');
	});

	it('stays folded and asks nothing from the server until opened', async () => {
		mockApi({});
		render(MaterialUsed, { props: { appointmentId: 30 } });
		const toggle = screen.getByRole('button', { name: 'Noter le matériel utilisé' });
		expect(toggle).toHaveAttribute('aria-expanded', 'false');
		expect(calls()).toEqual([]);
	});

	it('lists what was used and adds a product for this appointment', async () => {
		mockApi({
			'GET /api/stock/movements?appointmentId=30': () => json(200, [earlier]),
			'GET /api/stock/products': () => json(200, [composite, carpules]),
			'POST /api/stock/movements': () =>
				json(201, { movement: { ...earlier, id: 71, productId: 2, productName: 'Carpules d’articaïne', unit: 'carpule', quantity: -2 }, product: { ...carpules, quantity: 38 } })
		});
		render(MaterialUsed, { props: { appointmentId: 30 } });
		await fireEvent.click(screen.getByRole('button', { name: 'Noter le matériel utilisé' }));
		const region = within(await screen.findByRole('region', { name: 'Matériel utilisé' }));
		expect(await region.findByRole('listitem')).toHaveTextContent('1 pièce Composite');
		expect(region.getByLabelText('Produit')).toHaveValue('2'); // the last used product first
		await fireEvent.input(region.getByLabelText('Quantité'), { target: { value: '2' } });
		await fireEvent.click(region.getByRole('button', { name: 'Ajouter' }));
		await vi.waitFor(() => expect(sentJson('POST /api/stock/movements')).toEqual({ productId: 2, kind: 'use', quantity: 2, appointmentId: 30 }));
		expect(await region.findByText('Noté : 2 carpules de Carpules d’articaïne.')).toBeInTheDocument();
		expect(region.getAllByRole('listitem').map((li) => li.textContent?.replace(/\s+/g, ' ').trim())).toEqual([
			'2 carpules Carpules d’articaïne',
			'1 pièce Composite'
		]);
	});
});
