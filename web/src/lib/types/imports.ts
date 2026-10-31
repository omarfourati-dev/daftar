/** Excel/CSV import (section 14). */
export type ImportKind = 'patients' | 'appointments';
export type DuplicateRule = 'skip' | 'update' | 'create';
export type NameOrder = 'last_first' | 'first_last';
export type DateFormat = 'dmy' | 'mdy' | 'ymd';

export interface ImportColumn {
	index: number;
	header: string;
	samples: string[];
}

/** `POST /api/imports` and `POST /api/imports/{id}/sheet` */
export interface ImportJob {
	id: string;
	filename: string;
	sheets: string[];
	sheet: string;
	/** 1-based row that holds the column titles; 0 = the file has no title row (columns are then "Colonne A…") */
	headerRow: number;
	columns: ImportColumn[];
	rowCount: number;
	suggestedMapping: Record<string, number | null>;
}

export interface ImportOptions {
	nameOrder: NameOrder;
	dateFormat: DateFormat;
	defaultLang: 'fr' | 'ar';
	reminderConsent: boolean;
	duplicates: DuplicateRule;
	/** appointments without duration or end time */
	defaultDurationMin?: number | null;
}

export type ImportMapping = Record<string, number | null>;

/** `POST /api/imports/{id}/preview` */
export interface ImportPreview {
	willCreate: number;
	willUpdate: number;
	willSkip: number;
	/** appointments import: patients that will be created on the way */
	willCreatePatients: number;
	errorCount: number;
	/** at most 500 */
	errors: { row: number; field: string; message: string; value: string }[];
	duplicates: { row: number; patientId: number | null; name: string }[];
	conflicts: { row: number; startsAt: string; message: string }[];
	sample: Record<string, unknown>[];
}

/** `POST /api/imports/{id}/commit` */
export interface ImportResult {
	created: number;
	updated: number;
	skipped: number;
	errorCount: number;
	patientsCreated: number;
}

/** `GET/POST /api/import-templates` */
export interface ImportTemplate {
	id: number;
	name: string;
	kind: ImportKind;
	mapping: ImportMapping;
	options: ImportOptions;
}
