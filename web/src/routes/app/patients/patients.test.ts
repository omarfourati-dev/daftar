import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { deps } from '#lib/api';
import { auth } from '#lib/auth.svelte';
import { clock } from '#lib/clock';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, mockApi, problem, sentJson } from '#lib/test-utils';
import { assistant, NOW } from '#lib/agenda/fixtures';
import { patientFile, summary } from '#lib/agenda/patient-fixtures';

const sami = summary({ nextAppointmentAt: '2026-11-02T10:30:00+01:00', dueMillimes: 40000 });
const lina = summary({ id: 9, firstName: 'Lina', lastName: 'Zouari', phone: '+21620000002', noShows: 3, hasAlerts: true, attended: 1 });

describe('/app/patients – list and search', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
		clock.now = () => new Date(NOW);
		history.replaceState(null, '', '/app/patients');
	});

	it('lists the patients with next appointment, no-shows and what they owe', async () => {
		mockApi({ 'GET /api/patients?q=&limit=50&offset=0': () => json(200, { items: [sami, lina], total: 2 }) });
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'Patients' })).toBeInTheDocument();
		expect(await screen.findByText('2 patients')).toBeInTheDocument();
		const row = screen.getByRole('link', { name: /Sami Trabelsi/ });
		expect(row).toHaveAttribute('href', '/app/patients/7');
		expect(row).toHaveTextContent('+216 20 123 456');
		expect(row).toHaveTextContent('lun. 2 nov. 10:30');
		expect(row).toHaveTextContent('40 DT');
		const other = screen.getByRole('link', { name: /Lina Zouari/ });
		expect(other).toHaveTextContent('3 absences');
		expect(other).toHaveTextContent('Alerte médicale');
	});

	it('searches by name or phone, also from the address', async () => {
		history.replaceState(null, '', '/app/patients?q=ben');
		mockApi({
			'GET /api/patients?q=ben&limit=50&offset=0': () => json(200, { items: [sami], total: 1 }),
			'GET /api/patients?q=2000&limit=50&offset=0': () => json(200, { items: [], total: 0 })
		});
		render(Page);
		expect(screen.getByRole('searchbox', { name: 'Rechercher par nom ou téléphone' })).toHaveValue('ben');
		expect(await screen.findByRole('link', { name: /Sami Trabelsi/ })).toBeInTheDocument();
		await fireEvent.input(screen.getByRole('searchbox'), { target: { value: '2000' } });
		expect(await screen.findByText('Aucun patient trouvé pour « 2000 ».')).toBeInTheDocument();
	});

	it('loads more patients page by page', async () => {
		const many = Array.from({ length: 50 }, (_, i) => summary({ id: 100 + i, lastName: `Patient ${i}` }));
		mockApi({
			'GET /api/patients?q=&limit=50&offset=0': () => json(200, { items: many, total: 51 }),
			'GET /api/patients?q=&limit=50&offset=50': () => json(200, { items: [lina], total: 51 })
		});
		render(Page);
		await fireEvent.click(await screen.findByRole('button', { name: 'Afficher plus' }));
		expect(await screen.findByRole('link', { name: /Lina Zouari/ })).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Afficher plus' })).not.toBeInTheDocument();
	});

	it('adds a patient with a medical alert and opens the file', async () => {
		mockApi({
			'GET /api/patients?q=&limit=50&offset=0': () => json(200, { items: [], total: 0 }),
			'POST /api/patients': () => json(201, patientFile({ id: 77, firstName: 'Amel', lastName: 'Gharbi' }))
		});
		render(Page);
		expect(await screen.findByText('Aucun patient pour le moment.')).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Importer depuis Excel' })).toHaveAttribute('href', '/app/import');
		await fireEvent.click(screen.getByRole('button', { name: 'Nouveau patient' }));
		const dialog = within(screen.getByRole('dialog', { name: 'Nouveau patient' }));
		await fireEvent.input(dialog.getByLabelText('Prénom'), { target: { value: 'Amel' } });
		await fireEvent.input(dialog.getByLabelText('Nom'), { target: { value: 'Gharbi' } });
		await fireEvent.input(dialog.getByLabelText('Téléphone'), { target: { value: '20 555 666' } });
		await fireEvent.input(dialog.getByLabelText('Année de naissance'), { target: { value: '1990' } });
		await fireEvent.click(dialog.getByLabelText('العربية'));
		await fireEvent.input(dialog.getByLabelText('Alerte médicale (allergie, anticoagulant…)'), { target: { value: 'Diabète' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer' }));
		await vi.waitFor(() => expect(deps.goto).toHaveBeenCalledWith('/app/patients/77'));
		expect(sentJson('POST /api/patients')).toEqual({
			firstName: 'Amel',
			lastName: 'Gharbi',
			phone: '20 555 666',
			birthYear: 1990,
			birthDate: null,
			lang: 'ar',
			reminderConsent: false,
			notes: '',
			alerts: 'Diabète'
		});
	});

	it('explains a wrong phone number and a loading problem', async () => {
		mockApi({
			'GET /api/patients?q=&limit=50&offset=0': () => problem(500, 'server_error'),
			'POST /api/patients': () => problem(422, 'invalid_phone')
		});
		render(Page);
		expect(await screen.findByRole('alert')).toHaveTextContent('La liste des patients n’a pas pu être chargée.');
		await fireEvent.click(screen.getByRole('button', { name: 'Nouveau patient' }));
		const dialog = within(screen.getByRole('dialog'));
		await fireEvent.input(dialog.getByLabelText('Prénom'), { target: { value: 'A' } });
		await fireEvent.input(dialog.getByLabelText('Nom'), { target: { value: 'B' } });
		await fireEvent.input(dialog.getByLabelText('Téléphone'), { target: { value: '1' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer' }));
		expect(await dialog.findByRole('alert')).toHaveTextContent('Numéro de téléphone invalide.');
		expect(calls()).toContain('POST /api/patients');
	});

	it('is translated into Arabic', async () => {
		i18n.setLocale('ar');
		mockApi({ 'GET /api/patients?q=&limit=50&offset=0': () => json(200, { items: [sami], total: 1 }) });
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'المرضى' })).toBeInTheDocument();
		expect(await screen.findByText('1 مريض')).toBeInTheDocument();
	});
});
