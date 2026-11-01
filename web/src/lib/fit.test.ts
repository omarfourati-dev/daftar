import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fit, type FitResult } from './fit';

/**
 * A fake layout (jsdom has none): the box holds `capacity(pt)` characters at a font size – fewer when bigger.
 * Anything longer overflows it, as a label line that wraps once too often.
 */
function box(capacity: (pt: number) => number): HTMLElement {
	const node = document.createElement('p');
	document.body.append(node);
	const size = () => parseFloat(node.style.fontSize) || 9;
	Object.defineProperty(node, 'clientHeight', { get: () => 20 });
	Object.defineProperty(node, 'scrollHeight', { get: () => ((node.textContent ?? '').length > capacity(size()) ? 60 : 20) });
	Object.defineProperty(node, 'clientWidth', { get: () => 100 });
	Object.defineProperty(node, 'scrollWidth', { get: () => 100 });
	return node;
}

const SIXTY = 'Kit extraction chirurgicale complet + élévateurs + davier 17';
const NAME = 'BEN HADJ ABDALLAH EL OUERGHEMMI BOUZOUITA Mohamed Amine Fatma Zahra Wijden';
const INITIALS = 'BEN HADJ ABDALLAH EL OUERGHEMMI BOUZOUITA M. A. F. Z. W.';

describe('use:fit – smaller first, never below 7 pt, then it says how much is too long (review M6)', () => {
	let results: FitResult[];
	const onfit = (r: FitResult) => results.push(r);
	beforeEach(() => (results = []));
	afterEach(() => document.body.replaceChildren());

	it('writes the text and keeps the biggest size it fits in', () => {
		const node = box((pt) => Math.floor(280 / pt)); // 31 characters at 9 pt, 40 at 7 pt
		fit(node, { max: 9, text: 'Kit examen', onfit });
		expect(node.textContent).toBe('Kit examen');
		expect(node.style.fontSize).toBe('9pt');
		expect(node.dataset.overflow).toBe('false');
		expect(results.at(-1)).toEqual({ text: 'Kit examen', index: 0, excess: 0, size: 9 });
	});

	it('shrinks half a point at a time down to 7 pt', () => {
		const node = box((pt) => Math.floor(280 / pt));
		fit(node, { max: 9, text: 'Kit extraction chirurgicale 35', onfit }); // 30 characters
		expect(node.style.fontSize).toBe('9pt');
		fit(node, { max: 9, text: 'Kit extraction chirurgicale complet 1', onfit }); // 37: 280/7.5 = 37
		expect(node.style.fontSize).toBe('7.5pt');
	});

	it('a 60-character content that does not fit at 7 pt: shown whole, marked, 20 characters too many', () => {
		const node = box((pt) => Math.floor(280 / pt));
		expect(SIXTY).toHaveLength(60);
		fit(node, { max: 9, text: SIXTY, onfit });
		expect(node.textContent).toBe(SIXTY); // never shortened by the action
		expect(node.style.fontSize).toBe('7pt');
		expect(node.dataset.overflow).toBe('true');
		expect(results.at(-1)).toEqual({ text: SIXTY, index: 0, excess: 20, size: 7 });
	});

	it('a 74-character name: the family name stays whole, the first names become initials', () => {
		expect(NAME).toHaveLength(74);
		const node = box(() => 60); // 60 characters at any size
		fit(node, { max: 9.5, text: [NAME, INITIALS], onfit });
		expect(node.textContent).toBe(INITIALS);
		expect(node.dataset.overflow).toBe('false');
		expect(results.at(-1)).toMatchObject({ text: INITIALS, index: 1, excess: 0 });
	});

	it('a name too long even with initials: the shortest form, marked with what is too much', () => {
		const node = box(() => 50);
		fit(node, { max: 9.5, text: [NAME, INITIALS], onfit });
		expect(node.textContent).toBe(INITIALS);
		expect(results.at(-1)).toMatchObject({ text: INITIALS, index: 1, excess: INITIALS.length - 50 });
	});

	it('fits again when the text or the format changes, and again once the fonts are there', async () => {
		const node = box((pt) => Math.floor(280 / pt));
		const action = fit(node, { max: 9, text: SIXTY, onfit });
		action.update({ max: 9, text: 'Kit examen', onfit });
		expect(node.textContent).toBe('Kit examen');
		expect(results.at(-1)?.excess).toBe(0);
		const spy = vi.fn();
		action.update({ max: 9, text: 'Kit examen', onfit: spy });
		expect(spy).toHaveBeenCalledOnce();
	});
});
