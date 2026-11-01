/**
 * Labels on real printers (spec stock-hygiène 7): the three formats with their page, label and safe area in
 * millimetres, the A4 sheet with its start position, what each kind of label says, error texts.
 *
 * - `roll62`: Brother QL, 62 mm roll cut at 29 mm (also the DK-11209 die-cut labels) – one label per page.
 * - `label57x32`: Dymo 11354 / Zebra 57 × 32 mm – one label per page.
 * - `a4_3x8`: A4 sheet of 24 labels 70 × 37 mm (3 × 8, no margin; 0.5 mm left at top and bottom); printing starts at
 *   any position, so a started sheet is used up. The next free position is remembered on this device.
 *
 * The safe area keeps text and QR away from the edges printers cannot reach (2–2.5 mm on label printers, 4–5 mm on
 * office printers). Text is at least 7 pt, black on white; codes and dates are always left to right.
 */
import { ApiError, apiErrorMessage } from './api';
import { formatDate, formatDay, formatTime, i18n, t, translate } from './i18n.svelte';
import type { Cycle, LabelFormat, Pack, Packaging, SpecimenKind, SpecimenPrint } from './types/labels';

export const FORMATS: readonly LabelFormat[] = ['roll62', 'label57x32', 'a4_3x8'];
export const PACKAGINGS: readonly Packaging[] = ['sachet', 'double_sachet', 'conteneur', 'champ'];
export const SPECIMEN_KINDS: readonly SpecimenKind[] = ['edta', 'sec', 'citrate', 'heparine', 'urine', 'selles', 'frottis', 'autre'];
export const SHEET_SLOTS = 24;

export interface FormatSpec {
	/** Paper of one printed page, mm. */
	page: [number, number];
	/** One label, mm. */
	label: [number, number];
	/** Safe area: inline and block padding inside a label, mm. */
	pad: [number, number];
	/** QR code side (with its quiet zone) on sterilisation and on specimen labels, mm. */
	qr: { sterile: number; specimen: number };
	/** A4 sheet: columns, rows and the space above the first row, mm. */
	sheet?: { cols: number; rows: number; top: number };
}

export const FORMAT_SPECS: Record<LabelFormat, FormatSpec> = {
	roll62: { page: [62, 29], label: [62, 29], pad: [2.5, 2], qr: { sterile: 17, specimen: 14 } },
	label57x32: { page: [57, 32], label: [57, 32], pad: [2, 2], qr: { sterile: 18, specimen: 15 } },
	a4_3x8: { page: [210, 297], label: [70, 37], pad: [5, 4], qr: { sterile: 19, specimen: 16 }, sheet: { cols: 3, rows: 8, top: 0.5 } }
};

export const isFormat = (value: unknown): value is LabelFormat => FORMATS.includes(value as LabelFormat);

/** The `@page` rules of a format: a named page (wins over the plain `@page` of other print pages) and a plain one. */
export function pageCss(format: LabelFormat): string {
	const [w, h] = FORMAT_SPECS[format].page;
	const size = `size:${w}mm ${h}mm;margin:0`;
	return `@page daftar-label{${size}}@page{${size}}`;
}

/** A4: the labels on sheets of 24, empty (`null`) before the start position of the first sheet. */
export function sheets<T>(labels: T[], start: number): (T | null)[][] {
	const slots: (T | null)[] = [...Array<null>(Math.max(0, start - 1)).fill(null), ...labels];
	const pages: (T | null)[][] = [];
	for (let i = 0; i < slots.length; i += SHEET_SLOTS) pages.push(slots.slice(i, i + SHEET_SLOTS));
	return pages.map((page) => [...page, ...Array<null>(SHEET_SLOTS - page.length).fill(null)]);
}

/** The first free position after printing `count` labels from `start` (1 again when the sheet is full). */
export const nextStart = (start: number, count: number) => ((start - 1 + count) % SHEET_SLOTS) + 1;

const START_KEY = 'daftar.labels.sheetStart';

export function readStart(): number {
	try {
		const value = Number(localStorage.getItem(START_KEY));
		return Number.isInteger(value) && value >= 1 && value <= SHEET_SLOTS ? value : 1;
	} catch {
		return 1;
	}
}

export function saveStart(position: number) {
	try {
		localStorage.setItem(START_KEY, String(position));
	} catch {
		/* private mode: the sheet starts at 1 next time */
	}
}

