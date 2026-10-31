/** Helpers of the hygiene pages (spec stock-hygiène 5): the rhythm in words, when an item is due, error texts. */
import { ApiError, apiErrorMessage } from './api';
import { formatDay, t, translate } from './i18n.svelte';
import type { EquipmentKind, Frequency, HygieneItem, HygieneTask } from './types/hygiene';

export const FREQUENCIES: readonly Frequency[] = ['daily', 'weekly', 'monthly', 'yearly', 'every_n_days'];
export const KINDS: readonly EquipmentKind[] = ['autoclave', 'thermodesinfecteur', 'ultrasons', 'compresseur', 'aspiration', 'fauteuil', 'radiographie', 'autre'];
export const WEEKDAYS = ['1', '2', '3', '4', '5', '6', '7'] as const;

export function weekdayName(day: number | string): string {
	return translate(`hygiene.weekdays.${day}`) ?? String(day);
}

export function kindLabel(kind: EquipmentKind): string {
	return translate(`hygiene.kinds.${kind}`) ?? kind;
}

/** "Chaque lundi", "Chaque mois, le 15", "Tous les 10 jours" … */
export function frequencyText(task: Pick<HygieneTask, 'frequency' | 'weekday' | 'intervalDays' | 'startsOn'>): string {
	const [, month, day] = task.startsOn.split('-');
	switch (task.frequency) {
		case 'weekly':
			return t('hygiene.frequency.weekly', { weekday: weekdayName(task.weekday ?? 1) });
		case 'monthly':
			return t('hygiene.frequency.monthly', { day: Number(day) });
		case 'yearly':
			return t('hygiene.frequency.yearly', { date: `${day}/${month}` });
		case 'every_n_days':
			return t('hygiene.frequency.every_n_days', { count: task.intervalDays ?? 0 });
		default:
			return t('hygiene.frequency.daily');
	}
}

export function dueText(item: Pick<HygieneItem, 'dueOn' | 'state'>): string {
	return item.state === 'overdue' ? t('hygiene.today.overdueSince', { date: formatDay(item.dueOn) }) : t('hygiene.today.dueToday');
}

export function hygieneError(err: unknown): string {
	if (err instanceof ApiError && err.code) {
		const own = translate(`hygiene.errors.${err.code}`);
		if (own) return own;
	}
	return apiErrorMessage(err);
}
