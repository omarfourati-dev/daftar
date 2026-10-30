/**
 * Column mapping of the Excel/CSV import (section 14) – the same fields and required rules as backend
 * daftar/imports.py (`PATIENT_FIELDS`, `APPOINTMENT_FIELDS`, `check_mapping`), so the page explains a missing
 * field before asking the server.
 */
import type { ImportKind, ImportMapping, ImportOptions } from './types/imports';

export const FIELDS: Record<ImportKind, readonly string[]> = {
	patients: ['lastName', 'firstName', 'fullName', 'phone', 'birthDate', 'birthYear', 'notes', 'alerts', 'lang', 'reminderConsent', 'openingBalance', 'externalRef'],
	appointments: ['date', 'time', 'datetime', 'durationMin', 'endTime', 'lastName', 'firstName', 'fullName', 'phone', 'service', 'practitioner', 'notes']
};

export const DEFAULT_OPTIONS: Readonly<ImportOptions> = Object.freeze({
	nameOrder: 'last_first',
	dateFormat: 'dmy',
	defaultLang: 'fr',
	reminderConsent: false,
	duplicates: 'skip'
});

/** Every field of `kind`, taken from `suggested` (the upload answer suggests fields of both kinds), else null. */
export function mappingFor(kind: ImportKind, suggested: Record<string, number | null | undefined>): ImportMapping {
	return Object.fromEntries(FIELDS[kind].map((f) => [f, typeof suggested[f] === 'number' ? (suggested[f] as number) : null]));
}

export type MissingField = 'name' | 'phone' | 'when';

export function missingRequired(kind: ImportKind, mapping: ImportMapping): MissingField[] {
	const has = (f: string) => typeof mapping[f] === 'number';
	const missing: MissingField[] = [];
	if (!(has('fullName') || (has('lastName') && has('firstName')))) missing.push('name');
	if (kind === 'patients' && !has('phone')) missing.push('phone');
	if (kind === 'appointments' && !(has('datetime') || (has('date') && has('time')))) missing.push('when');
	return missing;
}

/** Column indexes chosen for more than one field (allowed, but usually a mistake). */
export function sharedColumns(mapping: ImportMapping): number[] {
	const seen = new Map<number, number>();
	for (const index of Object.values(mapping)) if (typeof index === 'number') seen.set(index, (seen.get(index) ?? 0) + 1);
	return [...seen].filter(([, n]) => n > 1).map(([i]) => i);
}

/** "A", "B", … "AA" – the Excel name of a column index. */
export function columnLetter(index: number): string {
	let n = index + 1;
	let name = '';
	while (n > 0) {
		const r = (n - 1) % 26;
		name = String.fromCharCode(65 + r) + name;
		n = Math.floor((n - 1) / 26);
	}
	return name;
}
