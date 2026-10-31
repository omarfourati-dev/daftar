import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { ApiError, apiErrorMessage } from '#lib/api';
import { auth } from '#lib/auth.svelte';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, mockApi, noContent, problem, sentJson } from '#lib/test-utils';
import { assistant, dentist, owner } from '#lib/testing/fixtures';
import type { ImportJob, ImportPreview } from '#lib/types/imports';

const job: ImportJob = {
	id: '7c1e4f9a-0000-4000-8000-000000000001',
	filename: 'patients.xlsx',
	sheets: ['Patients', 'Archives'],
	sheet: 'Patients',
	headerRow: 1,
	columns: [
		{ index: 0, header: 'Nom', samples: ['Ben Salah', 'Trabelsi', 'Gharbi'] },
		{ index: 1, header: 'Prénom', samples: ['Amira', 'Karim', 'Sami'] },
		{ index: 2, header: 'GSM', samples: ['20123456', '98111222', '55222333'] },
		{ index: 3, header: 'Naissance', samples: ['12/03/1980', '01/01/1975', ''] }
	],
	rowCount: 412,
	suggestedMapping: { lastName: 0, firstName: 1, fullName: null, phone: 2, birthDate: 3, date: 3, time: null }
};
const preview: ImportPreview = {
	willCreate: 398,
	willUpdate: 0,
	willSkip: 9,
	willCreatePatients: 0,
	errorCount: 5,
	errors: [{ row: 14, field: 'phone', message: 'Numéro de téléphone invalide.', value: '2012' }],
	duplicates: [{ row: 20, patientId: 77, name: 'Amira Ben Salah' }],
	conflicts: [],
	sample: [{ lastName: 'Ben Salah', firstName: 'Amira', phone: '+21620123456', birthYear: 1980 }]
};
const URL_JOB = `/api/imports/${job.id}`;

function chooseFile(name = 'patients.xlsx', size = 1000) {
	const file = new File(['x'.repeat(size)], name, { type: 'application/octet-stream' });
	return fireEvent.change(screen.getByLabelText('Choisir un fichier'), { target: { files: [file] } });
}

