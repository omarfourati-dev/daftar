import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { beforeEach, describe, expect, it } from 'vitest';
import AppShell from './AppShell.svelte';
import { phoneBooking, patientSearch } from '../agenda/requests.svelte';
import { auth } from '../auth.svelte';
import { badges } from '../badges.svelte';
import { i18n } from '../i18n.svelte';
import { json, mockApi } from '../test-utils';
import { adminUser, assistant, dentist, owner } from '../testing/fixtures';
import type { Me } from '../types';

/** Fixlist 2 (C, B4): import, subscription and installer in the navigation; phone booking and patient search on phones. */
const children = createRawSnippet(() => ({ render: () => '<p>Contenu</p>' }));

function shell(user: Me, path = '/app') {
	auth.set('tok', user);
	mockApi({ 'GET /api/auth/me': () => json(200, user), 'GET /api/badges': () => json(200, { onlineRequests: 0, overdue: 0 }) });
	return render(AppShell, { props: { path, children } });
}
const hrefs = (links: HTMLElement[]) => links.map((a) => a.getAttribute('href'));

describe('AppShell – tools and phone shortcuts (fixlist 2)', () => {
	beforeEach(() => {
		i18n.setLocale('fr');
		badges.stop();
		phoneBooking.open = false;
		patientSearch.open = false;
	});

	it('lists import, subscription and installer under "Outils" in the sidebar, by role', () => {
		const { unmount } = shell(owner);
		const tools = () => within(screen.getByRole('navigation', { name: 'Outils' }));
		expect(hrefs(tools().getAllByRole('link'))).toEqual(['/app/import', '/app/abonnement', '/app/installer']);
		expect(tools().getByRole('link', { name: 'Abonnement' })).toBeInTheDocument();
		// the main navigation stays as it was
		const main = within(screen.getByRole('navigation', { name: 'Navigation principale' }));
		expect(main.queryByRole('link', { name: 'Importer' })).not.toBeInTheDocument();
		unmount();
		shell(assistant);
		expect(hrefs(tools().getAllByRole('link'))).toEqual(['/app/import', '/app/installer']);
	});

	it('gives a dentist the installer only and the admin no tools', () => {
		const { unmount } = shell(dentist);
		expect(hrefs(within(screen.getByRole('navigation', { name: 'Outils' })).getAllByRole('link'))).toEqual(['/app/installer']);
		unmount();
		shell(adminUser, '/app/admin');
		expect(screen.queryByRole('navigation', { name: 'Outils' })).not.toBeInTheDocument();
	});

	it('marks the current tool page', () => {
		shell(owner, '/app/abonnement');
		expect(within(screen.getByRole('navigation', { name: 'Outils' })).getByRole('link', { name: 'Abonnement' })).toHaveAttribute('aria-current', 'page');
	});

	it('the phone menu "Plus" has the phone appointment, the patient search and the tools', async () => {
		shell(owner);
		await fireEvent.click(within(screen.getByRole('navigation', { name: 'Navigation rapide' })).getByRole('button', { name: 'Plus' }));
		const more = within(screen.getByRole('dialog', { name: 'Plus' }));
		expect(hrefs(more.getAllByRole('link'))).toEqual([
			'/app/caisse',
			'/app/rappels',
			'/app/statistiques',
			'/app/reglages',
			'/app/import',
			'/app/abonnement',
			'/app/installer'
		]);
		await fireEvent.click(more.getByRole('button', { name: 'Rendez-vous par téléphone' }));
		expect(phoneBooking.open).toBe(true);
		expect(screen.queryByRole('dialog', { name: 'Plus' })).not.toBeInTheDocument();
	});

	it('"Rechercher un patient" in the menu opens the search and puts the cursor into it', async () => {
		shell(assistant);
		await fireEvent.click(within(screen.getByRole('navigation', { name: 'Navigation rapide' })).getByRole('button', { name: 'Plus' }));
		await fireEvent.click(within(screen.getByRole('dialog', { name: 'Plus' })).getByRole('button', { name: 'Rechercher un patient' }));
		expect(patientSearch.open).toBe(true);
		const search = screen.getByRole('combobox', { name: 'Rechercher un patient' });
		expect(search).toHaveFocus();
		expect(search.closest('[data-search]')).not.toHaveClass('hidden'); // folded away on phones until asked for
		expect(screen.queryByRole('dialog', { name: 'Plus' })).not.toBeInTheDocument();
	});

	it('keeps the search folded away on phones until asked for, and folds it again on another page', async () => {
		const { rerender } = shell(assistant);
		const box = () => screen.getByRole('combobox', { name: 'Rechercher un patient' }).closest('[data-search]');
		expect(box()).toHaveClass('hidden');
		expect(box()).toHaveClass('sm:block');
		patientSearch.show();
		expect(box()).not.toHaveClass('hidden');
		await rerender({ path: '/app/patients/7', children });
		expect(patientSearch.open).toBe(false);
		expect(box()).toHaveClass('hidden');
	});

	it('keeps the header on one line on phones: short language labels and an icon to sign out, full names for screen readers', () => {
		shell(owner);
		const header = within(screen.getByRole('banner'));
		const logout = header.getByRole('button', { name: 'Se déconnecter' });
		expect(logout.querySelector('svg')).not.toBeNull();
		expect(within(logout).getByText('Se déconnecter')).toHaveClass('max-lg:sr-only');
		const french = header.getByRole('button', { name: 'Français' });
		expect(within(french).getByText('FR')).toHaveAttribute('aria-hidden', 'true');
		expect(within(header.getByRole('button', { name: 'العربية' })).getByText('ع')).toHaveClass('lg:hidden');
	});
});
