import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { deps } from '#lib/api';
import { auth } from '#lib/auth.svelte';
import { hostDeps } from '#lib/host';
import { i18n } from '#lib/i18n.svelte';
import { json, mockApi, problem, sentJson } from '#lib/test-utils';

const owner = {
	id: 2,
	email: 'amira@cabinet.tn',
	name: 'Amira',
	role: 'owner',
	lang: 'ar',
	practice: { id: 1, name: 'Cabinet du Lac', slug: 'cabinet-lac', specialty: 'generaliste', status: 'pilot', brandColor: '#0f766e', isDemo: false, demoExpiresAt: null }
};
const admin = { id: 1, email: 'omar@daftar.tn', name: 'Admin', role: 'admin', lang: 'fr', practice: null };

async function fill(email: string, password: string) {
	await fireEvent.input(await screen.findByLabelText('E-mail'), { target: { value: email } });
	await fireEvent.input(screen.getByLabelText('Mot de passe'), { target: { value: password } });
	await fireEvent.click(screen.getByRole('button', { name: 'Se connecter' }));
}

describe('/connexion', () => {
	beforeEach(() => {
		auth.clear();
		i18n.setLocale('fr');
		hostDeps.hostname = () => 'localhost';
	});
	afterEach(() => {
		hostDeps.hostname = () => location.hostname;
	});

	it('signs in, stores the session, applies the account language and opens the app', async () => {
		mockApi({ 'POST /api/auth/login': () => json(200, { token: 'tok', user: owner }) });
		render(Page);
		expect(screen.getByRole('heading', { name: 'Connexion' })).toBeInTheDocument();
		await fill('amira@cabinet.tn', 'mot-de-passe-solide');
		await vi.waitFor(() => expect(auth.token).toBe('tok'));
		expect(sentJson('POST /api/auth/login')).toEqual({ email: 'amira@cabinet.tn', password: 'mot-de-passe-solide' });
		expect(auth.user?.name).toBe('Amira');
		expect(i18n.locale).toBe('ar');
		expect(deps.goto).toHaveBeenCalledWith('/app');
	});

	it('sends the admin to the administration', async () => {
		mockApi({ 'POST /api/auth/login': () => json(200, { token: 'tok', user: admin }) });
		render(Page);
		await fill('omar@daftar.tn', 'mot-de-passe-admin');
		await vi.waitFor(() => expect(deps.goto).toHaveBeenCalledWith('/app/admin'));
	});

	it('shows a translated error for a wrong password and keeps the form', async () => {
		mockApi({ 'POST /api/auth/login': () => problem(401, 'invalid_credentials', 'E-mail ou mot de passe incorrect.') });
		render(Page);
		await fill('amira@cabinet.tn', 'faux');
		expect(await screen.findByRole('alert')).toHaveTextContent('E-mail ou mot de passe incorrect.');
		expect(auth.token).toBeNull();
		expect(screen.getByRole('button', { name: 'Se connecter' })).toBeEnabled();
	});

	it('explains throttling', async () => {
		mockApi({ 'POST /api/auth/login': () => problem(429, 'too_many_requests') });
		render(Page);
		await fill('amira@cabinet.tn', 'faux');
		expect(await screen.findByRole('alert')).toHaveTextContent('Trop de tentatives');
	});

	it('switches to Arabic', async () => {
		mockApi({});
		render(Page);
		await fireEvent.click(screen.getByRole('button', { name: 'العربية' }));
		expect(await screen.findByRole('heading', { name: 'تسجيل الدخول' })).toBeInTheDocument();
		expect(document.documentElement.dir).toBe('rtl');
		expect(screen.getByLabelText('البريد الإلكتروني')).toBeInTheDocument();
	});

	it('offers the demo on the main domain', () => {
		mockApi({});
		render(Page);
		expect(screen.getByRole('link', { name: 'Essayer la démo' })).toHaveAttribute('href', '/app/demo');
	});

	it('shows the practice on its own sub-domain', async () => {
		hostDeps.hostname = () => 'cabinet-lac.daftar.omarfourati.de';
		mockApi({ 'GET /api/public/practices/cabinet-lac': () => json(200, { name: 'Cabinet du Lac', brandColor: '#1d4ed8' }) });
		render(Page);
		expect(await screen.findByRole('heading', { name: 'Cabinet du Lac' })).toBeInTheDocument();
		expect(screen.getByRole('img', { name: 'Cabinet du Lac' })).toHaveAttribute('src', '/icons/practice-192.png');
		expect(screen.queryByRole('link', { name: 'Essayer la démo' })).not.toBeInTheDocument();
	});

	it('still works on a sub-domain while the public profile is missing', async () => {
		hostDeps.hostname = () => 'cabinet-lac.daftar.omarfourati.de';
		mockApi({ 'GET /api/public/practices/cabinet-lac': () => problem(404, 'not_found') });
		render(Page);
		expect(await screen.findByRole('heading', { name: 'Connexion' })).toBeInTheDocument();
		expect(screen.getByRole('img', { name: 'Daftar' })).toHaveAttribute('src', '/icons/practice-192.png');
		expect(deps.goto).not.toHaveBeenCalled(); // a failing public call never signs anybody out
	});
});