describe('/app/import – Excel/CSV import with own mapping (E5)', () => {
	beforeEach(() => {
		i18n.setLocale('fr');
		auth.set('tok', owner);
	});
	afterEach(() => vi.restoreAllMocks());

	it('goes file → sheet → mapping → check → import → report and template', async () => {
		const createObjectURL = vi.fn(() => 'blob:x');
		Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() });
		vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
		mockApi({
			'GET /api/import-templates': () => json(200, []),
			'POST /api/imports': (init) => {
				expect(init?.body).toBeInstanceOf(FormData);
				return json(201, job);
			},
			[`POST ${URL_JOB}/sheet`]: () => json(200, { ...job, headerRow: 2 }),
			[`POST ${URL_JOB}/preview`]: () => json(200, preview),
			[`POST ${URL_JOB}/commit`]: () => json(200, { created: 398, updated: 0, skipped: 9, errorCount: 5, patientsCreated: 0 }),
			[`GET ${URL_JOB}/report.csv`]: () => new Response('Ligne;Champ;Message;Valeur\n', { status: 200 }),
			'POST /api/import-templates': () => json(201, { id: 3, name: 'Ancien logiciel', kind: 'patients', mapping: {}, options: {} })
		});
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'Importer depuis Excel' })).toBeInTheDocument();
		expect(screen.getByRole('radio', { name: /Des patients/ })).toBeChecked();
		await chooseFile();
		// sheet and title row
		expect(await screen.findByText('patients.xlsx – 412 ligne(s)')).toBeInTheDocument();
		expect(screen.getByLabelText('Feuille du classeur')).toHaveValue('Patients');
		await fireEvent.click(screen.getByRole('checkbox', { name: 'La première ligne contient les titres des colonnes' }));
		await fireEvent.click(screen.getByRole('checkbox', { name: 'La première ligne contient les titres des colonnes' }));
		await fireEvent.input(screen.getByLabelText('Ligne des titres'), { target: { value: '2' } });
		await vi.waitFor(() => expect(sentJson(`POST ${URL_JOB}/sheet`)).toEqual({ sheet: 'Patients', headerRow: 2 }));
		await fireEvent.click(screen.getByRole('button', { name: 'Continuer' }));

		// mapping: suggestions pre-selected, samples shown
		expect(screen.getByLabelText('Nom')).toHaveValue('0');
		expect(screen.getByLabelText('Téléphone')).toHaveValue('2');
		expect(screen.getByLabelText('Date de naissance')).toHaveValue('3');
		expect(within(screen.getByLabelText('Téléphone').closest('li')!).getByText('20123456, 98111222, 55222333')).toBeInTheDocument();
		await fireEvent.change(screen.getByLabelText('Langue des patients si la colonne manque'), { target: { value: 'ar' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Vérifier le fichier' }));

		// check
		const body = sentJson(`POST ${URL_JOB}/preview`) as { kind: string; mapping: Record<string, number | null>; options: Record<string, unknown> };
		expect(body.kind).toBe('patients');
		expect(body.mapping).toMatchObject({ lastName: 0, firstName: 1, fullName: null, phone: 2, birthDate: 3, notes: null });
		expect(body.mapping).not.toHaveProperty('date'); // appointment fields never go with a patient import
		expect(body.options).toEqual({ nameOrder: 'last_first', dateFormat: 'dmy', defaultLang: 'ar', reminderConsent: false, duplicates: 'skip' });
		expect(await screen.findByText('398')).toBeInTheDocument();
		const errors = within(screen.getByRole('table', { name: 'Lignes à corriger' }));
		expect(errors.getByText('Numéro de téléphone invalide.')).toBeInTheDocument();
		expect(errors.getByText('2012')).toBeInTheDocument();
		expect(errors.getByText('Téléphone')).toBeInTheDocument();
		expect(screen.getByText('Ligne 20 : Amira Ben Salah')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Importer 398 ligne(s)' }));

		// result
		expect(await screen.findByRole('heading', { name: 'Import terminé' })).toBeInTheDocument();
		expect(screen.getByText('398 créé(s), 0 complété(s), 9 ignoré(s), 5 en erreur.')).toBeInTheDocument();
		expect(sentJson(`POST ${URL_JOB}/commit`)).toEqual(body);
		await fireEvent.click(screen.getByRole('button', { name: 'Télécharger le rapport (CSV)' }));
		await vi.waitFor(() => expect(calls()).toContain(`GET ${URL_JOB}/report.csv`));
		await fireEvent.input(screen.getByLabelText('Nom du modèle'), { target: { value: 'Ancien logiciel' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le modèle' }));
		expect(await screen.findByText('Modèle enregistré.')).toBeInTheDocument();
		expect(sentJson('POST /api/import-templates')).toEqual({ name: 'Ancien logiciel', kind: 'patients', mapping: body.mapping, options: body.options });
	});

	it('checks size and type before uploading', async () => {
		mockApi({ 'GET /api/import-templates': () => json(200, []) });
		render(Page);
		await chooseFile('photo.png');
		expect(screen.getByRole('alert')).toHaveTextContent('Format non reconnu.');
		await chooseFile('patients.csv', 2 * 1024 * 1024 + 1);
		expect(screen.getByRole('alert')).toHaveTextContent('Le fichier dépasse 2 Mo.');
		expect(calls()).toEqual(['GET /api/import-templates']);
	});

	it('explains a file the server cannot read', async () => {
		mockApi({ 'GET /api/import-templates': () => json(200, []), 'POST /api/imports': () => problem(422, 'unreadable_file') });
		render(Page);
		await chooseFile();
		expect(await screen.findByRole('alert')).toHaveTextContent('Le fichier n’a pas pu être lu.');
	});

	it('says which required columns are missing before checking', async () => {
		mockApi({ 'GET /api/import-templates': () => json(200, []), 'POST /api/imports': () => json(201, { ...job, suggestedMapping: {} }) });
		render(Page);
		await chooseFile();
		await fireEvent.click(await screen.findByRole('button', { name: 'Continuer' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Vérifier le fichier' }));
		expect(screen.getByText('Choisissez la colonne du nom complet, ou celles du nom et du prénom.')).toBeInTheDocument();
		expect(screen.getByText('Choisissez la colonne du téléphone.')).toBeInTheDocument();
		expect(calls().some((c) => c.endsWith('/preview'))).toBe(false);
	});

	it('imports appointments and applies a saved template', async () => {
		mockApi({
			'GET /api/import-templates': () =>
				json(200, [{ id: 4, name: 'Agenda papier', kind: 'appointments', mapping: { fullName: 0, datetime: 1 }, options: { dateFormat: 'ymd', nameOrder: 'first_last', defaultLang: 'fr', reminderConsent: false, duplicates: 'skip' } }]),
			'POST /api/imports': () => json(201, job),
			[`POST ${URL_JOB}/preview`]: () => json(200, { ...preview, willCreate: 12, willCreatePatients: 3, errors: [], duplicates: [], errorCount: 0 })
		});
		render(Page);
		await fireEvent.click(screen.getByRole('radio', { name: /Des rendez-vous/ }));
		await chooseFile();
		await fireEvent.click(await screen.findByRole('button', { name: 'Continuer' }));
		await fireEvent.change(screen.getByLabelText('Modèle enregistré'), { target: { value: '4' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Appliquer le modèle' }));
		expect(screen.getByText('Modèle « Agenda papier » appliqué.')).toBeInTheDocument();
		expect(screen.getByLabelText('Date et heure')).toHaveValue('1');
		await fireEvent.click(screen.getByRole('button', { name: 'Vérifier le fichier' }));
		const body = sentJson(`POST ${URL_JOB}/preview`) as { kind: string; mapping: Record<string, unknown>; options: Record<string, unknown> };
		expect(body.kind).toBe('appointments');
		expect(body.mapping).toMatchObject({ fullName: 0, datetime: 1, date: null, phone: null });
		expect(body.options).toMatchObject({ dateFormat: 'ymd', nameOrder: 'first_last' });
		expect(await screen.findByText('Aucune erreur trouvée.')).toBeInTheDocument();
		expect(screen.getByText('nouveaux patients')).toBeInTheDocument();
	});

	it('deletes a template', async () => {
		mockApi({
			'GET /api/import-templates': () => json(200, [{ id: 4, name: 'Mon modèle', kind: 'patients', mapping: {}, options: {} }]),
			'POST /api/imports': () => json(201, job),
			'DELETE /api/import-templates/4': () => noContent()
		});
		render(Page);
		await chooseFile();
		await fireEvent.click(await screen.findByRole('button', { name: 'Continuer' }));
		await fireEvent.change(screen.getByLabelText('Modèle enregistré'), { target: { value: '4' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Supprimer le modèle' }));
		expect(await screen.findByText('Modèle supprimé.')).toBeInTheDocument();
	});

	it('is open to the assistant, not to other practitioners', () => {
		auth.set('tok', dentist);
		mockApi({});
		const { unmount } = render(Page);
		expect(screen.getByText('L’import est réservé au titulaire du cabinet et à l’assistance.')).toBeInTheDocument();
		unmount();
		auth.set('tok', assistant);
		mockApi({ 'GET /api/import-templates': () => json(200, []) });
		render(Page);
		expect(screen.getByLabelText('Choisir un fichier')).toBeInTheDocument();
	});

	it('explains that the demo does not import files, instead of the form', () => {
		auth.set('tok', { ...owner, practice: { ...owner.practice!, isDemo: true } });
		mockApi({}); // not even the templates are asked for
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'Importer depuis Excel' })).toBeInTheDocument();
		expect(screen.getByText(/L’import de fichiers n’est pas disponible dans la démo/)).toBeInTheDocument();
		expect(screen.queryByLabelText('Choisir un fichier')).not.toBeInTheDocument();
		expect(calls()).toEqual([]);
	});

	it('translates the server refusal for a demo', () => {
		expect(apiErrorMessage(new ApiError(403, '', 'demo_import_disabled'))).toMatch(/pas disponible dans la démo/);
	});
});
