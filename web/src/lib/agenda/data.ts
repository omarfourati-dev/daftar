/** Loading what the agenda pages need (practice settings, practitioners, catalog, closures, appointments). */
import { api } from '../api';
import type { Appointment, Closure, PracticeSettings, Practitioner, Service } from '../types/agenda';

export interface AgendaBase {
	practice: PracticeSettings;
	/** Active practitioners, in their order. */
	practitioners: Practitioner[];
	/** All services (inactive ones only to name old appointments). */
	services: Service[];
	closures: Closure[];
}

const bySort = <T extends { sort?: number; id: number }>(a: T, b: T) => (a.sort ?? 0) - (b.sort ?? 0) || a.id - b.id;

/** The practice is required; the lists fall back to empty (e.g. an older backend or a missing right). */
export async function loadAgendaBase(): Promise<AgendaBase> {
	const [practice, practitioners, services, closures] = await Promise.all([
		api<PracticeSettings>('/api/practice'),
		api<Practitioner[]>('/api/practitioners').catch(() => [] as Practitioner[]),
		api<Service[]>('/api/services').catch(() => [] as Service[]),
		api<Closure[]>('/api/closures').catch(() => [] as Closure[])
	]);
	return {
		practice,
		practitioners: practitioners.filter((p) => p.active !== false).sort(bySort),
		services: [...services].sort(bySort),
		closures
	};
}

export function loadAppointments(from: string, to: string): Promise<Appointment[]> {
	return api<Appointment[]>(`/api/appointments?from=${from}&to=${to}`);
}

/** Unwraps `{appointment, conflicts}` (contract of section 5) or a bare appointment. */
export function savedAppointment(body: { appointment: Appointment } | Appointment): Appointment {
	return 'appointment' in body ? body.appointment : body;
}
