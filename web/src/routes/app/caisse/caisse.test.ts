import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { clock } from '#lib/clock';
import { i18n } from '#lib/i18n.svelte';
import { json, mockApi, problem, sentJson, type Handler } from '#lib/test-utils';
import { assistant, NOW, owner } from '#lib/agenda/fixtures';
import type { CashDay } from '#lib/types/patients';

const pay = (id: number, amountMillimes: number, method: string, time: string, extra = {}) => ({
	id,
	patientId: 7,
	patientName: 'Sami Trabelsi',
	amountMillimes,
	method,
	paidAt: `2026-10-30T${time}:00+01:00`,
	appointmentId: null,
	isDeposit: false,
	note: '',
	receivedByName: 'Salma',
	...extra
});
const day: CashDay = {
	day: '2026-10-30',
	totalMillimes: 265000,
	byMethod: { cash: 185000, d17: 80000 },
	payments: [pay(70, 150000, 'cash', '09:40'), pay(71, 80000, 'd17', '10:05'), pay(72, 35000, 'cash', '10:30', { isDeposit: true, patientName: 'Lina Zouari', patientId: 9 })],
	closing: null
};
const balances = [
	{ patientId: 7, name: 'Sami Trabelsi', phone: '+21620123456', dueMillimes: 390000, lastPaymentAt: '2026-10-03T11:00:00+01:00' },
	{ patientId: 12, name: 'Rim Haddad', phone: '+21620000012', dueMillimes: 40000, lastPaymentAt: null }
];

function cashApi(extra: Record<string, Handler> = {}) {
	return mockApi({
		'GET /api/cash?day=2026-10-30': () => json(200, day),
		'GET /api/balances?limit=100': () => json(200, balances),
		...extra
	});
}

describe('/app/caisse – the cash book of the day', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
		clock.now = () => new Date(NOW);
		history.replaceState(null, '', '/app/caisse');
	});

	it('shows the total, the split by payment method and every payment with its receipt', async () => {
		cashApi();
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'Caisse' })).toBeInTheDocument();
		expect((await screen.findByText('Encaissé ce jour')).parentElement).toHaveTextContent('265 DT');
		const methods = within(screen.getByRole('list', { name: 'Par mode de paiement' }));
		expect(methods.getByText('Espèces').closest('li')).toHaveTextContent('185 DT');
		expect(methods.getByText('D17').closest('li')).toHaveTextContent('80 DT');
		const payments = within(screen.getByRole('table', { name: 'Paiements du jour' }));
		const row = payments.getByRole('row', { name: /10:30/ });
		expect(row).toHaveTextContent('Lina Zouari');
		expect(row).toHaveTextContent('Acompte');
		expect(within(row).getByRole('link', { name: 'Lina Zouari' })).toHaveAttribute('href', '/app/patients/9');
		expect(within(row).getByRole('link', { name: 'Reçu' })).toHaveAttribute('href', '/app/recu/72');
	});

	it('lists what patients still owe', async () => {
		cashApi();
		render(Page);
		const owed = within(await screen.findByRole('region', { name: 'Montants dus' }));
		expect(await owed.findByText('Total dû : 430 DT')).toBeInTheDocument();
		expect(owed.getByRole('link', { name: /Sami Trabelsi/ })).toHaveAttribute('href', '/app/patients/7');
		expect(owed.getByRole('link', { name: /Sami Trabelsi/ })).toHaveTextContent('390 DT');
		expect(owed.getByRole('link', { name: /Rim Haddad/ })).toHaveTextContent('Aucun paiement');
	});

	it('closes the cash with the counted amount and shows the difference', async () => {
		cashApi({
			'POST /api/cash/close': () =>
				json(200, { expectedCashMillimes: 185000, countedCashMillimes: 180000, differenceMillimes: -5000, closedBy: 'Salma', closedAt: '2026-10-30T18:05:00+01:00' })
		});
		render(Page);
		const closing = within(await screen.findByRole('region', { name: 'Clôture de caisse' }));
		expect(closing.getByText('Espèces attendues').parentElement).toHaveTextContent('185 DT');
		await fireEvent.click(closing.getByRole('button', { name: 'Clôturer la caisse' }));
		expect(await closing.findByRole('alert')).toHaveTextContent('Indiquez le montant compté');
		await fireEvent.input(closing.getByLabelText('Espèces comptées (DT)'), { target: { value: '180' } });
		await fireEvent.input(closing.getByLabelText('Note (facultatif)'), { target: { value: 'Monnaie rendue' } });
		await fireEvent.click(closing.getByRole('button', { name: 'Clôturer la caisse' }));
		await vi.waitFor(() => expect(sentJson('POST /api/cash/close')).toEqual({ day: '2026-10-30', countedCashMillimes: 180000, note: 'Monnaie rendue' }));
		expect(await closing.findByText('Manque 5 DT')).toBeInTheDocument();
		expect(closing.getByText('Clôturée par Salma à 18:05')).toBeInTheDocument();
		expect(closing.getByText('En attente de validation par le titulaire.')).toBeInTheDocument();
		expect(closing.queryByRole('button', { name: 'Valider la clôture' })).not.toBeInTheDocument();
	});

	it('lets the owner verify a closed day', async () => {
		auth.set('tok', owner);
		cashApi({
			'GET /api/cash?day=2026-10-30': () =>
				json(200, { ...day, closing: { expectedCashMillimes: 185000, countedCashMillimes: 185000, differenceMillimes: 0, note: '', closedBy: 'Salma', closedAt: '2026-10-30T18:05:00+01:00', verifiedBy: null, verifiedAt: null } }),
			'POST /api/cash/2026-10-30/verify': () => json(200, { verifiedBy: 'Amira', verifiedAt: '2026-10-30T19:00:00+01:00' })
		});
		render(Page);
		const closing = within(await screen.findByRole('region', { name: 'Clôture de caisse' }));
		expect(await closing.findByText('La caisse est juste.')).toBeInTheDocument();
		await fireEvent.click(closing.getByRole('button', { name: 'Valider la clôture' }));
		expect(await closing.findByText('Validée par Amira le 30/10/2026 19:00')).toBeInTheDocument();
	});

	it('goes to another day (also from the address)', async () => {
		history.replaceState(null, '', '/app/caisse?day=2026-10-29');
		cashApi({ 'GET /api/cash?day=2026-10-29': () => json(200, { day: '2026-10-29', totalMillimes: 0, byMethod: {}, payments: [], closing: null }) });
		render(Page);
		expect(await screen.findByText('Aucun paiement ce jour.')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Jour suivant' }));
		expect(await screen.findByRole('table', { name: 'Paiements du jour' })).toBeInTheDocument();
	});

	it('explains a loading problem and is translated into Arabic', async () => {
		i18n.setLocale('ar');
		cashApi({ 'GET /api/cash?day=2026-10-30': () => problem(500, 'server_error') });
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'الصندوق' })).toBeInTheDocument();
		expect(await screen.findByRole('alert')).toHaveTextContent('تعذّر تحميل الصندوق.');
	});
});
