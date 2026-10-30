import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Cabinet from './+page.svelte';
import Compte from './compte/+page.svelte';
import ReglagesNav from '../../../lib/components/reglages/ReglagesNav.svelte';
import { deps } from '#lib/api';
import { auth } from '#lib/auth.svelte';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, mockApi, noContent, problem, sentJson } from '#lib/test-utils';
import { assistant, owner, practice } from '#lib/testing/fixtures';

describe('settings navigation', () => {
	beforeEach(() => {
		i18n.setLocale('fr');
		auth.clear();
	});

	it('gives the owner every section and links to subscription, import and installation', () => {
		auth.set('tok', owner);
		render(ReglagesNav, { props: { path: '/app/reglages/equipe' } });
		const nav = within(screen.getByRole('navigation', { name: 'Rubriques des réglages' }));
		expect(nav.getAllByRole('link').map((a) => a.getAttribute('href'))).toEqual([
			'/app/reglages',
			'/app/reglages/horaires',
			'/app/reglages/actes',
			'/app/reglages/praticiens',
			'/app/reglages/equipe',
			'/app/reglages/reservation',
			'/app/reglages/ecran',
			'/app/reglages/donnees',
			'/app/reglages/compte',
			'/app/abonnement',
			'/app/import',
			'/app/installer'
		]);
		expect(nav.getByRole('link', { name: 'Équipe' })).toHaveAttribute('aria-current', 'page');
	});

	it('gives other roles their account, the import (assistant) and the installation', () => {
		auth.set('tok', assistant);
		render(ReglagesNav, { props: { path: '/app/reglages' } });
		const nav = within(screen.getByRole('navigation', { name: 'Rubriques des réglages' }));
		expect(nav.getAllByRole('link').map((a) => a.getAttribute('href'))).toEqual(['/app/reglages', '/app/import', '/app/installer']);
		expect(nav.getByRole('link', { name: 'Mon compte' })).toHaveAttribute('aria-current', 'page');
	});
});

