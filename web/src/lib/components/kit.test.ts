import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { tick } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ConfirmDialog from './ConfirmDialog.svelte';
import CopyLink from './CopyLink.svelte';
import HoursEditorHarness from './HoursEditorHarness.test.svelte';
import QrCode from './QrCode.svelte';
import { i18n } from '../i18n.svelte';

describe('CopyLink', () => {
	const writeText = vi.fn(async () => undefined);
	beforeEach(() => {
		i18n.setLocale('fr');
		writeText.mockClear();
		Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
	});

	it('shows the address, copies it and says so', async () => {
		render(CopyLink, { props: { label: 'Lien d’invitation', url: 'https://cabinet-lac.daftar.omarfourati.de/invitation#abc' } });
		const field = screen.getByRole('textbox', { name: 'Lien d’invitation' });
		expect(field).toHaveValue('https://cabinet-lac.daftar.omarfourati.de/invitation#abc');
		expect(field).toHaveAttribute('readonly');
		await fireEvent.click(screen.getByRole('button', { name: 'Copier' }));
		expect(writeText).toHaveBeenCalledWith('https://cabinet-lac.daftar.omarfourati.de/invitation#abc');
		expect(await screen.findByRole('status')).toHaveTextContent('Copié');
	});

	it('offers WhatsApp with a ready message and opening the page', () => {
		render(CopyLink, {
			props: { label: 'Page de réservation', url: 'https://x.tn/', whatsappText: 'Réservez ici : https://x.tn/', whatsappTo: '+216 20 123 456', openable: true }
		});
		expect(screen.getByRole('link', { name: 'Envoyer par WhatsApp' })).toHaveAttribute(
			'href',
			'https://wa.me/21620123456?text=R%C3%A9servez%20ici%20%3A%20https%3A%2F%2Fx.tn%2F'
		);
		const open = screen.getByRole('link', { name: 'Ouvrir' });
		expect(open).toHaveAttribute('href', 'https://x.tn/');
		expect(open).toHaveAttribute('target', '_blank');
		expect(open).toHaveAttribute('rel', 'noopener');
	});

	it('explains when the browser refuses to copy', async () => {
		writeText.mockRejectedValueOnce(new Error('denied'));
		render(CopyLink, { props: { label: 'Lien', url: 'https://x.tn/' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Copier' }));
		expect(await screen.findByRole('status')).toHaveTextContent('Copie impossible');
	});
});

describe('QrCode', () => {
	it('draws the QR code locally as SVG with an accessible name', async () => {
		render(QrCode, { props: { text: 'https://cabinet-lac.daftar.omarfourati.de/', label: 'QR code de la page de réservation' } });
		const img = await screen.findByRole('img', { name: 'QR code de la page de réservation' });
		await vi.waitFor(() => expect(img.querySelector('svg')).not.toBeNull());
		expect(img.innerHTML).not.toMatch(/<image|href=/); // drawn as paths, nothing loaded
	});
});

describe('ConfirmDialog', () => {
	beforeEach(() => i18n.setLocale('fr'));

	it('asks, confirms and closes with Escape', async () => {
		const onconfirm = vi.fn();
		const oncancel = vi.fn();
		render(ConfirmDialog, {
			props: { open: true, title: 'Supprimer l’acte ?', message: 'Les rendez-vous gardent leur motif.', confirmLabel: 'Supprimer l’acte', onconfirm, oncancel }
		});
		const dialog = screen.getByRole('dialog', { name: 'Supprimer l’acte ?' });
		expect(dialog).toHaveAttribute('aria-modal', 'true');
		expect(within(dialog).getByText('Les rendez-vous gardent leur motif.')).toBeInTheDocument();
		await fireEvent.click(within(dialog).getByRole('button', { name: 'Supprimer l’acte' }));
		expect(onconfirm).toHaveBeenCalledOnce();
		await fireEvent.keyDown(dialog, { key: 'Escape' });
		expect(oncancel).toHaveBeenCalledOnce();
	});

	it('can require typing a name before a dangerous action', async () => {
		const onconfirm = vi.fn();
		render(ConfirmDialog, {
			props: { open: true, title: 'Supprimer le cabinet ?', message: 'Tout sera effacé.', confirmLabel: 'Supprimer définitivement', typeToConfirm: 'Cabinet du Lac', danger: true, onconfirm }
		});
		const button = screen.getByRole('button', { name: 'Supprimer définitivement' });
		expect(button).toBeDisabled();
		await fireEvent.input(screen.getByLabelText(/Tapez « Cabinet du Lac » pour confirmer/), { target: { value: 'Cabinet du Lac' } });
		expect(button).toBeEnabled();
		await fireEvent.click(button);
		expect(onconfirm).toHaveBeenCalledOnce();
	});
});

describe('HoursEditor', () => {
	beforeEach(() => i18n.setLocale('fr'));
	afterEach(() => i18n.setLocale('fr'));

	it('opens a closed day with a first window and closes it again', async () => {
		render(HoursEditorHarness);
		const sunday = screen.getByRole('checkbox', { name: 'Dimanche' });
		expect(sunday).not.toBeChecked();
		await fireEvent.click(sunday);
		expect(screen.getByLabelText('Dimanche – début de la plage 1')).toHaveValue('08:00');
		expect(screen.getByLabelText('Dimanche – fin de la plage 1')).toHaveValue('12:00');
		await fireEvent.click(sunday);
		expect(screen.queryByLabelText('Dimanche – début de la plage 1')).not.toBeInTheDocument();
		expect(screen.getByTestId('value').textContent).toContain('"7":[]');
	});

	it('adds a window after a break and removes one', async () => {
		render(HoursEditorHarness);
		await fireEvent.click(screen.getByRole('button', { name: 'Ajouter une plage le lundi' }));
		expect(screen.getByLabelText('Lundi – début de la plage 3')).toHaveValue('19:00');
		expect(screen.getByLabelText('Lundi – fin de la plage 3')).toHaveValue('20:00');
		await fireEvent.click(screen.getByRole('button', { name: 'Supprimer la plage 14:00–18:00 du lundi' }));
		expect(screen.getByTestId('value').textContent).toContain('"1":[["08:00","12:30"],["19:00","20:00"]]');
	});

	it('copies a day to the other open days', async () => {
		render(HoursEditorHarness);
		await fireEvent.input(screen.getByLabelText('Lundi – fin de la plage 1'), { target: { value: '13:00' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Copier les horaires du lundi sur les autres jours ouverts' }));
		const value = JSON.parse(screen.getByTestId('value').textContent ?? '{}');
		expect(value['3']).toEqual([
			['08:00', '13:00'],
			['14:00', '18:00']
		]);
		expect(value['7']).toEqual([]); // closed days stay closed
	});

	it('explains a window that ends before it starts, next to the day', async () => {
		render(HoursEditorHarness);
		await fireEvent.input(screen.getByLabelText('Mardi – fin de la plage 1'), { target: { value: '07:00' } });
		await tick();
		expect(screen.getByText('Mardi : la fin doit être après le début.')).toBeInTheDocument();
		expect(screen.getByLabelText('Mardi – fin de la plage 1')).toHaveAttribute('aria-invalid', 'true');
	});

	it('speaks Arabic and keeps times left to right', async () => {
		i18n.setLocale('ar');
		render(HoursEditorHarness);
		expect(screen.getByRole('checkbox', { name: 'الاثنين' })).toBeChecked();
		expect(screen.getByLabelText('الاثنين – بداية الفترة 1')).toHaveAttribute('dir', 'ltr');
	});
});
