import { fireEvent, render } from '@testing-library/svelte';
import { beforeEach, describe, expect, it } from 'vitest';
import Shortcuts from './Shortcuts.svelte';
import { deps } from '../../api';
import { newAppointment } from '../../agenda/requests.svelte';
import { mockApi } from '../../test-utils';

describe('keyboard shortcuts of the app', () => {
	beforeEach(() => {
		document.body.innerHTML = '<input id="global-search" /><textarea id="note"></textarea>';
		mockApi({});
	});

	it('"/" jumps to the patient search', async () => {
		render(Shortcuts, { props: { path: '/app' } });
		await fireEvent.keyDown(window, { key: '/' });
		expect(document.activeElement?.id).toBe('global-search');
	});

	it('"N" opens a new appointment: from any page via the agenda, on the agenda directly', async () => {
		const { unmount } = render(Shortcuts, { props: { path: '/app/patients' } });
		await fireEvent.keyDown(window, { key: 'n' });
		expect(deps.goto).toHaveBeenCalledWith('/app/agenda?nouveau=1');
		unmount();
		const before = newAppointment.count;
		render(Shortcuts, { props: { path: '/app/agenda' } });
		await fireEvent.keyDown(window, { key: 'N' });
		expect(newAppointment.count).toBe(before + 1);
	});

	it('does nothing while typing or with modifier keys', async () => {
		render(Shortcuts, { props: { path: '/app' } });
		const note = document.getElementById('note') as HTMLTextAreaElement;
		note.focus();
		await fireEvent.keyDown(note, { key: 'n' });
		await fireEvent.keyDown(note, { key: '/' });
		await fireEvent.keyDown(window, { key: 'n', ctrlKey: true });
		expect(deps.goto).not.toHaveBeenCalled();
		expect(document.activeElement?.id).toBe('note');
	});
});
