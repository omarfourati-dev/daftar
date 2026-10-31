import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Reservation from './reservation/+page.svelte';
import Ecran from './ecran/+page.svelte';
import Donnees from './donnees/+page.svelte';
import { auth } from '#lib/auth.svelte';
import { i18n } from '#lib/i18n.svelte';
import { json, mockApi, sentJson } from '#lib/test-utils';
import { owner, practice } from '#lib/testing/fixtures';

describe('/app/reglages/reservation', () => {
	beforeEach(() => {
		i18n.setLocale('fr');
		auth.set('tok', owner);
	});

	it('shows the booking link with QR code and poster, and saves the settings', async () => {
		mockApi({
			'GET /api/practice': () => json(200, practice()),
			'PATCH /api/practice': () => json(200, practice({ onlineBooking: { enabled: true, autoConfirm: true, horizonDays: 30, minNoticeHours: 2, maxPerDay: 20, blockNoShows: 2 } }))
		});
		render(Reservation);
		const url = `http://cabinet-lac.${location.host}/`;
		expect(await screen.findByRole('textbox', { name: 'Adresse de la page' })).toHaveValue(url);
		expect(await screen.findByRole('img', { name: 'QR code de la page de réservation' })).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Imprimer l’affiche A4' })).toHaveAttribute('href', '/app/reglages/affiche');
		expect(screen.getByRole('link', { name: 'Envoyer par WhatsApp' }).getAttribute('href')).toContain(encodeURIComponent(url));
		await fireEvent.click(screen.getByRole('checkbox', { name: 'Confirmer les demandes automatiquement' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
		await vi.waitFor(() =>
			expect(sentJson('PATCH /api/practice')).toEqual({
				onlineBooking: { enabled: true, autoConfirm: true, horizonDays: 30, minNoticeHours: 2, maxPerDay: 20, blockNoShows: 2 }
			})
		);
		expect(await screen.findByText('Modifications enregistrées.')).toBeInTheDocument();
	});

	it('says when online booking is switched off', async () => {
		mockApi({ 'GET /api/practice': () => json(200, practice({ onlineBooking: undefined, onlineBookingEnabled: false })) });
		render(Reservation);
		expect(await screen.findByText(/La réservation en ligne est désactivée/)).toBeInTheDocument();
		expect(screen.getByRole('checkbox', { name: 'Réservation en ligne activée' })).not.toBeChecked();
	});
});

describe('/app/reglages/ecran', () => {
	beforeEach(() => {
		i18n.setLocale('fr');
		auth.set('tok', owner);
	});

	it('shows the waiting-room screen address on the app host and makes a new one', async () => {
		mockApi({
			'GET /api/practice': () => json(200, practice()),
			'POST /api/practice/display-token': () => json(200, { displayToken: 'disp-token-2' })
		});
		render(Ecran);
		expect(await screen.findByRole('textbox', { name: 'Adresse de l’écran' })).toHaveValue(`http://app.${location.host}/salle/disp-token-1`);
		await fireEvent.click(screen.getByRole('button', { name: 'Générer une nouvelle adresse' }));
		await fireEvent.click(within(screen.getByRole('dialog', { name: 'Générer une nouvelle adresse ?' })).getByRole('button', { name: 'Générer la nouvelle adresse' }));
		expect(await screen.findByText('Nouvelle adresse créée.')).toBeInTheDocument();
		expect(screen.getByRole('textbox', { name: 'Adresse de l’écran' })).toHaveValue(`http://app.${location.host}/salle/disp-token-2`);
	});
});

describe('/app/reglages/donnees', () => {
	const createObjectURL = vi.fn(() => 'blob:export');
	const revokeObjectURL = vi.fn();
	beforeEach(() => {
		i18n.setLocale('fr');
		auth.set('tok', owner);
		Object.assign(URL, { createObjectURL, revokeObjectURL });
	});
	afterEach(() => vi.restoreAllMocks());

	it('downloads the export as a JSON file', async () => {
		const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
		mockApi({
			'GET /api/practice/export': () => new Response('{"patients":[]}', { status: 200, headers: { 'Content-Type': 'application/json' } })
		});
		render(Donnees);
		await fireEvent.click(screen.getByRole('button', { name: 'Télécharger l’export' }));
		expect(await screen.findByText('Export téléchargé.')).toBeInTheDocument();
		expect(click).toHaveBeenCalled();
		const anchor = click.mock.contexts[0] as HTMLAnchorElement;
		expect(anchor.download).toMatch(/^daftar-export-cabinet-lac-\d{4}-\d{2}-\d{2}\.json$/);
		expect(screen.getByRole('link', { name: 'Importer depuis Excel' })).toHaveAttribute('href', '/app/import');
	});
});
