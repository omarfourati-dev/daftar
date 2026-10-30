import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { deps } from '#lib/api';
import { auth } from '#lib/auth.svelte';
import { clock } from '#lib/clock';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, mockApi, noContent, problem, sentJson, type Handler } from '#lib/test-utils';
import { appt, assistant, NOW, owner, practiceBrief } from '#lib/agenda/fixtures';
import { ledger, patientFile } from '#lib/agenda/patient-fixtures';

const file = patientFile({
	noShows: 2,
	alerts: 'Sous anticoagulant',
	samePhone: [{ id: 9, firstName: 'Leila', lastName: 'Trabelsi' }]
});
const upcoming = appt({ id: 80, startsAt: '2026-11-07T09:30:00+01:00', reason: 'Pose de la couronne', status: 'confirmed', patient: { id: 7, firstName: 'Sami', lastName: 'Trabelsi', phone: '+21620123456', noShows: 2 } });
const past = appt({ id: 81, startsAt: '2026-10-03T10:00:00+01:00', reason: 'Couronne', status: 'done', patient: upcoming.patient });

function fileApi(extra: Record<string, Handler> = {}) {
	return mockApi({
		'GET /api/patients/7': () => json(200, file),
		'GET /api/patients/7/appointments': () => json(200, [upcoming, past]),
		'GET /api/patients/7/ledger': () => json(200, ledger),
		...extra
	});
}

