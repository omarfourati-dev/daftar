import { render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it } from 'vitest';
import StockStats from './StockStats.svelte';
import { auth } from '../../auth.svelte';
import { i18n } from '../../i18n.svelte';
import { json, mockApi } from '../../test-utils';
import { owner } from '../../agenda/fixtures';
import type { StockStats as Stats } from '../../types/stock';

const withoutPrices: Stats = {
	month: '2026-10',
	spendingMillimes: 0,
	previousSpendingMillimes: 0,
	unpricedLines: 2,
	unpricedUses: 3,
	bySupplier: [],
	byCategory: [],
	usageMillimes: 0,
	wasteMillimes: 0,
	byService: [
		{ serviceId: 11, name: 'Soin carie', nameAr: 'علاج تسوس', treatments: 3, materialCostMillimes: 0, perTreatmentMillimes: 0,
			items: [{ productId: 1, name: 'Seringues 5 ml', unit: 'piece', quantity: 3, costMillimes: 0 }] }
	],
	topMaterials: []
};

describe('StockStats – the material of the month', () => {
	beforeEach(() => {
		auth.set('tok', owner);
		i18n.setLocale('fr');
	});

	it('shows the quantities per act even without any price (review N5), as cards and as a table', async () => {
		mockApi({ 'GET /api/stock/stats?month=2026-10': () => json(200, withoutPrices) });
		render(StockStats, { props: { month: '2026-10', previousName: 'septembre' } });
		const cards = within(await screen.findByRole('list', { name: 'Coût du matériel par acte' }));
		expect(cards.getByText('Soin carie')).toBeInTheDocument();
		expect(cards.getByText('3 pièces Seringues 5 ml (prix manquant)')).toBeInTheDocument();
		const table = within(screen.getByRole('table', { name: 'Coût du matériel par acte' }));
		expect(table.getByRole('row', { name: /Soin carie/ })).toHaveTextContent('3');
		expect(screen.getByText('3 sortie(s) sans prix connu comptent pour 0 : notez le prix à la réception.')).toBeInTheDocument();
		expect(screen.queryByText('Aucun achat ni sortie ce mois-ci.')).not.toBeInTheDocument();
	});

	it('names the act in Arabic (review N6)', async () => {
		i18n.setLocale('ar');
		mockApi({ 'GET /api/stock/stats?month=2026-10': () => json(200, withoutPrices) });
		render(StockStats, { props: { month: '2026-10', previousName: 'سبتمبر' } });
		const table = within(await screen.findByRole('table'));
		expect(table.getByText('علاج تسوس')).toBeInTheDocument();
		expect(table.queryByText('Soin carie')).not.toBeInTheDocument();
	});

	it('says plainly when there is nothing at all', async () => {
		mockApi({ 'GET /api/stock/stats?month=2026-10': () => json(200, { ...withoutPrices, unpricedLines: 0, unpricedUses: 0, byService: [] }) });
		render(StockStats, { props: { month: '2026-10', previousName: 'septembre' } });
		expect(await screen.findByText('Aucun achat ni sortie ce mois-ci.')).toBeInTheDocument();
	});
});
