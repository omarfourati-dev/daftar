import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { DEFAULT_CATALOGS, DEMO_SPECIALTIES, SPECIALTIES, catalogFor } from './catalog';

/** Reads the catalog constant of the backend (the source of truth) so both never drift apart. */
function backendCatalogs(): Record<string, [string, string, number, boolean][]> {
	const source = readFileSync(resolve(process.cwd(), '../backend/daftar/catalog.py'), 'utf8');
	const constants = Object.fromEntries([...source.matchAll(/^(\w+_AR) = "([^"]+)"\r?$/gm)].map((m) => [m[1], m[2]]));
	const result: Record<string, [string, string, number, boolean][]> = {};
	let current = '';
	for (const line of source.split(/\r?\n/)) {
		const head = line.match(/^ {4}"(\w+)": \($/);
		if (head) current = head[1];
		const item = line.match(/_i\("([^"]+)", (?:"([^"]+)"|(\w+)), (\d+), (True|False)\)/);
		if (item && current) (result[current] ??= []).push([item[1], item[2] ?? constants[item[3]], Number(item[4]), item[5] === 'True']);
	}
	return result;
}

describe('default service catalogs', () => {
	it('match the backend catalog of every specialty', () => {
		const backend = backendCatalogs();
		expect(Object.keys(backend)).toEqual([...SPECIALTIES]);
		for (const specialty of SPECIALTIES) {
			expect(
				DEFAULT_CATALOGS[specialty].map((s) => [s.nameFr, s.nameAr, s.durationMin, s.onlineBookable]),
				specialty
			).toEqual(backend[specialty]);
		}
	});

	it('gives a fresh, editable copy with empty prices', () => {
		const list = catalogFor('kinesitherapeute');
		expect(list).toEqual([
			{ nameFr: 'Séance', nameAr: 'حصّة', durationMin: 45, priceMillimes: null, onlineBookable: true },
			{ nameFr: 'Bilan', nameAr: 'تقييم', durationMin: 60, priceMillimes: null, onlineBookable: true }
		]);
		list[0].durationMin = 30;
		expect(catalogFor('kinesitherapeute')[0].durationMin).toBe(45);
	});

	it('offers five specialties for the demo', () => {
		expect(DEMO_SPECIALTIES).toEqual(['generaliste', 'dentiste', 'pediatre', 'kinesitherapeute', 'autre']);
	});
});
