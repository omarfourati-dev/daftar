/**
 * The signed-in session: token and the `Me` object, kept in localStorage (`daftar.token`, `daftar.user`) so the app
 * starts instantly; the app shell refreshes `user` from `/api/auth/me` on every start.
 */
import type { Me, Role } from './types';

const TOKEN = 'daftar.token';
const USER = 'daftar.user';

function read(key: string): string | null {
	try {
		return localStorage.getItem(key);
	} catch {
		return null;
	}
}

function write(key: string, value: string | null) {
	try {
		if (value === null) localStorage.removeItem(key);
		else localStorage.setItem(key, value);
	} catch {
		/* private mode: memory only */
	}
}

function readUser(): Me | null {
	const text = read(USER);
	if (!text) return null;
	try {
		const user = JSON.parse(text) as Me;
		return user && typeof user === 'object' && typeof user.id === 'number' ? user : null;
	} catch {
		return null;
	}
}

class Auth {
	token = $state<string | null>(read(TOKEN));
	user = $state<Me | null>(readUser());

	get role(): Role | null {
		return (this.user?.role as Role | undefined) ?? null;
	}

	/** After login, invitation or demo start. */
	set(token: string, user: Me) {
		this.setToken(token);
		this.setUser(user);
	}

	/** A new token for the same user (e.g. after a password change). */
	setToken(token: string) {
		this.token = token;
		write(TOKEN, token);
	}

	setUser(user: Me) {
		this.user = user;
		write(USER, JSON.stringify(user));
	}

	/** The token as persisted (another tab may have replaced it). */
	stored(): string | null {
		return read(TOKEN);
	}

	clear() {
		this.token = null;
		this.user = null;
		write(TOKEN, null);
		write(USER, null);
	}
}

export const auth = new Auth();
