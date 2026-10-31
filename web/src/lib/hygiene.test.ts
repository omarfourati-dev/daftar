import { beforeEach, describe, expect, it } from 'vitest';
import { ApiError } from './api';
import { i18n } from './i18n.svelte';
import { dueText, frequencyText, hygieneError } from './hygiene';
import type { HygieneItem } from './types/hygiene';

const base = { weekday: null, intervalDays: null, startsOn: '2026-01-15' } as const;

describe('hygiene helpers', () => {
	beforeEach(() => i18n.setLocale('fr'));

	it('says the rhythm of a task in words', () => {
		expect(frequencyText({ ...base, frequency: 'daily' })).toBe('Chaque jour d’ouverture');
		expect(frequencyText({ ...base, frequency: 'weekly', weekday: 1 })).toBe('Chaque lundi');
		expect(frequencyText({ ...base, frequency: 'monthly' })).toBe('Chaque mois, le 15');
		expect(frequencyText({ ...base, frequency: 'yearly' })).toBe('Chaque année, le 15/01');
		expect(frequencyText({ ...base, frequency: 'every_n_days', intervalDays: 10 })).toBe('Tous les 10 jours');
		i18n.setLocale('ar');
		expect(frequencyText({ ...base, frequency: 'weekly', weekday: 5 })).toBe('كل جمعة');
	});

	it('says when an item is due', () => {
		const item = { dueOn: '2026-10-26', state: 'overdue' } as HygieneItem;
		expect(dueText(item)).toBe('En retard depuis le 26/10/2026');
		expect(dueText({ ...item, dueOn: '2026-10-30', state: 'due' })).toBe('À faire aujourd’hui');
	});

	it('translates the errors of the hygiene endpoints', () => {
		expect(hygieneError(new ApiError(409, 'x', 'already_done'))).toBe('Quelqu’un l’a déjà marquée comme faite.');
		expect(hygieneError(new ApiError(403, 'x', 'forbidden'))).toBe('Vous n’avez pas accès à cette action.');
	});
});
