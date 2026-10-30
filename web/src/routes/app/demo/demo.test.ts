import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page@.svelte';
import { deps } from '#lib/api';
import { auth } from '#lib/auth.svelte';
import { i18n } from '#lib/i18n.svelte';
import { json, mockApi, problem, sentJson } from '#lib/test-utils';
import { owner } from '#lib/testing/fixtures';

const demoUser = { ...owner, email: 'demo-x@demo.daftar.invalid', practice: { ...owner.practice!, isDemo: true, demoExpiresAt: '2099-01-01T00:00:00+01:00' } };

describe('/app/demo', () => {
	beforeEach(() => {
		i18n.setLocale('fr');
		auth.clear();
		history.replaceState(null, '', '/app/demo');
	});

	it('starts a demo for the chosen specialty in the current language', async () => {
		mockApi({ 'POST /api/demo': () => json(201, { token: 'demo-tok', user: demoUser }) });
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'Essayez Daftar avec un cabinet fictif' })).toBeInTheDocument();
		expect(screen.getByRole('radio', { name: 'Médecine générale' })).toBeChecked();
		await fireEvent.click(screen.getByRole('radio', { name: 'Kinésithérapie' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Lancer la démo' }));
		await vi.waitFor(() => expect(auth.token).toBe('demo-tok'));
		expect(sentJson('POST /api/demo')).toEqual({ lang: 'fr', specialty: 'kinesitherapeute' });
		expect(deps.goto).toHaveBeenCalledWith('/app');
	});

	it('takes language and specialty from the address (links from the landing page)', async () => {
		history.replaceState(null, '', '/app/demo?lang=ar&specialty=dentiste');
		mockApi({ 'POST /api/demo': () => json(201, { token: 't', user: demoUser }) });
		render(Page);
		expect(screen.getByRole('radio', { name: 'طب الأسنان' })).toBeChecked();
		await fireEvent.click(screen.getByRole('button', { name: 'بدء النسخة التجريبية' }));
		await vi.waitFor(() => expect(sentJson('POST /api/demo')).toEqual({ lang: 'ar', specialty: 'dentiste' }));
	});

	it('explains the limit of demos per connection', async () => {
		mockApi({ 'POST /api/demo': () => problem(429, 'too_many_requests') });
		render(Page);
		await fireEvent.click(screen.getByRole('button', { name: 'Lancer la démo' }));
		expect(await screen.findByRole('alert')).toHaveTextContent('Réessayez dans une heure');
	});

	it('offers to resume a running demo', () => {
		auth.set('tok', demoUser);
		mockApi({});
		render(Page);
		expect(screen.getByRole('link', { name: 'Reprendre ma démo en cours' })).toHaveAttribute('href', '/app');
	});
});
