import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { deps } from '#lib/api';
import { defaultWeeklyHours } from '#lib/hours';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, mockApi, noContent, problem, sentJson } from '#lib/test-utils';
import type { AdminPractice } from '#lib/types/admin';

const practice: AdminPractice = {
	id: 7,
	name: 'Cabinet du Lac',
	nameAr: 'عيادة البحيرة',
	slug: 'cabinet-lac',
	specialty: 'dentiste',
	contactName: 'Dr Amira Ben Salah',
	phone: '+21671123456',
	whatsapp: '+21620123456',
	email: 'amira@cabinet.tn',
	address: '12 rue du Lac Léman',
	postalCode: '1053',
	city: 'Les Berges du Lac',
	governorate: 'tunis',
	mapsUrl: '',
	descriptionFr: '',
	descriptionAr: '',
	taxId: '',
	brandColor: '#0f766e',
	status: 'pilot',
	planCode: 'pilot',
	paidUntil: '2026-12-31',
	adminNotes: 'Pilote depuis octobre',
	weeklyHours: defaultWeeklyHours(),
	isDemo: false,
	createdAt: '2026-10-01T10:00:00+01:00',
	onlineBooking: { enabled: true, autoConfirm: false, horizonDays: 30, minNoticeHours: 2, maxPerDay: 20, blockNoShows: 2 }
};

const render7 = () => render(Page, { props: { data: { id: 7 } } });

describe('/app/admin/cabinets/[id]', () => {
	beforeEach(() => i18n.setLocale('fr'));

	it('shows the practice and saves only what changed', async () => {
		mockApi({
			'GET /api/admin/practices/7': () => json(200, practice),
			'PATCH /api/admin/practices/7': () => json(200, { ...practice, status: 'active', planCode: 'cabinet_mensuel', adminNotes: 'Payé par virement' })
		});
		render7();
		expect(await screen.findByRole('heading', { level: 1, name: 'Cabinet du Lac' })).toBeInTheDocument();
		expect(screen.getByLabelText('Statut')).toHaveValue('pilot');
		expect(screen.getByLabelText('Nom du cabinet')).toHaveValue('Cabinet du Lac');
		expect(screen.getByLabelText('Sous-domaine')).toHaveValue('cabinet-lac');
		await fireEvent.change(screen.getByLabelText('Statut'), { target: { value: 'active' } });
		await fireEvent.change(screen.getByLabelText('Formule'), { target: { value: 'cabinet_mensuel' } });
		await fireEvent.input(screen.getByLabelText(/^Notes internes/), { target: { value: 'Payé par virement' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer les modifications' }));
		expect(await screen.findByText('Modifications enregistrées.')).toBeInTheDocument();
		expect(sentJson('PATCH /api/admin/practices/7')).toEqual({ status: 'active', planCode: 'cabinet_mensuel', adminNotes: 'Payé par virement' });
	});

	it('says when there is nothing to save', async () => {
		mockApi({ 'GET /api/admin/practices/7': () => json(200, practice) });
		render7();
		await fireEvent.click(await screen.findByRole('button', { name: 'Enregistrer les modifications' }));
		expect(await screen.findByText('Aucune modification à enregistrer.')).toBeInTheDocument();
		expect(calls()).toEqual(['GET /api/admin/practices/7']);
	});

	it('checks a new sub-domain and warns about old links', async () => {
		mockApi({
			'GET /api/admin/practices/7': () => json(200, practice),
			'GET /api/admin/slug-available?slug=lac-tunis': () => json(200, { available: true }),
			'PATCH /api/admin/practices/7': () => json(200, { ...practice, slug: 'lac-tunis' })
		});
		render7();
		await fireEvent.input(await screen.findByLabelText('Sous-domaine'), { target: { value: 'lac-tunis' } });
		expect(screen.getByText(/Changer le sous-domaine casse les anciens liens/)).toBeInTheDocument();
		expect(await screen.findByText(`Disponible : http://lac-tunis.${location.host}/`)).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer les modifications' }));
		await vi.waitFor(() => expect(sentJson('PATCH /api/admin/practices/7')).toEqual({ slug: 'lac-tunis' }));
	});

	it('validates fields before saving', async () => {
		mockApi({ 'GET /api/admin/practices/7': () => json(200, practice) });
		render7();
		await fireEvent.input(await screen.findByLabelText('Téléphone du cabinet'), { target: { value: '12' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer les modifications' }));
		expect(screen.getByLabelText('Téléphone du cabinet')).toHaveAccessibleDescription(/Numéro invalide/);
		expect(calls()).toEqual(['GET /api/admin/practices/7']);
	});

	it('creates a new invitation link and an owner reset link', async () => {
		mockApi({
			'GET /api/admin/practices/7': () => json(200, practice),
			'POST /api/admin/practices/7/invitation': () => json(201, { token: 'inv-1', expiresAt: '2026-11-06T09:00:00+01:00' }),
			'POST /api/admin/practices/7/owner-reset-link': () => json(201, { token: 'reset-1', expiresAt: '2026-10-31T09:00:00+01:00' })
		});
		render7();
		await fireEvent.click(await screen.findByRole('button', { name: 'Créer un lien d’invitation' }));
		expect(await screen.findByRole('textbox', { name: 'Lien d’invitation du titulaire' })).toHaveValue(
			`http://cabinet-lac.${location.host}/invitation#inv-1`
		);
		await fireEvent.click(screen.getByRole('button', { name: 'Créer un lien de réinitialisation' }));
		expect(await screen.findByRole('textbox', { name: 'Lien de réinitialisation' })).toHaveValue(`http://cabinet-lac.${location.host}/reinitialiser#reset-1`);
		expect(screen.getByText('Valable jusqu’au 31/10/2026 09:00.')).toBeInTheDocument();
	});

	it('explains that a practice without owner needs an invitation first', async () => {
		mockApi({
			'GET /api/admin/practices/7': () => json(200, practice),
			'POST /api/admin/practices/7/owner-reset-link': () => problem(404, 'not_found')
		});
		render7();
		await fireEvent.click(await screen.findByRole('button', { name: 'Créer un lien de réinitialisation' }));
		expect(await screen.findByText('Ce cabinet n’a pas encore de titulaire : envoyez d’abord une invitation.')).toBeInTheDocument();
	});

	it('deletes the practice after typing its name', async () => {
		mockApi({ 'GET /api/admin/practices/7': () => json(200, practice), 'DELETE /api/admin/practices/7': () => noContent() });
		render7();
		await fireEvent.click(await screen.findByRole('button', { name: 'Supprimer ce cabinet…' }));
		const dialog = screen.getByRole('dialog', { name: 'Supprimer Cabinet du Lac ?' });
		await fireEvent.input(within(dialog).getByLabelText('Tapez « Cabinet du Lac » pour confirmer'), { target: { value: 'Cabinet du Lac' } });
		await fireEvent.click(within(dialog).getByRole('button', { name: 'Supprimer définitivement' }));
		await vi.waitFor(() => expect(deps.goto).toHaveBeenCalledWith('/app/admin'));
		expect(calls()).toContain('DELETE /api/admin/practices/7');
	});

	it('says when the practice does not exist', async () => {
		mockApi({ 'GET /api/admin/practices/7': () => problem(404, 'not_found') });
		render7();
		expect(await screen.findByRole('alert')).toHaveTextContent('Ce cabinet n’existe pas ou a été supprimé.');
	});
});