// --- what a label says ---------------------------------------------------------------------------------------------

export interface SterileLabel {
	kind: 'sterile';
	code: string;
	practice: string;
	content: string;
	sterilizedOn: string;
	useBefore: string;
	/** The autoclave's label code (A1); its name is in the register. */
	autoclave: string;
	initials: string;
}

export interface SpecimenLabel {
	kind: 'specimen';
	code: string;
	practice: string;
	/** NOM Prénom – the family name in capitals, as labs read it. */
	name: string;
	birth: string;
	fileNo: string;
	specimen: string;
	collected: string;
}

export interface TestLabel {
	kind: 'test';
	code: string;
	position: number;
}

export type LabelData = SterileLabel | SpecimenLabel | TestLabel;

/** "TRABELSI Sami"; Arabic names stay as they are written. */
export const labelName = (first: string, last: string) => `${last.toLocaleUpperCase('fr')} ${first}`.trim();

/** A date or time on a label: without the bidi marks of the Arabic format, and – in Arabic text – isolated left to
 * right, so "30/01/2027" never turns into "302027/01/". */
export function labelDate(text: string): string {
	const plain = text.replace(/[‎‏؜]/g, '');
	return i18n.dir === 'rtl' ? `⁦${plain}⁩` : plain;
}

export function birthText(patient: { birthDate: string | null; birthYear: number | null }): string {
	if (patient.birthDate) return t('labels.specimen.bornOn', { date: labelDate(formatDay(patient.birthDate)) });
	if (patient.birthYear) return t('labels.specimen.bornIn', { year: patient.birthYear });
	return '';
}

export const specimenName = (kind: SpecimenKind, label = '') => (kind === 'autre' && label ? label : (translate(`labels.kinds.${kind}`) ?? kind));

/** The packs a cycle's label page offers first: those still to use (a reprint chooses others by hand). */
export const printable = (pack: Pack) => pack.state === 'usable';

export function sterileLabels(cycle: Cycle, packs: Pack[], practice: string): SterileLabel[] {
	return packs.map((p) => ({
		kind: 'sterile',
		code: p.code,
		practice,
		content: p.content,
		sterilizedOn: labelDate(formatDate(cycle.runAt)).replace(/[⁦⁩]/g, ''),
		useBefore: labelDate(formatDay(p.expiresOn)).replace(/[⁦⁩]/g, ''),
		autoclave: cycle.labelCode,
		initials: cycle.initials
	}));
}

export function specimenLabels(print: SpecimenPrint, practice: string): SpecimenLabel[] {
	const collected = labelDate(`${formatDate(print.collectedAt)} ${formatTime(print.collectedAt)}`);
	return print.labels.map((l) => ({
		kind: 'specimen',
		code: l.code,
		practice,
		name: labelName(print.patient.firstName, print.patient.lastName),
		birth: birthText(print.patient),
		fileNo: String(print.patient.id),
		specimen: specimenName(l.kind, l.label),
		collected: print.collectedBy ? t('labels.specimen.collectedBy', { when: collected, by: initialsOf(print.collectedBy) }) : t('labels.specimen.collected', { when: collected })
	}));
}

const TITLES = new Set(['dr', 'dr.', 'pr', 'pr.', 'docteur', 'prof', 'prof.', 'mme', 'm.', 'mr', 'mr.', 'د', 'د.']);

/** "Dr. Amira Ben Salem" → "ABS" (as the server prints the initials of a cycle). */
export function initialsOf(name: string): string {
	return name
		.split(/\s+/)
		.filter((w) => w && !TITLES.has(w.toLowerCase()))
		.map((w) => w[0])
		.join('')
		.slice(0, 3)
		.toLocaleUpperCase('fr');
}

/** Error texts of the labels and the traceability, with the dates the server sends along. */
export function labelsError(err: unknown): string {
	if (err instanceof ApiError && err.code) {
		const body = (err.body ?? {}) as Record<string, unknown>;
		const params: Record<string, string> = {};
		if (typeof body.expiresOn === 'string') params.date = formatDay(body.expiresOn);
		if (typeof body.usedAt === 'string') params.date = formatDate(body.usedAt);
		if (typeof body.patientName === 'string') params.patient = body.patientName;
		const own = translate(`labels.errors.${err.code}`, params);
		if (own) return own;
	}
	return apiErrorMessage(err);
}
