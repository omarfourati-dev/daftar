import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { deps } from '#lib/api';
import { auth } from '#lib/auth.svelte';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, mockApi, problem, sentJson } from '#lib/test-utils';
import { assistant } from '#lib/testing/fixtures';

describe('/reinitialiser#token – new password from a reset link (A3)', () => {
	beforeEach(() => {
		i18n.setLocale('fr');
		auth.clear();
		history.replaceState(null, '', '/reinitialiser#rst-1');
	});

	it('shows whose password it is, checks the new one and signs in', async () => {
		mockApi({
			'POST /api/password-reset/preview': () => json(200, { email: 'salma@cabinet.tn', practiceName: 'Cabinet du Lac' }),
			'POST /api/password-reset/accept': () => json(200, { token: 'tok', user: { ...assistant, lang: 'ar' } })
		});
		render(Page);
		expect(await screen.findByText('Choisissez un nouveau mot de passe pour salma@cabinet.tn (Cabinet du Lac).')).toBeInTheDocument();
		expect(sentJson('POST /api/password-reset/preview')).toEqual({ token: 'rst-1' });
		await fireEvent.input(screen.getByLabelText('Nouveau mot de passe'), { target: { value: 'court' } });
		await fireEvent.input(screen.getByLabelText('Répéter le mot de passe'), { target: { value: 'court' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le mot de passe' }));
		expect(screen.getByRole('alert')).toHaveTextContent('au moins 10 caractères');
		await fireEvent.input(screen.getByLabelText('Nouveau mot de passe'), { target: { value: 'nouveau-mot-de-passe' } });
		await fireEvent.input(screen.getByLabelText('Répéter le mot de passe'), { target: { value: 'nouveau-mot-de-passe' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le mot de passe' }));
		await vi.waitFor(() => expect(auth.token).toBe('tok'));
		expect(sentJson('POST /api/password-reset/accept')).toEqual({ token: 'rst-1', password: 'nouveau-mot-de-passe' });
		expect(i18n.locale).toBe('ar');
		expect(location.hash).toBe(''); // the used link leaves the address bar
		expect(deps.goto).toHaveBeenCalledWith('/app');
	});

	it('explains an invalid, expired or used link', async () => {
		mockApi({ 'POST /api/password-reset/preview': () => problem(404, 'reset_invalid') });
		render(Page);
		expect(await screen.findByRole('alert')).toHaveTextContent('Ce lien n’est pas valide, a expiré ou a déjà été utilisé.');
		expect(screen.getByRole('link', { name: 'Aller à la connexion' })).toHaveAttribute('href', '/connexion');
	});

	it('does not ask the server without a token', () => {
		history.replaceState(null, '', '/reinitialiser');
		mockApi({});
		render(Page);
		expect(screen.getByRole('alert')).toHaveTextContent('Ce lien est incomplet.');
		expect(calls()).toEqual([]);
	});
});
