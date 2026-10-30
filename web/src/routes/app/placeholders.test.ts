import { render, screen } from '@testing-library/svelte';
import type { Component } from 'svelte';
import { beforeEach, describe, expect, it } from 'vitest';
import Admin from './admin/+page.svelte';
import Caisse from './caisse/+page.svelte';
import Patients from './patients/+page.svelte';
import Rappels from './rappels/+page.svelte';
import Reglages from './reglages/+page.svelte';
import { i18n } from '#lib/i18n.svelte';

// Each page is replaced by its feature work; until then it shows its title in the current language.
const pages: [string, Component, string, string][] = [
	['/app/patients', Patients, 'Patients', 'المرضى'],
	['/app/caisse', Caisse, 'Caisse', 'الصندوق'],
	['/app/rappels', Rappels, 'Rappels', 'التذكيرات'],
	['/app/reglages', Reglages, 'Réglages', 'الإعدادات'],
	['/app/admin', Admin, 'Administration', 'الإدارة']
];

describe('app pages', () => {
	beforeEach(() => i18n.setLocale('fr'));

	it.each(pages)('%s shows its title in French and Arabic', (_path, Page, fr, ar) => {
		const { unmount } = render(Page);
		expect(screen.getByRole('heading', { level: 1, name: fr })).toBeInTheDocument();
		unmount();
		i18n.setLocale('ar');
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: ar })).toBeInTheDocument();
	});
});
