/** Shapes of the API (backend daftar/*.py). JSON fields are camelCase; instants carry the Tunis offset. */

export type Role = 'admin' | 'owner' | 'dentist' | 'assistant';
export type Lang = 'fr' | 'ar';
export type Specialty =
	| 'generaliste'
	| 'dentiste'
	| 'pediatre'
	| 'gynecologue'
	| 'dermatologue'
	| 'ophtalmologue'
	| 'cardiologue'
	| 'orl'
	| 'kinesitherapeute'
	| 'psychologue'
	| 'autre';
export type PracticeStatus = 'pilot' | 'trial' | 'active' | 'past_due' | 'suspended' | 'canceled';

export interface PracticeBrief {
	id: number;
	name: string;
	slug: string;
	specialty: Specialty | string;
	status: PracticeStatus | string;
	brandColor: string;
	isDemo: boolean;
	demoExpiresAt: string | null;
}

/** `GET /api/auth/me` */
export interface Me {
	id: number;
	email: string;
	name: string;
	role: Role | string;
	lang: Lang | string;
	practice: PracticeBrief | null;
}

/** `{token, user}` – login, invitation accept, demo start. */
export interface Session {
	token: string;
	user: Me;
}
