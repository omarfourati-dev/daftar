import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { hostDeps } from '#lib/host';
import { i18n } from '#lib/i18n.svelte';
import { install, installDeps } from '#lib/install.svelte';
import { calls, json, mockApi, noContent } from '#lib/test-utils';
import { owner } from '#lib/testing/fixtures';

const IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1';
const ANDROID = 'Mozilla/5.0 (Linux; Android 15; Pixel 8) AppleWebKit/537.36 Chrome/131.0 Mobile Safari/537.36';

describe('/app/installer (A4)', () => {
	beforeEach(() => {
		i18n.setLocale('fr');
		auth.set('tok', owner);
		hostDeps.hostname = () => 'cabinet-lac.daftar.omarfourati.de';
		installDeps.userAgent = () => IPHONE;
		installDeps.standalone = () => false;
		install.reset();
	});
	afterEach(() => {
		hostDeps.hostname = () => location.hostname;
	});

	it('shows the steps for this phone first and a QR code of the practice app for the team', async () => {
		mockApi({});
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'Installer l’application' })).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: 'Sur cet appareil : iPhone et iPad (Safari)' })).toBeInTheDocument();
		expect(screen.getByText('Touchez le bouton Partager (le carré avec une flèche).')).toBeInTheDocument();
		expect(await screen.findByRole('img', { name: 'QR code de l’application du cabinet' })).toBeInTheDocument();
		expect(screen.queryByText(/ouvrez cette page à l’adresse du cabinet/)).not.toBeInTheDocument();
	});

	it('uses the browser’s install prompt when there is one and ticks the first step', async () => {
		installDeps.userAgent = () => ANDROID;
		const prompt = vi.fn(async () => undefined);
		const event = Object.assign(new Event('beforeinstallprompt', { cancelable: true }), {
			prompt,
			userChoice: Promise.resolve({ outcome: 'accepted' as const })
		});
		window.dispatchEvent(event);
		mockApi({ 'POST /api/onboarding/install/done': () => noContent() });
		render(Page);
		expect(screen.getByRole('heading', { name: 'Sur cet appareil : Android (Chrome)' })).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Installer l’application' }));
		expect(prompt).toHaveBeenCalledOnce();
		expect(await screen.findByText('L’application est installée sur cet appareil.')).toBeInTheDocument();
		expect(calls()).toContain('POST /api/onboarding/install/done');
	});

	it('sends visitors of the main domain to the practice address first', () => {
		hostDeps.hostname = () => 'daftar.omarfourati.de';
		mockApi({});
		render(Page);
		expect(screen.getByText(/ouvrez cette page à l’adresse du cabinet/)).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Ouvrir l’adresse du cabinet' })).toHaveAttribute(
			'href',
			`${location.protocol}//cabinet-lac.${location.host}/app/installer`
		);
	});

	it('lets the team tick the step by hand', async () => {
		mockApi({ 'POST /api/onboarding/install/done': () => noContent() });
		render(Page);
		await fireEvent.click(screen.getByRole('button', { name: 'C’est fait, l’application est installée' }));
		expect(await screen.findByText('Parfait ! L’étape « Installer l’application » est cochée.')).toBeInTheDocument();
	});

	it('says so when it already runs as the installed app', () => {
		installDeps.standalone = () => true;
		mockApi({ 'POST /api/onboarding/install/done': () => json(204, undefined) });
		render(Page);
		expect(screen.getByText('L’application est installée sur cet appareil.')).toBeInTheDocument();
	});
});
