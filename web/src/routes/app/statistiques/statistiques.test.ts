import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { clock } from '#lib/clock';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, mockApi, problem } from '#lib/test-utils';
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

describe('/app/statistiques – the month for the owner', () => {
	beforeEach(() => {
		auth.set('tok', owner);
		i18n.setLocale('fr');
		clock.now = () => new Date(NOW);
	});

	it('shows the key numbers with the comparison to last month', async () => {
		mockApi({ 'GET /api/stats?month=2026-10': () => json(200, october) });
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

	it('goes back one month', async () => {
		mockApi({
			'GET /api/stats?month=2026-10': () => json(200, october),
			'GET /api/stats?month=2026-09': () => json(200, { ...october.previous, previous: { ...october.previous, month: '2026-08' } })
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
