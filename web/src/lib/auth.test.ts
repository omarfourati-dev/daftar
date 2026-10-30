import { beforeEach, describe, expect, it, vi } from 'vitest';

const ME = {
	id: 7,
	email: 'amira@cabinet.tn',
	name: 'Amira',
	role: 'assistant',
	lang: 'ar',
	practice: {
		id: 3,
		name: 'Cabinet du Lac',
		slug: 'cabinet-lac',
		specialty: 'dentiste',
		status: 'pilot',
		brandColor: '#0f766e',
		isDemo: false,
		demoExpiresAt: null
	}
} as const;

describe('auth', () => {
	beforeEach(() => {
		localStorage.clear();
		vi.resetModules();
	});

	it('persists token and user and clears them', async () => {
		const { auth } = await import('./auth.svelte');
		auth.set('tok', ME);
		expect(localStorage.getItem('daftar.token')).toBe('tok');
		vi.resetModules();
		const again = (await import('./auth.svelte')).auth; // a new page load reads storage
		expect(again.token).toBe('tok');
		expect(again.user).toEqual(ME);
		expect(again.role).toBe('assistant');
		auth.clear();
		expect(auth.token).toBeNull();
		expect(auth.user).toBeNull();
		expect(localStorage.getItem('daftar.user')).toBeNull();
	});

	it('updates the user without touching the token and the token without the user', async () => {
		const { auth } = await import('./auth.svelte');
		auth.set('tok', ME);
		auth.setUser({ ...ME, name: 'Amira B.' });
		expect(auth.user?.name).toBe('Amira B.');
		expect(auth.token).toBe('tok');
		auth.setToken('tok2'); // after a password change
		expect(auth.user?.name).toBe('Amira B.');
		expect(auth.stored()).toBe('tok2');
	});

	it('ignores a broken stored user', async () => {
		localStorage.setItem('daftar.token', 'tok');
		localStorage.setItem('daftar.user', '{not json');
		const { auth } = await import('./auth.svelte');
		expect(auth.token).toBe('tok');
		expect(auth.user).toBeNull();
	});

	it('works when storage throws (private mode)', async () => {
		vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
			throw new Error('blocked');
		});
		vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
			throw new Error('blocked');
		});
		const { auth } = await import('./auth.svelte');
		expect(auth.token).toBeNull();
		auth.set('tok', ME);
		expect(auth.token).toBe('tok');
		vi.restoreAllMocks();
	});
});
