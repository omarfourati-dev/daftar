import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Actes from './+page.svelte';
import Praticiens from '../praticiens/+page.svelte';
import { auth } from '#lib/auth.svelte';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, mockApi, noContent, sentJson } from '#lib/test-utils';
import { owner, practitioners, services } from '#lib/testing/fixtures';

describe('/app/reglages/actes', () => {
	beforeEach(() => {
		i18n.setLocale('fr');
		auth.set('tok', owner);
	});

	it('lists acts with duration, price, online and inactive state', async () => {
		mockApi({ 'GET /api/services': () => json(200, services) });
		render(Actes);
		const row = (await screen.findByRole('heading', { name: 'Consultation' })).closest('li')!;
		expect(within(row).getByText('30 min')).toBeInTheDocument();
		expect(within(row).getByText('40 DT')).toBeInTheDocument();
		expect(within(row).getByText('En ligne')).toBeInTheDocument();
		expect(within(screen.getByRole('heading', { name: 'Détartrage' }).closest('li')!).getByText('prix libre')).toBeInTheDocument();
		expect(within(screen.getByRole('heading', { name: 'Blanchiment' }).closest('li')!).getByText('Désactivé')).toBeInTheDocument();
	});

	it('adds an act', async () => {
		mockApi({
			'GET /api/services': () => json(200, services),
			'POST /api/services': () => json(201, { ...services[0], id: 14, nameFr: 'Radio panoramique', nameAr: '', durationMin: 15, priceMillimes: 35500, onlineBookable: false })
		});
		render(Actes);
		await fireEvent.click(await screen.findByRole('button', { name: 'Nouvel acte' }));
		const dialog = within(screen.getByRole('dialog', { name: 'Nouvel acte' }));
		await fireEvent.input(dialog.getByLabelText('Acte (français)'), { target: { value: 'Radio panoramique' } });
		await fireEvent.input(dialog.getByLabelText('Durée (min)'), { target: { value: '15' } });
		await fireEvent.input(dialog.getByLabelText(/^Prix \(DT\)/), { target: { value: '35,5' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer l’acte' }));
		expect(await screen.findByRole('heading', { name: 'Radio panoramique' })).toBeInTheDocument();
		expect(sentJson('POST /api/services')).toEqual({
			nameFr: 'Radio panoramique',
			nameAr: '',
			durationMin: 15,
			priceMillimes: 35500,
			onlineBookable: false,
			active: true
		});
	});

	it('edits an act and validates the duration', async () => {
		mockApi({
			'GET /api/services': () => json(200, services),
			'PATCH /api/services/11': () => json(200, { ...services[0], durationMin: 20 })
		});
		render(Actes);
		await fireEvent.click(await screen.findByRole('button', { name: 'Modifier Consultation' }));
		const dialog = within(screen.getByRole('dialog', { name: 'Modifier Consultation' }));
		await fireEvent.input(dialog.getByLabelText('Durée (min)'), { target: { value: '2' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer l’acte' }));
		expect(dialog.getByLabelText('Durée (min)')).toHaveAccessibleDescription('Durée entre 5 et 480 minutes.');
		await fireEvent.input(dialog.getByLabelText('Durée (min)'), { target: { value: '20' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer l’acte' }));
		await vi.waitFor(() => expect(sentJson('PATCH /api/services/11')).toEqual({ durationMin: 20 }));
		expect(await screen.findByText('20 min')).toBeInTheDocument();
	});

	it('deletes an act after confirmation', async () => {
		mockApi({ 'GET /api/services': () => json(200, services), 'DELETE /api/services/12': () => noContent() });
		render(Actes);
		await fireEvent.click(await screen.findByRole('button', { name: 'Supprimer Détartrage' }));
		await fireEvent.click(within(screen.getByRole('dialog', { name: 'Supprimer « Détartrage » ?' })).getByRole('button', { name: 'Supprimer l’acte' }));
		await vi.waitFor(() => expect(screen.queryByRole('heading', { name: 'Détartrage' })).not.toBeInTheDocument());
		expect(calls()).toContain('DELETE /api/services/12');
	});
});

describe('/app/reglages/praticiens', () => {
	beforeEach(() => {
		i18n.setLocale('fr');
		auth.set('tok', owner);
	});

	it('lists, adds and deactivates practitioners', async () => {
		mockApi({
			'GET /api/practitioners': () => json(200, practitioners),
			'POST /api/practitioners': () => json(201, { id: 23, name: 'Rim Haddad', title: '', specialty: 'kinesitherapeute', color: '#b45309', onlineBookable: true, active: true, sort: 3 }),
			'PATCH /api/practitioners/22': () => json(200, { ...practitioners[1], active: false })
		});
		render(Praticiens);
		const karim = (await screen.findByRole('heading', { name: 'Dr. Karim Trabelsi' })).closest('li')!;
		expect(within(karim).getByText('ORL')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Nouveau praticien' }));
		const dialog = within(screen.getByRole('dialog', { name: 'Nouveau praticien' }));
		await fireEvent.input(dialog.getByLabelText('Titre'), { target: { value: '' } });
		await fireEvent.input(dialog.getByLabelText('Nom'), { target: { value: 'Rim Haddad' } });
		await fireEvent.change(dialog.getByLabelText('Spécialité'), { target: { value: 'kinesitherapeute' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Enregistrer le praticien' }));
		expect(await screen.findByRole('heading', { name: 'Rim Haddad' })).toBeInTheDocument();
		expect(sentJson('POST /api/practitioners')).toMatchObject({ name: 'Rim Haddad', title: '', specialty: 'kinesitherapeute', onlineBookable: true, active: true });

		await fireEvent.click(screen.getByRole('button', { name: 'Modifier Dr. Karim Trabelsi' }));
		const edit = within(screen.getByRole('dialog', { name: 'Modifier Dr. Karim Trabelsi' }));
		await fireEvent.click(edit.getByRole('checkbox', { name: 'Actif' }));
		await fireEvent.click(edit.getByRole('button', { name: 'Enregistrer le praticien' }));
		await vi.waitFor(() => expect(sentJson('PATCH /api/practitioners/22')).toEqual({ active: false }));
		expect(await within(screen.getByRole('heading', { name: 'Dr. Karim Trabelsi' }).closest('li')!).findByText('Désactivé')).toBeInTheDocument();
	});
});