describe('/app/patients/[id] – the patient file', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
		clock.now = () => new Date(NOW);
		history.replaceState(null, '', '/app/patients/7');
	});

	it('shows identity, medical alert, same number, reliability and the balance', async () => {
		fileApi();
		render(Page);
		expect(await screen.findByRole('heading', { level: 1, name: 'Sami Trabelsi' })).toBeInTheDocument();
		expect(screen.getByText('+216 20 123 456')).toBeInTheDocument();
		expect(screen.getByText('né(e) en 1978')).toBeInTheDocument();
		expect(screen.getByRole('note')).toHaveTextContent('Sous anticoagulant');
		expect(screen.getByRole('link', { name: 'Leila Trabelsi' })).toHaveAttribute('href', '/app/patients/9');
		const reliability = within(screen.getByRole('list', { name: 'Fiabilité' }));
		expect(reliability.getByText('Venu').parentElement).toHaveTextContent('4');
		expect(reliability.getByText('Absent').parentElement).toHaveTextContent('2');
		expect(reliability.getByText('Annulé').parentElement).toHaveTextContent('1');
		expect(screen.getByText('Acompte conseillé pour le prochain rendez-vous.')).toBeInTheDocument();
		const balance = within(screen.getByRole('region', { name: 'Solde' }));
		expect(balance.getByText('Total des actes').parentElement).toHaveTextContent('990 DT');
		expect(balance.getByText('Payé').parentElement).toHaveTextContent('600 DT');
		expect(balance.getByText('Reste à payer').parentElement).toHaveTextContent('390 DT');
		expect(screen.getByRole('link', { name: 'Nouveau rendez-vous' })).toHaveAttribute('href', '/app/agenda?nouveau=1&patient=7');
		const next = within(screen.getByRole('region', { name: 'Prochains rendez-vous' }));
		expect(next.getByText(/Pose de la couronne/)).toBeInTheDocument();
	});

	it('lists treatments and payments with receipts, and the appointments in their tab', async () => {
		fileApi();
		render(Page);
		const money = await screen.findByRole('tabpanel', { name: 'Actes et paiements' });
		const treatments = within(within(money).getByRole('table', { name: 'Actes' }));
		expect(treatments.getAllByRole('row')).toHaveLength(4);
		expect(treatments.getByRole('row', { name: /Couronne/ })).toHaveTextContent('650 DT');
		expect(treatments.queryByRole('columnheader', { name: 'Dent' })).not.toBeInTheDocument(); // only for dentists
		const payments = within(within(money).getByRole('table', { name: 'Paiements' }));
		expect(payments.getByRole('row', { name: /D17/ })).toHaveTextContent('400 DT');
		expect(payments.getAllByRole('link', { name: 'Reçu' })[0]).toHaveAttribute('href', '/app/recu/70');
		await fireEvent.click(screen.getByRole('tab', { name: 'Rendez-vous' }));
		const list = within(screen.getByRole('tabpanel', { name: 'Rendez-vous' }));
		expect(list.getByText(/Couronne/)).toBeInTheDocument();
		expect(list.getByText('Terminé')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('tab', { name: 'Notes' }));
		expect(screen.getByRole('tabpanel', { name: 'Notes' })).toHaveTextContent('Préfère les rendez-vous le matin.');
	});

	it('shows the tooth for dentists', async () => {
		auth.set('tok', { ...assistant, practice: { ...practiceBrief, specialty: 'dentiste' } });
		fileApi();
		render(Page);
		const treatments = within(await screen.findByRole('table', { name: 'Actes' }));
		expect(treatments.getByRole('columnheader', { name: 'Dent' })).toBeInTheDocument();
		expect(treatments.getByRole('row', { name: /Couronne/ })).toHaveTextContent('26');
	});

	it('adds a treatment and updates the balance', async () => {
		let added = false;
		fileApi({
			'POST /api/patients/7/treatments': () => {
				added = true;
				return json(201, { id: 4, label: 'Consultation', tooth: null, priceMillimes: 40000, performedOn: '2026-10-30', appointmentId: null, createdAt: NOW });
			},
			'GET /api/patients/7': () => json(200, added ? { ...file, totalMillimes: 1030000, dueMillimes: 430000 } : file),
			'GET /api/patients/7/ledger': () => json(200, added ? { ...ledger, totalMillimes: 1030000, dueMillimes: 430000 } : ledger)
		});
		render(Page);
		await fireEvent.click(await screen.findByRole('button', { name: 'Acte' }));
		const dialog = within(screen.getByRole('dialog', { name: 'Nouvel acte' }));
		await fireEvent.input(dialog.getByLabelText('Acte'), { target: { value: 'Consultation' } });
		await fireEvent.input(dialog.getByLabelText('Prix (DT)'), { target: { value: '40' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Ajouter l’acte' }));
		await vi.waitFor(() => expect(sentJson('POST /api/patients/7/treatments')).toEqual({ label: 'Consultation', priceMillimes: 40000, performedOn: '2026-10-30' }));
		expect(await screen.findByText('Acte ajouté.')).toBeInTheDocument();
		expect(within(screen.getByRole('region', { name: 'Solde' })).getByText('Reste à payer').parentElement).toHaveTextContent('430 DT');
	});

	it('records a payment (the amount due is proposed) and offers the receipt', async () => {
		fileApi({
			'POST /api/patients/7/payments': () =>
				json(201, { id: 72, patientId: 7, patientName: 'Sami Trabelsi', amountMillimes: 390000, method: 'cash', paidAt: NOW, appointmentId: null, isDeposit: false, note: '', receivedByName: 'Salma' })
		});
		render(Page);
		await fireEvent.click(await screen.findByRole('button', { name: 'Paiement' }));
		const dialog = within(screen.getByRole('dialog', { name: 'Nouveau paiement' }));
		expect(dialog.getByLabelText('Montant (DT)')).toHaveValue('390');
		expect(dialog.getByLabelText('Mode de paiement')).toHaveValue('cash');
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer le paiement' }));
		await vi.waitFor(() => expect(sentJson('POST /api/patients/7/payments')).toEqual({ amountMillimes: 390000, method: 'cash', note: '' }));
		expect(await screen.findByText('Paiement enregistré.')).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Imprimer le reçu' })).toHaveAttribute('href', '/app/recu/72');
	});

	it('records a deposit for a coming appointment, dated another day', async () => {
		fileApi({ 'POST /api/patients/7/payments': () => json(201, { id: 73 }) });
		render(Page);
		await fireEvent.click(await screen.findByRole('button', { name: 'Paiement' }));
		const dialog = within(screen.getByRole('dialog', { name: 'Nouveau paiement' }));
		await fireEvent.input(dialog.getByLabelText('Montant (DT)'), { target: { value: '20' } });
		await fireEvent.change(dialog.getByLabelText('Mode de paiement'), { target: { value: 'd17' } });
		await fireEvent.input(dialog.getByLabelText('Date'), { target: { value: '2026-10-29' } });
		await fireEvent.click(dialog.getByLabelText('C’est un acompte pour un rendez-vous'));
		await fireEvent.change(dialog.getByLabelText('Rendez-vous'), { target: { value: '80' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer le paiement' }));
		await vi.waitFor(() =>
			expect(sentJson('POST /api/patients/7/payments')).toEqual({
				amountMillimes: 20000,
				method: 'd17',
				note: '',
				paidAt: '2026-10-29T12:00:00+01:00',
				isDeposit: true,
				appointmentId: 80
			})
		);
	});

	it('edits the patient data', async () => {
		fileApi({ 'PATCH /api/patients/7': () => json(200, { ...file, phone: '+21620999888' }) });
		render(Page);
		await fireEvent.click(await screen.findByRole('button', { name: 'Modifier' }));
		const dialog = within(screen.getByRole('dialog', { name: 'Modifier le patient' }));
		expect(dialog.getByLabelText('Alerte médicale (allergie, anticoagulant…)')).toHaveValue('Sous anticoagulant');
		await fireEvent.input(dialog.getByLabelText('Téléphone'), { target: { value: '20 999 888' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer' }));
		await vi.waitFor(() => expect(sentJson('PATCH /api/patients/7')).toMatchObject({ phone: '20 999 888', alerts: 'Sous anticoagulant' }));
		expect(await screen.findByText('+216 20 999 888')).toBeInTheDocument();
	});

	it('lets only the owner delete, after typing the full name', async () => {
		auth.set('tok', owner);
		fileApi({ 'DELETE /api/patients/7': () => noContent(), 'DELETE /api/payments/70': () => noContent() });
		render(Page);
		await fireEvent.click(await screen.findByRole('button', { name: 'Supprimer le patient' }));
		const dialog = within(screen.getByRole('dialog', { name: 'Supprimer Sami Trabelsi ?' }));
		const confirm = dialog.getByRole('button', { name: 'Supprimer définitivement' });
		expect(confirm).toBeDisabled();
		await fireEvent.input(dialog.getByLabelText('Pour confirmer, tapez le nom complet : Sami Trabelsi'), { target: { value: 'sami trabelsi ' } });
		expect(confirm).toBeEnabled();
		await fireEvent.click(confirm);
		await vi.waitFor(() => expect(deps.goto).toHaveBeenCalledWith('/app/patients'));
		expect(calls()).toContain('DELETE /api/patients/7');
	});

	it('hides deleting from the staff', async () => {
		fileApi();
		render(Page);
		await screen.findByRole('heading', { level: 1, name: 'Sami Trabelsi' });
		expect(screen.queryByRole('button', { name: 'Supprimer le patient' })).not.toBeInTheDocument();
		expect(screen.queryByRole('button', { name: /Supprimer le paiement/ })).not.toBeInTheDocument();
	});

	it('the owner can delete a payment after confirmation', async () => {
		auth.set('tok', owner);
		fileApi({ 'DELETE /api/payments/70': () => noContent() });
		render(Page);
		await fireEvent.click(await screen.findByRole('button', { name: 'Supprimer le paiement du 12/09/2026' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Oui, supprimer' }));
		await vi.waitFor(() => expect(calls()).toContain('DELETE /api/payments/70'));
	});

	it('explains an unknown patient', async () => {
		mockApi({
			'GET /api/patients/7': () => problem(404, 'not_found'),
			'GET /api/patients/7/appointments': () => problem(404, 'not_found'),
			'GET /api/patients/7/ledger': () => problem(404, 'not_found')
		});
		render(Page);
		expect(await screen.findByRole('alert')).toHaveTextContent('Ce patient n’existe pas ou a été supprimé.');
		expect(screen.getByRole('link', { name: 'Tous les patients' })).toHaveAttribute('href', '/app/patients');
	});

	it('is translated into Arabic', async () => {
		i18n.setLocale('ar');
		fileApi();
		render(Page);
		expect(await screen.findByRole('tab', { name: 'الخدمات والدفعات' })).toBeInTheDocument();
		expect(screen.getByRole('region', { name: 'الرصيد' })).toBeInTheDocument();
	});
});
