import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { clock } from '#lib/clock';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, mockApi, problem } from '#lib/test-utils';
import * as download from '#lib/download';
import { assistant, NOW, owner } from '#lib/agenda/fixtures';

const october = {
	month: '2026-10',
	appointments: { total: 240, done: 200, noShow: 12, cancelled: 28, online: 36 },
	noShowRate: 0.0566,
	revenueMillimes: 9450000,
	newPatients: 31,
	topServices: [
		{ name: 'Consultation', count: 120 },
		{ name: 'Contrôle', count: 60 },
		{ name: 'Vaccination', count: 20 }
	],
	previous: {
		month: '2026-09',
		appointments: { total: 200, done: 160, noShow: 20, cancelled: 20, online: 10 },
		noShowRate: 0.1111,
		revenueMillimes: 8000000,
		newPatients: 31,
		topServices: []
	}
};

const material = {
	month: '2026-10',
	spendingMillimes: 210000,
	previousSpendingMillimes: 50000,
	unpricedLines: 1,
	bySupplier: [{ name: 'Dentalia Sfax', amountMillimes: 210000 }],
	byCategory: [
		{ category: 'hygiene', amountMillimes: 120000 },
		{ category: 'restauration', amountMillimes: 90000 }
	],
	usageMillimes: 66000,
	wasteMillimes: 12000,
	byService: [
		{ serviceId: 11, name: 'Soin carie / composite', treatments: 2, materialCostMillimes: 54000, perTreatmentMillimes: 27000, items: [{ productId: 3, name: 'Composite', unit: 'piece', quantity: 1, costMillimes: 30000 }] },
		{ serviceId: null, name: null, treatments: 0, materialCostMillimes: 12000, perTreatmentMillimes: null, items: [] }
	],
	topMaterials: [{ productId: 1, name: 'Gants d’examen', unit: 'boite', quantity: 3, costMillimes: 36000 }]
};

describe('/app/statistiques – the month for the owner', () => {
	beforeEach(() => {
		auth.set('tok', owner);
		i18n.setLocale('fr');
		// the month shown and the CSV name come from "now": never from the day the suite runs (CI ran on 01.11.)
		vi.useFakeTimers({ toFake: ['Date'] });
		vi.setSystemTime(new Date(NOW));
		clock.now = () => new Date(NOW);
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('shows the key numbers with the comparison to last month', async () => {
		mockApi({ 'GET /api/stats?month=2026-10': () => json(200, october), 'GET /api/stock/stats?month=2026-10': () => json(200, material) });
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'Statistiques' })).toBeInTheDocument();
		expect(await screen.findByText('octobre 2026')).toBeInTheDocument();
		const kpis = within(await screen.findByRole('list', { name: 'Statistiques' }));
		const tile = (label: string) => kpis.getByText(label).closest('li') as HTMLElement;
		expect(tile('Rendez-vous')).toHaveTextContent('240');
		expect(tile('Rendez-vous')).toHaveTextContent('+40 par rapport à septembre');
		expect(tile('Taux d’absence')).toHaveTextContent('5,7 %');
		expect(tile('Taux d’absence')).toHaveTextContent('12 absences');
		expect(tile('Taux d’absence')).toHaveTextContent('−5,4 pt par rapport à septembre');
		expect(tile('Réservés en ligne')).toHaveTextContent('36');
		expect(tile('Réservés en ligne')).toHaveTextContent('15 % des rendez-vous');
		expect(tile('Encaissé')).toHaveTextContent('9 450 DT');
		expect(tile('Encaissé')).toHaveTextContent('+1 450 DT par rapport à septembre');
		expect(tile('Nouveaux patients')).toHaveTextContent('comme le mois précédent');
		const top = within(screen.getByRole('region', { name: 'Actes les plus fréquents' }));
		expect(top.getAllByRole('listitem').map((li) => li.textContent)).toEqual([
			expect.stringContaining('Consultation'),
			expect.stringContaining('Contrôle'),
			expect.stringContaining('Vaccination')
		]);
		expect(screen.getByRole('img', { name: 'Ce mois et le mois précédent' })).toBeInTheDocument();
	});

	it('shows the material of the month: spending, cost per act, and the CSV (spec stock-hygiène 4.3)', async () => {
		const save = vi.spyOn(download, 'saveBlob').mockImplementation(() => undefined);
		mockApi({
			'GET /api/stats?month=2026-10': () => json(200, october),
			'GET /api/stock/stats?month=2026-10': () => json(200, material),
			'GET /api/stock/export.csv?month=2026-10': () => new Response('Date;Type', { status: 200, headers: { 'Content-Type': 'text/csv' } })
		});
		render(Page);
		const region = within(await screen.findByRole('region', { name: 'Matériel du mois' }));
		const spending = (await region.findByText('Achats')).closest('li') as HTMLElement;
		expect(spending).toHaveTextContent('210 DT');
		expect(spending).toHaveTextContent('+160 DT par rapport à septembre');
		const table = within(region.getByRole('table', { name: 'Coût du matériel par acte' }));
		const soin = table.getByRole('row', { name: /Soin carie/ });
		expect(soin).toHaveTextContent('2');
		expect(soin).toHaveTextContent('54 DT');
		expect(soin).toHaveTextContent('27 DT');
		expect(table.getByRole('row', { name: /Sans acte précisé/ })).toHaveTextContent('12 DT');
		expect(region.getByText('1 ligne(s) reçue(s) sans prix ne sont pas comptées.')).toBeInTheDocument();
		await fireEvent.click(region.getByRole('button', { name: 'Exporter le mois (CSV)' }));
		await vi.waitFor(() => expect(save).toHaveBeenCalled());
		const [blob, filename] = save.mock.calls[0];
		expect(filename).toBe('stock-2026-10.csv');
		expect(await blob.text()).toBe('Date;Type'); // a Blob of undici or jsdom alike (no instanceof across realms)
		save.mockRestore();
	});

	it('goes back one month', async () => {
		mockApi({
			'GET /api/stats?month=2026-10': () => json(200, october),
			'GET /api/stats?month=2026-09': () => json(200, { ...october.previous, previous: { ...october.previous, month: '2026-08' } }),
			'GET /api/stock/stats?month=2026-10': () => json(200, material),
			'GET /api/stock/stats?month=2026-09': () => json(200, { ...material, month: '2026-09' })
		});
		render(Page);
		await screen.findByText('octobre 2026');
		await fireEvent.click(screen.getByRole('button', { name: 'Mois précédent' }));
		expect(await screen.findByText('septembre 2026')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Mois suivant' })).toBeEnabled();
	});

	it('is only for the owner', () => {
		auth.set('tok', assistant);
		mockApi({});
		render(Page);
		expect(screen.getByText('Les statistiques sont réservées au titulaire du cabinet.')).toBeInTheDocument();
		expect(calls()).toEqual([]);
	});

	it('explains a loading problem and works in Arabic', async () => {
		i18n.setLocale('ar');
		mockApi({ 'GET /api/stats?month=2026-10': () => problem(500, 'server_error') });
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'الإحصائيات' })).toBeInTheDocument();
		expect(await screen.findByRole('alert')).toHaveTextContent('تعذّر تحميل الإحصائيات.');
	});
});
