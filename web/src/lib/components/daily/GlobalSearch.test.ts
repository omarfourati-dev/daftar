import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import GlobalSearch from './GlobalSearch.svelte';
import { deps } from '../../api';
import { auth } from '../../auth.svelte';
import { i18n } from '../../i18n.svelte';
import { json, mockApi } from '../../test-utils';
import { assistant } from '../../agenda/fixtures';

const sami = { id: 7, firstName: 'Sami', lastName: 'Trabelsi', phone: '+21620123456', birthYear: null, lang: 'fr', reminderConsent: true, noShows: 0, attended: 1, dueMillimes: 0, nextAppointmentAt: null };
const salma = { ...sami, id: 8, firstName: 'Salma', lastName: 'Ben Omar', phone: '+21620000006' };

describe('GlobalSearch in the header', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
	});

	it('finds patients by name or phone and opens the file with the keyboard', async () => {
		mockApi({ 'GET /api/patients?q=sa&limit=8': () => json(200, { items: [sami, salma], total: 2 }) });
		render(GlobalSearch);
		const box = screen.getByRole('combobox', { name: 'Rechercher un patient' });
		await fireEvent.input(box, { target: { value: 'sa' } });
		const options = await screen.findAllByRole('option');
		expect(options.map((o) => o.textContent)).toEqual([expect.stringContaining('Sami Trabelsi'), expect.stringContaining('Salma Ben Omar'), 'Tous les résultats pour « sa »']);
		expect(box).toHaveAttribute('aria-expanded', 'true');
		await fireEvent.keyDown(box, { key: 'ArrowDown' });
		await fireEvent.keyDown(box, { key: 'ArrowDown' });
		expect(box.getAttribute('aria-activedescendant')).toBe(options[1].id);
		await fireEvent.keyDown(box, { key: 'Enter' });
		expect(deps.goto).toHaveBeenCalledWith('/app/patients/8');
		expect(box).toHaveValue('');
	});

	it('opens the patient list with all results, and Escape closes', async () => {
		mockApi({ 'GET /api/patients?q=20%201&limit=8': () => json(200, { items: [sami], total: 14 }) });
		render(GlobalSearch);
		const box = screen.getByRole('combobox');
		await fireEvent.input(box, { target: { value: '20 1' } });
		await fireEvent.click(await screen.findByRole('option', { name: 'Tous les résultats pour « 20 1 »' }));
		expect(deps.goto).toHaveBeenCalledWith('/app/patients?q=20%201');
		await fireEvent.input(box, { target: { value: '20 1' } });
		await screen.findAllByRole('option');
		await fireEvent.keyDown(box, { key: 'Escape' });
		expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
	});

	it('says when nobody matches', async () => {
		mockApi({ 'GET /api/patients?q=zz&limit=8': () => json(200, { items: [], total: 0 }) });
		render(GlobalSearch);
		await fireEvent.input(screen.getByRole('combobox'), { target: { value: 'zz' } });
		expect(await screen.findByText('Aucun patient trouvé.')).toBeInTheDocument();
		await vi.waitFor(() => expect(screen.getByRole('combobox')).toHaveAttribute('aria-expanded', 'true'));
	});
});
