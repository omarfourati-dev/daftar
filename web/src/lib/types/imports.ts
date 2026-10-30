/** Excel/CSV import (section 14). */
export type ImportKind = 'patients' | 'appointments';
export type DuplicateRule = 'skip' | 'update' | 'create';
export type NameOrder = 'last_first' | 'first_last';
export type DateFormat = 'auto' | 'dmy' | 'ymd' | 'mdy';

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
	/** 1-based row that holds the column titles; 0 = the file has no title row (booleans are accepted too) */
	headerRow: number | boolean;
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
}

export type ImportMapping = Record<string, number | null>;

/** `POST /api/imports/{id}/preview` */
export interface ImportPreview {
	willCreate: number;
	willUpdate: number;
	willSkip: number;
	errors: { row: number; field: string; message: string }[];
	duplicates: { row: number; patientId: number; name: string }[];
	sample: Record<string, unknown>[];
}

/** `POST /api/imports/{id}/commit` */
export interface ImportResult {
	created: number;
	updated: number;
	skipped: number;
	errorCount: number;
}

/** `GET/POST /api/import-templates` */
export interface ImportTemplate {
	id: number;
	name: string;
	kind: ImportKind;
	mapping: ImportMapping;
	options: ImportOptions;
}
