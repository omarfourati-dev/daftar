import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PatientForm from './PatientForm.svelte';
import { auth } from '../../auth.svelte';
import { clock } from '../../clock';
import { i18n } from '../../i18n.svelte';
import { json, mockApi, sentJson } from '../../test-utils';
import { assistant } from '../../testing/fixtures';
import type { Patient } from '../../types/patients';

const patient = {
	id: 7, firstName: 'Sami', lastName: 'Trabelsi', phone: '+21620123456', birthYear: 1980, birthDate: null, lang: 'fr', reminderConsent: true,
	noShows: 0, attended: 1, dueMillimes: 0, nextAppointmentAt: null, notes: '', alerts: '', createdAt: '2026-10-01T09:00:00+01:00', cancelled: 0,
	totalMillimes: 0, paidMillimes: 0
} as Patient;

describe('the full birth date of a patient (spec stock-hygiène 6)', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
		clock.now = () => new Date('2026-10-30T10:10:00+01:00');
	});

	it('sends the date and lets the year follow it', async () => {
		mockApi({ 'PATCH /api/patients/7': () => json(200, { ...patient, birthDate: '1978-03-12', birthYear: 1978 }) });
		const onsaved = vi.fn();
		render(PatientForm, { props: { patient, onsaved, onclose: vi.fn() } });
		const year = screen.getByLabelText('ou année');
		expect(year).toHaveValue('1980');
		await fireEvent.input(screen.getByLabelText('Date de naissance'), { target: { value: '1978-03-12' } });
		expect(year).toBeDisabled();
		expect(year).toHaveValue('1978');
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
		await vi.waitFor(() => expect(onsaved).toHaveBeenCalled());
		expect(sentJson('PATCH /api/patients/7')).toMatchObject({ birthDate: '1978-03-12', birthYear: null });
	});

	it('refuses a birth date in the future', async () => {
		mockApi({});
		render(PatientForm, { props: { patient, onsaved: vi.fn(), onclose: vi.fn() } });
		await fireEvent.input(screen.getByLabelText('Date de naissance'), { target: { value: '2026-11-02' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));
		expect(await screen.findByRole('alert')).toHaveTextContent('Date de naissance invalide.');
	});
});
