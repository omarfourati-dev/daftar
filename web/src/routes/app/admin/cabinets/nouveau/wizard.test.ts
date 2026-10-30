import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, mockApi, problem, sentJson } from '#lib/test-utils';

const next = () => fireEvent.click(screen.getByRole('button', { name: 'Suivant' }));
const input = (label: string | RegExp, value: string) => fireEvent.input(screen.getByLabelText(label), { target: { value } });
const pick = (label: string | RegExp, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });

function slugApi(taken: string[] = []) {
	return (_: RequestInit | undefined, url: string) => {
		const slug = new URL(url, 'http://x').searchParams.get('slug') ?? '';
		return json(200, taken.includes(slug) ? { available: false, reason: 'taken' } : { available: true });
	};
}

async function fillIdentity() {
	await pick('Spécialité', 'dentiste');
	await input('Nom du cabinet', 'Cabinet du Lac');
	await input(/^Nom en arabe/, 'عيادة البحيرة');
	await input('Personne responsable', 'Dr Amira Ben Salah');
	await input('Téléphone du cabinet', '20 123 456');
}

describe('/app/admin/cabinets/nouveau – wizard', () => {
	beforeEach(() => {
		i18n.setLocale('fr');
		sessionStorage.clear();
	});

	it('creates a practice in six steps and hands out the invitation and booking links', async () => {
		const api = mockApi({
			'/api/admin/slug-available?slug=cabinet-du-lac': slugApi(),
			'/api/admin/slug-available?slug=cabinet-lac': slugApi(['cabinet-lac']),
			'/api/admin/slug-available?slug=cabinet-lac-tunis': slugApi(),
			'POST /api/admin/practices': () =>
				json(201, { practice: { id: 42, slug: 'cabinet-lac-tunis', name: 'Cabinet du Lac' }, invitation: { token: 'tok-123', expiresAt: '2026-11-06T09:00:00+01:00' } })
		});
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'Nouveau cabinet' })).toBeInTheDocument();
		expect(screen.getByRole('heading', { level: 2, name: 'Cabinet & contact' })).toBeInTheDocument();
		expect(screen.getByText('Étape 1 sur 7')).toBeInTheDocument();

		// 1 – required fields are checked at the field
		await next();
		expect(screen.getByRole('alert')).toHaveTextContent('Corrigez les champs signalés pour continuer.');
		expect(screen.getByLabelText('Nom du cabinet')).toHaveAttribute('aria-invalid', 'true');
		expect(screen.getByLabelText('Nom du cabinet')).toHaveAccessibleDescription(/Ce champ est obligatoire\./);
		expect(screen.getByLabelText('Nom du cabinet')).toHaveFocus();
		await fillIdentity();
		await input(/^E-mail/, 'amira@');
		await next();
		expect(screen.getByLabelText(/^E-mail/)).toHaveAccessibleDescription('Adresse e-mail invalide.');
		await input(/^E-mail/, 'amira@cabinet.tn');
		await next();

		// 2 – address and a sub-domain checked live
		expect(screen.getByRole('heading', { level: 2, name: 'Adresse & sous-domaine' })).toBeInTheDocument();
		const slug = screen.getByLabelText('Sous-domaine');
		expect(slug).toHaveValue('cabinet-du-lac');
		expect(await screen.findByText(`Disponible : http://cabinet-du-lac.${location.host}/`)).toBeInTheDocument();
		await input('Sous-domaine', 'ab');
		expect(await screen.findByText(/3 à 40 caractères/)).toBeInTheDocument();
		await input('Sous-domaine', 'admin');
		expect(await screen.findByText('Ce nom est réservé. Choisissez-en un autre.')).toBeInTheDocument();
		await input('Sous-domaine', 'cabinet-lac');
		expect(await screen.findByText('Déjà utilisé par un autre cabinet.')).toBeInTheDocument();
		await next();
		expect(screen.getByRole('heading', { level: 2, name: 'Adresse & sous-domaine' })).toBeInTheDocument(); // blocked
		await input('Sous-domaine', 'cabinet-lac-tunis');
		expect(await screen.findByText(`Disponible : http://cabinet-lac-tunis.${location.host}/`)).toBeInTheDocument();
		expect(calls().filter((c) => c.includes('slug=ab') || c.includes('slug=admin'))).toEqual([]); // checked locally
		await input('Adresse', '12 rue du Lac Léman');
		await input('Ville', 'Les Berges du Lac');
		await pick('Gouvernorat', 'tunis');
		await next();

		// 3 – hours (defaults are fine)
		expect(screen.getByRole('heading', { level: 2, name: 'Horaires' })).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('checkbox', { name: 'Samedi' }));
		await next();

		// 4 – practitioners, the first one taken from the contact
		expect(screen.getByRole('heading', { level: 2, name: 'Praticiens' })).toBeInTheDocument();
		expect(screen.getByLabelText('Nom 1')).toHaveValue('Amira Ben Salah');
		expect(screen.getByLabelText('Titre 1')).toHaveValue('Dr.');
		await fireEvent.click(screen.getByRole('button', { name: 'Ajouter un praticien' }));
		await input('Nom 2', 'Karim Trabelsi');
		await next();

		// 5 – catalog of the specialty, prices optional
		expect(screen.getByRole('heading', { level: 2, name: 'Actes & tarifs' })).toBeInTheDocument();
		expect(screen.getByText(/Catalogue proposé pour « Dentiste »/)).toBeInTheDocument();
		expect(screen.getByLabelText('Acte (français) 3')).toHaveValue('Détartrage');
		await input('Prix (DT) 1', '40');
		await input('Prix (DT) 2', 'quarante');
		await next();
		expect(screen.getByLabelText('Prix (DT) 2')).toHaveAccessibleDescription('Montant invalide. Exemple : 35 ou 35,500.');
		await input('Prix (DT) 2', '25,5');
		await next();

		// 6 – online booking
		expect(screen.getByRole('heading', { level: 2, name: 'Réservation en ligne' })).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('checkbox', { name: 'Réservation en ligne activée' }));
		await input('Réservable jusqu’à … jours à l’avance', '14');
		await next();

		// summary
		expect(screen.getByRole('heading', { level: 2, name: 'Récapitulatif' })).toBeInTheDocument();
		expect(screen.getByText('5 jour(s) d’ouverture')).toBeInTheDocument();
		expect(screen.getByText('2 praticien(s)')).toBeInTheDocument();
		expect(screen.getByText('9 acte(s), dont 3 en ligne')).toBeInTheDocument();
		expect(screen.getByText('Activée – 14 jours à l’avance, délai 2 h')).toBeInTheDocument();
		await input(/^Notes internes/, 'Rencontré au congrès de Sousse');
		await fireEvent.click(screen.getByRole('button', { name: 'Créer le cabinet' }));

		expect(await screen.findByRole('heading', { name: 'Cabinet du Lac est créé' })).toBeInTheDocument();
		const body = sentJson('POST /api/admin/practices') as Record<string, unknown>;
		expect(body).toMatchObject({
			specialty: 'dentiste',
			name: 'Cabinet du Lac',
			nameAr: 'عيادة البحيرة',
			contactName: 'Dr Amira Ben Salah',
			phone: '20 123 456',
			whatsapp: null,
			email: 'amira@cabinet.tn',
			slug: 'cabinet-lac-tunis',
			address: '12 rue du Lac Léman',
			city: 'Les Berges du Lac',
			governorate: 'tunis',
			status: 'pilot',
			planCode: 'pilot',
			adminNotes: 'Rencontré au congrès de Sousse',
			practitioners: [
				{ title: 'Dr.', name: 'Amira Ben Salah', specialty: null },
				{ title: 'Dr.', name: 'Karim Trabelsi', specialty: null }
			],
			onlineBooking: { enabled: true, autoConfirm: false, horizonDays: 14, minNoticeHours: 2, maxPerDay: 20, blockNoShows: 2 }
		});
		const hours = body.weeklyHours as Record<string, string[][]>;
		expect(hours['1']).toEqual([
			['08:00', '12:30'],
			['14:00', '18:00']
		]);
		expect(hours['6']).toEqual([]);
		const services = body.services as { nameFr: string; priceMillimes: number | null; onlineBookable: boolean }[];
		expect(services).toHaveLength(9);
		expect(services[0]).toEqual({ nameFr: 'Consultation', nameAr: 'معاينة', durationMin: 30, priceMillimes: 40000, onlineBookable: true });
		expect(services[1].priceMillimes).toBe(25500);
		expect(services[2].priceMillimes).toBeNull();

		expect(screen.getByRole('textbox', { name: 'Lien d’invitation du titulaire' })).toHaveValue(
			`http://cabinet-lac-tunis.${location.host}/invitation#tok-123`
		);
		expect(screen.getByRole('textbox', { name: 'Page de réservation des patients' })).toHaveValue(`http://cabinet-lac-tunis.${location.host}/`);
		const whatsapp = screen.getAllByRole('link', { name: 'Envoyer par WhatsApp' })[0];
		expect(whatsapp.getAttribute('href')).toMatch(/^https:\/\/wa\.me\/21620123456\?text=Bonjour%20Dr%20Amira%20Ben%20Salah/);
		expect(screen.getByRole('link', { name: 'Ouvrir la fiche du cabinet' })).toHaveAttribute('href', '/app/admin/cabinets/42');
		expect(api).toHaveBeenCalled();
	});

	it('goes back to the sub-domain when it was taken in the meantime', async () => {
		mockApi({
			'/api/admin/slug-available?slug=cabinet-du-lac': slugApi(),
			'POST /api/admin/practices': () => problem(409, 'slug_taken', 'Ce sous-domaine est déjà utilisé.')
		});
		render(Page);
		await fillIdentity();
		await next();
		await screen.findByText(/^Disponible/);
		await input('Adresse', '12 rue du Lac');
		await input('Ville', 'Tunis');
		await pick('Gouvernorat', 'tunis');
		for (let i = 0; i < 5; i++) await next();
		await fireEvent.click(screen.getByRole('button', { name: 'Créer le cabinet' }));
		expect(await screen.findByRole('heading', { level: 2, name: 'Adresse & sous-domaine' })).toBeInTheDocument();
		expect(screen.getByText('Déjà utilisé par un autre cabinet.')).toBeInTheDocument();
	});

	it('refills the catalog when the specialty changes before the services were edited', async () => {
		mockApi({ '/api/admin/slug-available?slug=cabinet-du-lac': slugApi() });
		render(Page);
		await fillIdentity();
		await next();
		await screen.findByText(/^Disponible/);
		await input('Adresse', '12 rue du Lac');
		await input('Ville', 'Tunis');
		await pick('Gouvernorat', 'tunis');
		for (let i = 0; i < 3; i++) await next();
		expect(screen.getByLabelText('Acte (français) 3')).toHaveValue('Détartrage');
		// back to step 1 through the step list
		await fireEvent.click(within(screen.getByRole('list', { name: 'Étapes' })).getByRole('button', { name: /Cabinet & contact/ }));
		await pick('Spécialité', 'kinesitherapeute');
		await fireEvent.click(within(screen.getByRole('list', { name: 'Étapes' })).getByRole('button', { name: /Actes & tarifs/ }));
		expect(screen.getByLabelText('Acte (français) 1')).toHaveValue('Séance');
		expect(screen.queryByLabelText('Acte (français) 3')).not.toBeInTheDocument();
	});

	it('starts from a pilot request', async () => {
		sessionStorage.setItem(
			'daftar.wizardPrefill',
			JSON.stringify({ name: 'Dr Sami Gharbi', practice: 'Cabinet Gharbi', city: 'Sfax', phone: '+21698111222', email: 'sami@gharbi.tn' })
		);
		mockApi({});
		render(Page);
		expect(screen.getByText('Pré-rempli depuis la demande pilote de Dr Sami Gharbi.')).toBeInTheDocument();
		expect(screen.getByLabelText('Nom du cabinet')).toHaveValue('Cabinet Gharbi');
		expect(screen.getByLabelText('Personne responsable')).toHaveValue('Dr Sami Gharbi');
		expect(screen.getByLabelText('Téléphone du cabinet')).toHaveValue('+21698111222');
		await vi.waitFor(() => expect(sessionStorage.getItem('daftar.wizardPrefill')).toBeNull());
	});
});