describe('/app/reglages – practice data (owner)', () => {
	beforeEach(() => {
		i18n.setLocale('fr');
		auth.set('tok', owner);
	});

	it('loads the practice and saves only the changed fields, then refreshes the account', async () => {
		mockApi({
			'GET /api/practice': () => json(200, practice()),
			'PATCH /api/practice': () => json(200, practice({ name: 'Cabinet du Lac – Dr Ben Salah', slotMinutes: 20 })),
			'GET /api/auth/me': () => json(200, { ...owner, practice: { ...owner.practice!, name: 'Cabinet du Lac – Dr Ben Salah' } })
		});
		render(Cabinet);
		expect(await screen.findByLabelText('Nom du cabinet')).toHaveValue('Cabinet du Lac');
		expect(screen.getByText(`http://cabinet-lac.${location.host}/`)).toBeInTheDocument();
		await fireEvent.input(screen.getByLabelText('Nom du cabinet'), { target: { value: 'Cabinet du Lac – Dr Ben Salah' } });
		await fireEvent.change(screen.getByLabelText('Pas de l’agenda'), { target: { value: '20' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
		expect(await screen.findByText('Modifications enregistrées.')).toBeInTheDocument();
		expect(sentJson('PATCH /api/practice')).toEqual({ name: 'Cabinet du Lac – Dr Ben Salah', slotMinutes: 20 });
		await vi.waitFor(() => expect(auth.user?.practice?.name).toBe('Cabinet du Lac – Dr Ben Salah'));
	});

	it('shows field errors and sends nothing', async () => {
		mockApi({ 'GET /api/practice': () => json(200, practice()) });
		render(Cabinet);
		await fireEvent.input(await screen.findByLabelText('Nom du cabinet'), { target: { value: ' ' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
		expect(screen.getByLabelText('Nom du cabinet')).toHaveAccessibleDescription(/Ce champ est obligatoire\./);
		expect(calls()).toEqual(['GET /api/practice']);
	});

	it('shows the account instead of the practice to other roles', async () => {
		auth.set('tok', assistant);
		mockApi({});
		render(Cabinet);
		expect(screen.getByRole('heading', { name: 'Mon compte' })).toBeInTheDocument();
		expect(calls()).toEqual([]);
	});
});

describe('/app/reglages/compte', () => {
	beforeEach(() => {
		i18n.setLocale('fr');
		auth.set('tok', assistant);
	});

	it('renames the account', async () => {
		mockApi({ 'PATCH /api/auth/me': () => json(200, { ...assistant, name: 'Salma Gharbi' }) });
		render(Compte);
		expect(screen.getByText('salma@cabinet.tn')).toBeInTheDocument();
		await fireEvent.input(screen.getByLabelText('Nom affiché'), { target: { value: 'Salma Gharbi' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le nom' }));
		expect(await screen.findByText('Nom enregistré.')).toBeInTheDocument();
		expect(sentJson('PATCH /api/auth/me')).toEqual({ name: 'Salma Gharbi' });
		expect(auth.user?.name).toBe('Salma Gharbi');
	});

	it('changes the password and keeps this device signed in', async () => {
		mockApi({ 'POST /api/auth/password': () => json(200, { token: 'new-token' }) });
		render(Compte);
		await fireEvent.input(screen.getByLabelText('Mot de passe actuel'), { target: { value: 'ancien-mot-de-passe' } });
		await fireEvent.input(screen.getByLabelText('Nouveau mot de passe'), { target: { value: 'court' } });
		await fireEvent.input(screen.getByLabelText('Confirmer le nouveau mot de passe'), { target: { value: 'court' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Changer le mot de passe' }));
		expect(screen.getByLabelText('Nouveau mot de passe')).toHaveAccessibleDescription(/doit contenir au moins 10 caractères/);
		await fireEvent.input(screen.getByLabelText('Nouveau mot de passe'), { target: { value: 'nouveau-mot-de-passe' } });
		await fireEvent.input(screen.getByLabelText('Confirmer le nouveau mot de passe'), { target: { value: 'autre-mot-de-passe' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Changer le mot de passe' }));
		expect(screen.getByLabelText('Confirmer le nouveau mot de passe')).toHaveAccessibleDescription('Les deux mots de passe ne sont pas identiques.');
		await fireEvent.input(screen.getByLabelText('Confirmer le nouveau mot de passe'), { target: { value: 'nouveau-mot-de-passe' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Changer le mot de passe' }));
		expect(await screen.findByText(/Mot de passe changé/)).toBeInTheDocument();
		expect(sentJson('POST /api/auth/password')).toEqual({ current: 'ancien-mot-de-passe', next: 'nouveau-mot-de-passe' });
		expect(auth.token).toBe('new-token');
		expect(screen.getByLabelText('Mot de passe actuel')).toHaveValue('');
	});

	it('explains a wrong current password at the field', async () => {
		mockApi({ 'POST /api/auth/password': () => problem(400, 'wrong_password') });
		render(Compte);
		await fireEvent.input(screen.getByLabelText('Mot de passe actuel'), { target: { value: 'faux' } });
		await fireEvent.input(screen.getByLabelText('Nouveau mot de passe'), { target: { value: 'nouveau-mot-de-passe' } });
		await fireEvent.input(screen.getByLabelText('Confirmer le nouveau mot de passe'), { target: { value: 'nouveau-mot-de-passe' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Changer le mot de passe' }));
		await vi.waitFor(() =>
			expect(screen.getByLabelText('Mot de passe actuel')).toHaveAccessibleDescription('Le mot de passe actuel est incorrect.')
		);
	});

	it('switches the language and saves it on the account', async () => {
		mockApi({ 'PATCH /api/auth/me': () => json(200, { ...assistant, lang: 'ar' }) });
		render(Compte);
		await fireEvent.click(screen.getByRole('button', { name: 'العربية' }));
		await vi.waitFor(() => expect(sentJson('PATCH /api/auth/me')).toEqual({ lang: 'ar' }));
		expect(i18n.locale).toBe('ar');
	});

	it('signs out everywhere after confirmation', async () => {
		mockApi({ 'POST /api/auth/logout-all': () => noContent() });
		render(Compte);
		await fireEvent.click(screen.getByRole('button', { name: 'Se déconnecter partout' }));
		const dialog = screen.getByRole('dialog', { name: 'Se déconnecter de tous les appareils ?' });
		await fireEvent.click(within(dialog).getByRole('button', { name: 'Se déconnecter partout' }));
		await vi.waitFor(() => expect(deps.goto).toHaveBeenCalledWith('/connexion'));
		expect(auth.token).toBeNull();
	});
});
