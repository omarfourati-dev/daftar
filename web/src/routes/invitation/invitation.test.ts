import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { deps } from '#lib/api';
import { auth } from '#lib/auth.svelte';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, mockApi, problem, sentJson } from '#lib/test-utils';

const session = {
	token: 'jeton-assistante',
	user: {
		id: 9,
		email: 'salma@cabinet.tn',
		name: 'Salma',
		role: 'assistant',
		lang: 'fr',
		practice: { id: 1, name: 'Cabinet du Lac', slug: 'cabinet-lac', specialty: 'generaliste', status: 'pilot', brandColor: '#0f766e', isDemo: false, demoExpiresAt: null }
	}
};

async function fillForm(password: string, repeat: string) {
	await fireEvent.input(await screen.findByLabelText('Votre nom'), { target: { value: 'Salma' } });
	await fireEvent.input(screen.getByLabelText('E-mail'), { target: { value: 'salma@cabinet.tn' } });
	await fireEvent.input(screen.getByLabelText('Mot de passe'), { target: { value: password } });
	await fireEvent.input(screen.getByLabelText('Répéter le mot de passe'), { target: { value: repeat } });
	await fireEvent.click(screen.getByRole('button', { name: 'Créer mon compte' }));
}

describe('/invitation', () => {
	beforeEach(() => {
		auth.clear();
		i18n.setLocale('fr');
		history.replaceState(null, '', '/invitation#jeton-de-l-invitation');
	});

	it('shows practice and role, creates the account in it and opens the app', async () => {
		mockApi({
			'POST /api/invitations/preview': () => json(200, { practiceName: 'Cabinet du Lac', role: 'assistant' }),
			'POST /api/invitations/accept': () => json(201, session)
		});
		render(Page);
		expect(await screen.findByText('Vous êtes invité(e) à rejoindre Cabinet du Lac en tant que Assistant(e).')).toBeInTheDocument();
		await fillForm('mot-de-passe-salma', 'mot-de-passe-salma');
		await vi.waitFor(() => expect(auth.token).toBe('jeton-assistante'));
		expect(sentJson('POST /api/invitations/preview')).toEqual({ token: 'jeton-de-l-invitation' });
		expect(sentJson('POST /api/invitations/accept')).toEqual({
			token: 'jeton-de-l-invitation',
			name: 'Salma',
			email: 'salma@cabinet.tn',
			password: 'mot-de-passe-salma',
			lang: 'fr'
		});
		expect(auth.user?.practice?.name).toBe('Cabinet du Lac');
		expect(deps.goto).toHaveBeenCalledWith('/app');
		expect(location.hash).toBe(''); // the used link leaves the address bar
	});

	it('checks the repetition before sending anything', async () => {
		mockApi({ 'POST /api/invitations/preview': () => json(200, { practiceName: 'Cabinet du Lac', role: 'dentist' }) });
		render(Page);
		await fillForm('mot-de-passe-salma', 'autre-mot-de-passe');
		expect(await screen.findByRole('alert')).toHaveTextContent('Les deux mots de passe ne sont pas identiques.');
		expect(calls()).toEqual(['POST /api/invitations/preview']);
	});

	it('checks the length before sending anything', async () => {
		mockApi({ 'POST /api/invitations/preview': () => json(200, { practiceName: 'Cabinet du Lac', role: 'dentist' }) });
		render(Page);
		await fillForm('court', 'court');
		expect(await screen.findByRole('alert')).toHaveTextContent('au moins 10 caractères');
		expect(calls()).toEqual(['POST /api/invitations/preview']);
	});

	it('explains an invalid, expired or used link', async () => {
		mockApi({ 'POST /api/invitations/preview': () => problem(404, 'invitation_invalid') });
		render(Page);
		expect(await screen.findByRole('alert')).toHaveTextContent('Cette invitation n’est pas valide, a expiré ou a déjà été utilisée.');
		expect(screen.queryByLabelText('Mot de passe')).not.toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Aller à la connexion' })).toHaveAttribute('href', '/connexion');
	});

	it('does not ask the server when the token is missing', async () => {
		history.replaceState(null, '', '/invitation');
		const fetch = mockApi({});
		render(Page);
		expect(await screen.findByRole('alert')).toHaveTextContent('Ce lien est incomplet.');
		expect(fetch).not.toHaveBeenCalled();
	});

	it('shows why accepting failed, e.g. a taken e-mail', async () => {
		mockApi({
			'POST /api/invitations/preview': () => json(200, { practiceName: 'Cabinet du Lac', role: 'owner' }),
			'POST /api/invitations/accept': () => problem(409, 'email_taken')
		});
		render(Page);
		await fillForm('mot-de-passe-salma', 'mot-de-passe-salma');
		expect(await screen.findByRole('alert')).toHaveTextContent('Un compte existe déjà avec cette adresse e-mail.');
		expect(auth.token).toBeNull();
		expect(deps.goto).not.toHaveBeenCalled();
	});

	it('works in Arabic', async () => {
		i18n.setLocale('ar');
		mockApi({ 'POST /api/invitations/preview': () => json(200, { practiceName: 'Cabinet du Lac', role: 'dentist' }) });
		render(Page);
		expect(await screen.findByText('أنتم مدعوون للانضمام إلى Cabinet du Lac بصفة طبيب(ة).')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'إنشاء حسابي' })).toBeInTheDocument();
	});
});
