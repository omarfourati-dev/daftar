/**
 * The change log of stock and hygiene in words (spec stock-hygiène 8, review M3): who changed, corrected or deleted
 * what, when, old → new – never a raw code. Backend: daftar/audit.py (`GET /api/audit-log?entity=a,b`); an update
 * names its object in `before` (product, supplier, task, equipment …) and holds only the new values in `after`.
 */
import { money } from './agenda/format';
import { displayPhone } from './agenda/links';
import { kindLabel, weekdayName } from './hygiene';
import { formatDateTime, formatDay, t, translate } from './i18n.svelte';
import { categoryLabel, unitLabel } from './stock';
import type { EquipmentKind } from './types/hygiene';
import type { StockCategory, StockUnit } from './types/stock';

export type AuditAction = 'create' | 'update' | 'delete';

export interface AuditEntry {
	id: number;
	at: string;
	userName: string;
	entity: string;
	entityId: number;
	action: AuditAction;
	before: Record<string, unknown> | null;
	after: Record<string, unknown> | null;
	reason: string;
}

/** What each page asks for: its own entities only. */
export const STOCK_ENTITIES = 'stock_receipt,stock_receipt_line,stock_movement,stock_product,supplier';
export const HYGIENE_ENTITIES = 'hygiene_task,equipment,hygiene_task_done,sterilization_cycle,sterile_pack_use,label_settings';

const isEmpty = (value: unknown) => value === null || value === undefined || value === '';
const str = (value: unknown) => String(value ?? '');

/** A value as people read it: labels instead of codes, dates and amounts formatted. */
const FORMAT: Record<string, (value: unknown) => string> = {
	active: (v) => t(v ? 'audit.yes' : 'audit.no'),
	category: (v) => categoryLabel(v as StockCategory),
	unit: (v) => unitLabel(v as StockUnit),
	frequency: (v) => translate(`hygiene.frequencies.${str(v)}`) ?? str(v),
	weekday: (v) => weekdayName(v as number),
	startsOn: (v) => formatDay(str(v)),
	kind: (v) => kindLabel(v as EquipmentKind),
	unitPriceMillimes: (v) => money(Number(v)),
	phone: (v) => displayPhone(str(v)),
	whatsapp: (v) => displayPhone(str(v)),
	result: (v) => t(v === 'not_ok' ? 'hygiene.today.resultNotOk' : 'hygiene.today.resultOk'),
	formatSterile: (v) => translate(`labels.formats.${str(v)}`) ?? str(v),
	formatSpecimen: (v) => translate(`labels.formats.${str(v)}`) ?? str(v),
	shelfLifeSachet: (v) => t('audit.days', { count: Number(v) }),
	shelfLifeDoubleSachet: (v) => t('audit.days', { count: Number(v) }),
	shelfLifeConteneur: (v) => t('audit.days', { count: Number(v) }),
	shelfLifeChamp: (v) => t('audit.days', { count: Number(v) })
};

export function auditValue(field: string, value: unknown): string {
	if (isEmpty(value)) return t('audit.none');
	return (FORMAT[field] ?? str)(value);
}

/** "Seuil de commande : 4 → 6", one line per changed field of an update. */
export function auditChanges(entry: AuditEntry): string[] {
	if (entry.action !== 'update' || !entry.after) return [];
	const before = entry.before ?? {};
	return Object.entries(entry.after).map(([field, value]) =>
		t('audit.change', {
			field: translate(`audit.fields.${field}`) ?? field,
			before: auditValue(field, before[field]),
			after: auditValue(field, value)
		})
	);
}

/** "30/10/2026 10:20 – Nisrine a modifié la tâche « Purge »". */
export function auditSummary(entry: AuditEntry): string {
	const b = entry.before ?? {};
	const params: Record<string, string | number> = {
		name: str(b.product ?? b.supplier ?? b.task ?? b.equipment ?? b.name ?? b.title),
		product: str(b.product),
		date: b.receivedOn || b.dueOn ? formatDay(str(b.receivedOn ?? b.dueOn)) : '',
		total: money(Number(b.totalMillimes ?? 0)),
		kind: translate(`stock.movements.kinds.${str(b.kind)}`) ?? '',
		quantity: Math.abs(Number(b.quantity ?? 0)),
		by: str(b.doneBy),
		cycle: str(b.cycle),
		code: str(b.code),
		patient: str(b.patient)
	};
	const what = translate(`audit.what.${entry.entity}.${entry.action}`, params) ?? t('audit.what.other');
	return t('audit.entry', { date: formatDateTime(entry.at), user: entry.userName, what });
}
