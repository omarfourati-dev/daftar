import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ProductDialog from './ProductDialog.svelte';
import { auth } from '../../auth.svelte';
import { i18n } from '../../i18n.svelte';
import { mockApi, problem } from '../../test-utils';
import { assistant } from '../../agenda/fixtures';
import type { Product } from '../../types/stock';

const needles: Product = {
	id: 4, name: 'Aiguilles', category: 'anesthesie', unit: 'boite', supplierId: null, supplierName: null, minQuantity: 1, note: '', ean: null,
	active: true, quantity: 2, status: 'ok', hasHistory: true, expiresOn: null, expiry: null, averageCostMillimes: 35000, lastUsedAt: null
};

describe('ProductDialog – the unit of a product with history is locked (review M2)', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
	});

	it('greys the unit out, says why and offers a new product', async () => {
		mockApi({});
		const onnew = vi.fn();
		render(ProductDialog, { props: { product: needles, suppliers: [], onsaved: vi.fn(), onnew, onclose: vi.fn() } });
		const dialog = within(screen.getByRole('dialog', { name: 'Modifier le produit' }));
		const unit = dialog.getByLabelText('Unité');
		expect(unit).toBeDisabled();
		expect(unit).toHaveAccessibleDescription(/son unité ne change plus/);
		await fireEvent.click(dialog.getByRole('button', { name: 'Créer un nouveau produit' }));
		expect(onnew).toHaveBeenCalledWith('Aiguilles');
	});

	it('leaves the unit free while nothing was recorded, and explains the server’s refusal', async () => {
		mockApi({ 'PATCH /api/stock/products/4': () => problem(409, 'unit_in_use') });
		render(ProductDialog, { props: { product: { ...needles, hasHistory: false }, suppliers: [], onsaved: vi.fn(), onclose: vi.fn() } });
		const dialog = within(screen.getByRole('dialog', { name: 'Modifier le produit' }));
		expect(dialog.getByLabelText('Unité')).toBeEnabled();
		await fireEvent.change(dialog.getByLabelText('Unité'), { target: { value: 'piece' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer le produit' }));
		expect(await dialog.findByRole('alert')).toHaveTextContent('Ce produit a déjà des mouvements : son unité ne change plus.');
	});
});
