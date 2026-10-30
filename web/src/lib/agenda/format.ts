/** Display names shared by the agenda, the waiting room and the patient file. */
import { i18n, t, translate } from '../i18n.svelte';
import type { AppointmentStatus } from '../status';
import type { Practitioner, Service } from '../types/agenda';

/** "Dr Amira Ben Salem" (title + name). */
export function practitionerLabel(p: Pick<Practitioner, 'name' | 'title'>): string {
	return [p.title?.trim(), p.name].filter(Boolean).join(' ');
}

export function personName(p: { firstName: string; lastName: string }): string {
	return `${p.firstName} ${p.lastName}`.trim();
}

/** Initials for an avatar: "Hichem Bouzid" → "HB". */
export function initials(p: { firstName: string; lastName: string }): string {
	return `${p.firstName.trim().charAt(0)}${p.lastName.trim().charAt(0)}`.toUpperCase();
}

/** The text of an appointment status, including `requested` (online request). */
export function statusLabel(status: AppointmentStatus | string): string {
	if (status === 'requested') return t('agenda.requested');
	return translate(`appointmentStatus.${status}`) ?? status;
}

/** Service name in the current language (Arabic falls back to French when empty). */
export function serviceLabel(s: Pick<Service, 'nameFr' | 'nameAr'>): string {
	return i18n.locale === 'ar' && s.nameAr ? s.nameAr : s.nameFr;
}

/** Statuses that free the slot again (backend FREEING_STATUSES). */
export const FREEING: readonly string[] = ['cancelled', 'no_show'];

/** Light background of an appointment block, by status (design section 6 colours). */
export const STATUS_TINT: Record<string, string> = {
	requested: 'bg-[repeating-linear-gradient(135deg,#f0fdfa_0_8px,#ffffff_8px_16px)] border-dashed border-brand-600',
	scheduled: 'bg-white border-slate-200',
	confirmed: 'bg-sky-50 border-sky-200',
	arrived: 'bg-amber-50 border-amber-200',
	in_treatment: 'bg-violet-50 border-violet-200',
	done: 'bg-emerald-50 border-emerald-200',
	no_show: 'bg-rose-50 border-rose-200 text-slate-600',
	cancelled: 'bg-zinc-50 border-zinc-200 text-zinc-500'
};

/** Inline-start accent of an appointment block, by status (design section 6 colours). */
export const STATUS_ACCENT: Record<string, string> = {
	requested: 'border-s-brand-600',
	scheduled: 'border-s-slate-400',
	confirmed: 'border-s-sky-500',
	arrived: 'border-s-amber-500',
	in_treatment: 'border-s-violet-500',
	done: 'border-s-emerald-500',
	no_show: 'border-s-rose-500',
	cancelled: 'border-s-zinc-300'
};
