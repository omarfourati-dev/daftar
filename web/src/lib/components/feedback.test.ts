import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import FeedbackButton from './FeedbackButton.svelte';
import { i18n } from '../i18n.svelte';
import { calls, json, mockApi, sentJson } from '../test-utils';

describe('feedback button (J2)', () => {
	beforeEach(() => i18n.setLocale('fr'));

	it('sends an idea with the page it was written on', async () => {
		mockApi({ 'POST /api/feedback': () => json(201, { id: 1 }) });
		render(FeedbackButton, { props: { path: '/app/agenda' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Une idée ? Un problème ?' }));
		const dialog = within(screen.getByRole('dialog', { name: 'Une idée ? Un problème ?' }));
		await fireEvent.click(dialog.getByRole('button', { name: 'Envoyer' }));
		expect(dialog.getByLabelText('Votre message')).toHaveAccessibleDescription(/Écrivez votre message avant d’envoyer\./);
		expect(calls()).toEqual([]);
		await fireEvent.input(dialog.getByLabelText('Votre message'), { target: { value: 'Ajoutez les SMS automatiques, svp.' } });
		expect(dialog.getByText('34 / 2000')).toBeInTheDocument();
		await fireEvent.click(dialog.getByRole('button', { name: 'Envoyer' }));
		expect(await dialog.findByText('Merci ! Votre message est envoyé.')).toBeInTheDocument();
		expect(sentJson('POST /api/feedback')).toEqual({ message: 'Ajoutez les SMS automatiques, svp.', page: '/app/agenda' });
	});

	it('keeps the message when sending fails', async () => {
		mockApi({ 'POST /api/feedback': () => new Response('', { status: 500 }) });
		render(FeedbackButton, { props: { path: '/app' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Une idée ? Un problème ?' }));
		const dialog = within(screen.getByRole('dialog'));
		await fireEvent.input(dialog.getByLabelText('Votre message'), { target: { value: 'Bug' } });
		await fireEvent.click(dialog.getByRole('button', { name: 'Envoyer' }));
		await vi.waitFor(() => expect(dialog.getByRole('alert')).toBeInTheDocument());
		expect(dialog.getByLabelText('Votre message')).toHaveValue('Bug');
	});
});
