import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { clock } from '#lib/clock';
import { i18n } from '#lib/i18n.svelte';
import { json, mockApi } from '#lib/test-utils';
import { appt, assistant, NOW, practice, practitioners, services } from '#lib/agenda/fixtures';

function api(list: unknown[]) {
	return mockApi({
		'GET /api/practice': () => json(200, practice),
		'GET /api/practitioners': () => json(200, practitioners),
		'GET /api/services': () => json(200, services),
		'GET /api/closures': () => json(200, []),
		'GET /api/appointments?from=2026-11-02&to=2026-11-02': () => json(200, list)
	});
}

describe('/app/agenda/imprimer – the day on paper', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
		clock.now = () => new Date(NOW);
		history.replaceState(null, '', '/app/agenda/imprimer?date=2026-11-02');
	});

	it('lists the appointments of the day per practitioner, without the cancelled ones', async () => {
		api([
			appt({ id: 1, startsAt: '2026-11-02T08:30:00+01:00', notes: 'À jeun', patient: { id: 1, firstName: 'Mounia', lastName: 'Chebbi', phone: '+21620000001', noShows: 0, alerts: 'Diabète' } }),
			appt({ id: 2, startsAt: '2026-11-02T09:00:00+01:00', practitionerId: 12, practitionerName: 'Karim Jaziri', status: 'confirmed', reason: 'Vaccination' }),
			appt({ id: 3, startsAt: '2026-11-02T10:00:00+01:00', status: 'cancelled', patient: { id: 3, firstName: 'Riadh', lastName: 'Ben Youssef', phone: '+21620000003', noShows: 0 } })
		]);
		render(Page);
		expect(await screen.findByRole('heading', { level: 1, name: 'Rendez-vous du lundi 2 novembre 2026' })).toBeInTheDocument();
		const amira = within(await screen.findByRole('table', { name: 'Dr Amira Ben Salem' }));
		const row = amira.getByRole('row', { name: /08:30/ });
		expect(row).toHaveTextContent('Mounia Chebbi');
		expect(row).toHaveTextContent('+216 20 000 001');
		expect(row).toHaveTextContent('À jeun');
		expect(row).toHaveTextContent('Diabète');
		expect(within(screen.getByRole('table', { name: 'Dr Karim Jaziri' })).getByRole('row', { name: /09:00/ })).toHaveTextContent('Vaccination');
		expect(screen.queryByText('Riadh Ben Youssef')).not.toBeInTheDocument();
		expect(screen.getByText('Cabinet du Lac')).toBeInTheDocument();
	});

	it('prints with one click and goes back to the same day', async () => {
		api([]);
		const print = vi.spyOn(window, 'print').mockImplementation(() => undefined);
		render(Page);
		expect(await screen.findByText('Aucun rendez-vous ce jour.')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Imprimer' }));
		expect(print).toHaveBeenCalled();
		expect(screen.getByRole('link', { name: 'Retour à l’agenda' })).toHaveAttribute('href', '/app/agenda?date=2026-11-02');
	});

	it('prints in Arabic', async () => {
		i18n.setLocale('ar');
		api([appt({ id: 1, startsAt: '2026-11-02T08:30:00+01:00' })]);
		render(Page);
		expect(await screen.findByRole('heading', { level: 1, name: /مواعيد يوم/ })).toBeInTheDocument();
		expect(await screen.findByRole('columnheader', { name: 'المريض' })).toBeInTheDocument();
	});
});
