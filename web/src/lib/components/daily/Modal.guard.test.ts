import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AppointmentForm from '../agenda/AppointmentForm.svelte';
import PaymentForm from '../patients/PaymentForm.svelte';
import TicketForm from '../salle/TicketForm.svelte';
import { auth } from '../../auth.svelte';
import { clock } from '../../clock';
import { i18n } from '../../i18n.svelte';
import { json, mockApi } from '../../test-utils';
import { assistant, NOW, practice, practitioners, services } from '../../agenda/fixtures';

/** Code review N6: a tap next to the sheet (or Escape) must not throw away what was typed at the desk. */
const backdrop = () => screen.getAllByRole('button', { name: 'Fermer' })[0];
const escape = () => fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });

describe('form dialogs ask before Escape or the backdrop throw away the input', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
		clock.now = () => new Date(NOW);
		mockApi({});
	});

	it('closes at once while nothing was entered', async () => {
		const onclose = vi.fn();
		render(AppointmentForm, { props: { base: { practice, practitioners, services, closures: [] }, day: '2026-10-30', time: '09:15', onsaved: vi.fn(), onclose } });
		await escape();
		expect(onclose).toHaveBeenCalledTimes(1);
		await fireEvent.click(backdrop());
		expect(onclose).toHaveBeenCalledTimes(2);
	});

	it('asks after a change: "Continuer la saisie" keeps everything, "Abandonner" closes', async () => {
		const onclose = vi.fn();
		render(AppointmentForm, { props: { base: { practice, practitioners, services, closures: [] }, day: '2026-10-30', time: '09:15', onsaved: vi.fn(), onclose } });
		await fireEvent.input(screen.getByLabelText('Note interne'), { target: { value: 'Rappeler la veille' } });
		await escape();
		const ask = within(screen.getByRole('alertdialog', { name: 'Abandonner les modifications ?' }));
		expect(ask.getByText('Ce que vous avez saisi sera perdu.')).toBeInTheDocument();
		expect(ask.getByRole('button', { name: 'Continuer la saisie' })).toHaveFocus();
		await fireEvent.click(ask.getByRole('button', { name: 'Continuer la saisie' }));
		expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
		expect(screen.getByLabelText('Note interne')).toHaveValue('Rappeler la veille');
		expect(onclose).not.toHaveBeenCalled();
		await fireEvent.click(backdrop());
		await fireEvent.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Abandonner' }));
		expect(onclose).toHaveBeenCalledTimes(1);
	});

	it('"Annuler" and the close button still close at once', async () => {
		const onclose = vi.fn();
		render(PaymentForm, { props: { patientId: 7, due: 50000, appointments: [], onsaved: vi.fn(), onclose } });
		await fireEvent.input(screen.getByLabelText('Montant (DT)'), { target: { value: '20' } });
		await fireEvent.click(backdrop());
		expect(screen.getByRole('alertdialog')).toBeInTheDocument();
		await fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' }); // Escape on the question: back to the form
		expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Annuler' }));
		expect(onclose).toHaveBeenCalledTimes(1);
	});

	it('no question once the ticket is given', async () => {
		const onclose = vi.fn();
		mockApi({ 'POST /api/queue': () => json(201, { id: 1, ticketNo: 4, name: 'Passant', phone: null, patientId: null, appointmentId: null, appointmentAt: null, status: 'waiting', arrivedAt: NOW, calledAt: null, doneAt: null, ticketToken: 't'.repeat(32), position: 1, peopleAhead: 0, estimatedWaitMin: 0, alerts: '' }) });
		render(TicketForm, { props: { practice: 'Cabinet du Lac', oncreated: vi.fn(), onclose } });
		await fireEvent.click(screen.getByLabelText('Juste un nom'));
		await fireEvent.input(screen.getByLabelText('Nom'), { target: { value: 'Passant' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Donner le ticket' }));
		expect(await screen.findByText('Ticket 4 pour Passant')).toBeInTheDocument();
		await escape();
		expect(onclose).toHaveBeenCalledTimes(1);
	});

	it('asks in Arabic', async () => {
		i18n.setLocale('ar');
		render(PaymentForm, { props: { patientId: 7, due: 0, appointments: [], onsaved: vi.fn(), onclose: vi.fn() } });
		await fireEvent.input(screen.getAllByRole('textbox')[0], { target: { value: '5' } });
		await escape();
		expect(screen.getByRole('alertdialog', { name: 'تجاهل التعديلات؟' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'مواصلة الإدخال' })).toBeInTheDocument();
	});
});
