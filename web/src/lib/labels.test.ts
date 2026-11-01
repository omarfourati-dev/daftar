import jsQR from 'jsqr';
import { beforeEach, describe, expect, it } from 'vitest';
import { ApiError } from './api';
import { i18n } from './i18n.svelte';
import {
	FORMAT_SPECS,
	birthText,
	initialsOf,
	labelName,
	labelsError,
	nextStart,
	pageCss,
	readStart,
	saveStart,
	sheets,
	specimenLabels,
	sterileLabels
} from './labels';
import { QUIET_ZONE, qrPath } from './components/labels/LabelQr.svelte';
import type { Cycle, SpecimenPrint } from './types/labels';

const cycle: Cycle = {
	id: 3, equipmentId: 1, equipmentName: 'Autoclave Melag', labelCode: 'A1', number: 412, runAt: '2026-10-30T07:45:00+01:00',
	program: '134 °C – 18 min', result: 'ok', packCount: 1, note: '', performedBy: 'Nisrine Hamza', initials: 'NH',
	createdAt: '2026-10-30T07:46:00+01:00',
	packs: [{ id: 9, seq: 7, code: 'A1-0412-07', content: 'Kit extraction', packaging: 'sachet', expiresOn: '2027-01-28', state: 'usable', use: null }]
};
const print: SpecimenPrint = {
	id: 1042, patient: { id: 77, firstName: 'Sami', lastName: 'Trabelsi', birthDate: '1978-03-12', birthYear: 1978 }, appointmentId: null,
	items: [{ kind: 'edta', count: 1, label: '' }, { kind: 'autre', count: 1, label: 'Liquide pleural' }], labelCount: 2,
	labels: [{ code: 'E1042-01', kind: 'edta', label: '' }, { code: 'E1042-02', kind: 'autre', label: 'Liquide pleural' }],
	collectedAt: '2026-10-30T09:42:00+01:00', collectedBy: 'Dr. Amira Ben Salem', printedBy: 'Nisrine', printedAt: '2026-10-30T09:43:00+01:00'
};

describe('labels on real printers (spec stock-hygiène 7)', () => {
	beforeEach(() => i18n.setLocale('fr'));

	it('knows the paper of each format and keeps a safe area', () => {
		expect(pageCss('roll62')).toBe('@page daftar-label{size:62mm 29mm;margin:0}@page{size:62mm 29mm;margin:0}');
		expect(pageCss('label57x32')).toContain('size:57mm 32mm');
		expect(pageCss('a4_3x8')).toContain('size:210mm 297mm');
		const a4 = FORMAT_SPECS.a4_3x8;
		expect(a4.sheet!.cols * a4.label[0]).toBe(210);
		expect(a4.sheet!.rows * a4.label[1] + 2 * a4.sheet!.top).toBe(297);
		for (const spec of Object.values(FORMAT_SPECS)) {
			// the QR code and the text both fit between the paddings
			expect(spec.qr.sterile).toBeLessThanOrEqual(spec.label[1] - 2 * spec.pad[1]);
			expect(spec.pad[0]).toBeGreaterThanOrEqual(2);
		}
	});

	it('fills an A4 sheet from the first free position and remembers the next one', () => {
		const pages = sheets(['a', 'b', 'c'], 23);
		expect(pages).toHaveLength(2);
		expect(pages[0].slice(20)).toEqual([null, null, 'a', 'b']);
		expect(pages[1][0]).toBe('c');
		expect(pages[1].filter(Boolean)).toHaveLength(1);
		expect(sheets([], 1)).toEqual([]);
		expect(nextStart(23, 3)).toBe(2);
		expect(nextStart(1, 24)).toBe(1);
		localStorage.clear();
		expect(readStart()).toBe(1);
		saveStart(11);
		expect(readStart()).toBe(11);
		localStorage.setItem('daftar.labels.sheetStart', '99');
		expect(readStart()).toBe(1);
	});

	it('writes what a sterilisation label says', () => {
		expect(sterileLabels(cycle, cycle.packs, 'Cabinet du Lac')).toEqual([
			{ kind: 'sterile', code: 'A1-0412-07', practice: 'Cabinet du Lac', content: 'Kit extraction', sterilizedOn: '30/10/2026', useBefore: '28/01/2027', autoclave: 'A1', initials: 'NH' }
		]);
	});

	it('writes NOM Prénom, the birth date or year and the specimen on a specimen label', () => {
		expect(labelName('Sami', 'Ben Salah')).toBe('BEN SALAH Sami');
		expect(labelName('سامي', 'الطرابلسي')).toBe('الطرابلسي سامي');
		expect(birthText({ birthDate: '1978-03-12', birthYear: 1978 })).toBe('Né(e) le 12/03/1978');
		expect(birthText({ birthDate: null, birthYear: 2015 })).toBe('Né(e) en 2015');
		expect(birthText({ birthDate: null, birthYear: null })).toBe('');
		const [edta, other] = specimenLabels(print, 'Cabinet du Lac');
		expect(edta).toEqual({
			kind: 'specimen', code: 'E1042-01', practice: 'Cabinet du Lac', name: 'TRABELSI Sami', birth: 'Né(e) le 12/03/1978', fileNo: '77',
			specimen: 'Sang EDTA', collected: 'Prél. le 30/10/2026 09:42 – ABS'
		});
		expect(other.specimen).toBe('Liquide pleural');
		expect(initialsOf('Nisrine Hamza')).toBe('NH');
		expect(initialsOf('Dr Fadoua')).toBe('F');
	});

	it('explains a refused pack with its date and patient', () => {
		const expired = new ApiError(422, 'x', 'pack_expired', { code: 'pack_expired', expiresOn: '2026-10-29' });
		expect(labelsError(expired)).toBe('Paquet périmé (à utiliser avant le 29/10/2026) : ne l’utilisez pas, restérilisez-le.');
		const used = new ApiError(409, 'x', 'pack_used', { code: 'pack_used', patientName: 'Sami Trabelsi', usedAt: '2026-10-30T09:00:00+01:00' });
		expect(labelsError(used)).toBe('Ce paquet est déjà noté pour Sami Trabelsi (le 30/10/2026).');
		i18n.setLocale('ar');
		expect(labelsError(new ApiError(422, 'x', 'pack_not_sterile'))).toContain('غير معقّمة');
	});
});

describe('the QR code of a label', () => {
	it('reads back as the code, with the full quiet zone', () => {
		const { size, path } = qrPath('A1-0412-07');
		expect(size).toBe(21 + 2 * QUIET_ZONE); // version 1: a short alphanumeric code stays coarse and easy to scan
		const scale = 6;
		const width = size * scale;
		const pixels = new Uint8ClampedArray(width * width * 4).fill(255);
		for (const [, x, y, w] of path.matchAll(/M(\d+) (\d+)h(\d+)/g)) {
			for (let dy = 0; dy < scale; dy++)
				for (let dx = 0; dx < Number(w) * scale; dx++) {
					const i = ((Number(y) * scale + dy) * width + Number(x) * scale + dx) * 4;
					pixels[i] = pixels[i + 1] = pixels[i + 2] = 0;
				}
		}
		// nothing dark in the quiet zone
		for (const [, x, y] of path.matchAll(/M(\d+) (\d+)/g)) {
			expect(Number(x)).toBeGreaterThanOrEqual(QUIET_ZONE);
			expect(Number(y)).toBeGreaterThanOrEqual(QUIET_ZONE);
		}
		expect(jsQR(pixels, width, width)?.data).toBe('A1-0412-07');
	});
});
