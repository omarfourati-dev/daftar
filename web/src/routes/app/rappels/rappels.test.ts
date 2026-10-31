import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { auth } from '#lib/auth.svelte';
import { clock } from '#lib/clock';
import { i18n } from '#lib/i18n.svelte';
import { calls, json, mockApi, problem, type Handler } from '#lib/test-utils';
import { appt, assistant, NOW, practiceBrief } from '#lib/agenda/fixtures';

const youssef = {
	appointment: appt({ id: 31, startsAt: '2026-10-31T09:00:00+01:00', reason: 'Séance de rééducation', patient: { id: 1, firstName: 'Youssef', lastName: 'Marzouki', phone: '+21620000031', noShows: 0, lang: 'fr' } }),
	patientLang: 'fr',
	reminderConsent: true,
	phoneDigits: '21620000031',
	message: 'Bonjour Youssef, rappel de votre rendez-vous demain 31/10/2026 à 09:00.'
};
const mounia = {
	appointment: appt({ id: 30, startsAt: '2026-10-31T08:30:00+01:00', reminderSentAt: '2026-10-30T09:12:00+01:00', patient: { id: 2, firstName: 'Mounia', lastName: 'Chebbi', phone: '+21620000030', noShows: 0, lang: 'fr' } }),
	patientLang: 'ar',
	reminderConsent: true,
	phoneDigits: '21620000030',
	message: 'مرحبًا منية، نذكّرك بموعدك غدًا.'
};
const anis = {
	appointment: appt({ id: 32, startsAt: '2026-10-31T11:30:00+01:00', patient: { id: 3, firstName: 'Anis', lastName: 'Dridi', phone: '+21620000032', noShows: 0, lang: 'fr' } }),
	patientLang: 'fr',
	reminderConsent: false,
	phoneDigits: '21620000032',
	message: 'Bonjour Anis…'
};

function rappelsApi(extra: Record<string, Handler> = {}) {
	return mockApi({ 'GET /api/reminders?day=2026-10-31': () => json(200, [youssef, mounia, anis]), ...extra });
}
const card = (name: RegExp) => within(screen.getByRole('heading', { name }).closest('li') as HTMLElement);

describe('/app/rappels – reminders of tomorrow by click', () => {
	beforeEach(() => {
		auth.set('tok', assistant);
		i18n.setLocale('fr');
		clock.now = () => new Date(NOW);
		history.replaceState(null, '', '/app/rappels');
	});

	it('lists tomorrow with the ready message and WhatsApp / SMS links', async () => {
		rappelsApi();
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'Rappels' })).toBeInTheDocument();
		expect(await screen.findByText('3 rendez-vous, 1 rappel(s) envoyé(s)')).toBeInTheDocument();
		expect(screen.getByText(/Rendez-vous du samedi 31 octobre 2026/)).toBeInTheDocument();
		const y = card(/Youssef Marzouki/);
		expect(y.getByText('Bonjour Youssef, rappel de votre rendez-vous demain 31/10/2026 à 09:00.')).toBeInTheDocument();
		expect(y.getByRole('link', { name: 'WhatsApp' })).toHaveAttribute('href', `https://wa.me/21620000031?text=${encodeURIComponent(youssef.message)}`);
		expect(y.getByRole('link', { name: 'SMS' })).toHaveAttribute('href', `sms:+21620000031?&body=${encodeURIComponent(youssef.message)}`);
		expect(card(/Mounia Chebbi/).getByText('Envoyé à 09:12')).toBeInTheDocument();
	});

	it('marks the reminder as sent when WhatsApp is opened', async () => {
		rappelsApi({ 'POST /api/appointments/31/reminder': () => json(200, { ...youssef.appointment, reminderSentAt: NOW }) });
		render(Page);
		await screen.findByText('3 rendez-vous, 1 rappel(s) envoyé(s)');
		const link = card(/Youssef Marzouki/).getByRole('link', { name: 'WhatsApp' });
		link.addEventListener('click', (e) => e.preventDefault()); // jsdom cannot navigate
		await fireEvent.click(link);
		expect(await card(/Youssef Marzouki/).findByText('Envoyé à 10:10')).toBeInTheDocument();
		expect(calls()).toContain('POST /api/appointments/31/reminder');
		expect(screen.getByText('3 rendez-vous, 2 rappel(s) envoyé(s)')).toBeInTheDocument();
	});

	it('can mark as sent without opening anything', async () => {
		rappelsApi({ 'POST /api/appointments/31/reminder': () => json(200, { ...youssef.appointment, reminderSentAt: NOW }) });
		render(Page);
		await screen.findByText('3 rendez-vous, 1 rappel(s) envoyé(s)');
		await fireEvent.click(card(/Youssef Marzouki/).getByRole('button', { name: 'Marquer comme envoyé' }));
		expect(await card(/Youssef Marzouki/).findByText('Envoyé à 10:10')).toBeInTheDocument();
	});

	it('greys out patients without consent', async () => {
		rappelsApi();
		render(Page);
		await screen.findByText('3 rendez-vous, 1 rappel(s) envoyé(s)');
		const a = card(/Anis Dridi/);
		expect(a.getByText('Pas d’accord pour les rappels')).toBeInTheDocument();
		expect(a.queryByRole('link', { name: 'WhatsApp' })).not.toBeInTheDocument();
		expect(a.getByRole('button', { name: 'WhatsApp' })).toBeDisabled();
		expect(a.getByRole('button', { name: 'SMS' })).toBeDisabled();
	});

	it('opens nothing in a demo practice, explains instead', async () => {
		auth.set('tok', { ...assistant, practice: { ...practiceBrief, isDemo: true } });
		rappelsApi({ 'POST /api/appointments/31/reminder': () => json(200, { ...youssef.appointment, reminderSentAt: NOW }) });
		render(Page);
		await screen.findByText('3 rendez-vous, 1 rappel(s) envoyé(s)');
		const y = card(/Youssef Marzouki/);
		expect(y.queryByRole('link', { name: 'WhatsApp' })).not.toBeInTheDocument();
		await fireEvent.click(y.getByRole('button', { name: 'WhatsApp' }));
		expect(await y.findByRole('status')).toHaveTextContent('Démo : rien n’est envoyé.');
	});

	it('goes to another day', async () => {
		rappelsApi({ 'GET /api/reminders?day=2026-11-01': () => json(200, []) });
		render(Page);
		await screen.findByText('3 rendez-vous, 1 rappel(s) envoyé(s)');
		await fireEvent.click(screen.getByRole('button', { name: 'Jour suivant' }));
		expect(await screen.findByText('Aucun rendez-vous ce jour-là.')).toBeInTheDocument();
	});

	it('explains a loading problem and works in Arabic', async () => {
		i18n.setLocale('ar');
		rappelsApi({ 'GET /api/reminders?day=2026-10-31': () => problem(500, 'server_error') });
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'التذكيرات' })).toBeInTheDocument();
		expect(await screen.findByRole('alert')).toHaveTextContent('تعذّر تحميل التذكيرات.');
		await vi.waitFor(() => expect(calls()).toEqual(['GET /api/reminders?day=2026-10-31']));
	});
});
