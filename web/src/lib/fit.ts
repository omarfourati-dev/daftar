/**
 * `use:fit={{ max: 9, text: label.content }}` – a label line that may wrap (content of a pack, name of a patient):
 * the action writes the text and makes it smaller, half a point at a time, until it fits its box – never below 7 pt
 * (spec stock-hygiène 7). `text` may give shorter forms to try in turn (a name with the first names as initials), the
 * next one only when the one before does not fit even at 7 pt. If the last one still does not fit, it stays whole in
 * the box (cut off at its edge), `data-overflow="true"` marks it and `onfit` says how many characters are too many – the
 * label page warns before printing instead of shortening it silently (review M6).
 */
export interface FitOptions {
	max: number;
	min?: number;
	/** The text, or its forms from the longest to the shortest. */
	text: string | string[];
	/** Anything else that changes the box (the format) – a new value fits again. */
	key?: unknown;
	/** After every fitting: what is shown and how much of it does not fit. */
	onfit?: (result: FitResult) => void;
}

export interface FitResult {
	/** The form shown (the last one tried when none fits). */
	text: string;
	/** Its place in `text` (0: the full text). */
	index: number;
	/** Characters that do not fit even at the smallest size (0: everything fits). */
	excess: number;
	/** The font size in points. */
	size: number;
}

/**
 * Lines hidden or cut: the box scrolls by more than the font's own ascent and descent stick out of its line boxes
 * (IBM Plex Sans Arabic keeps room for Arabic marks above and below – about a third of the size).
 */
function overflowing(node: HTMLElement): boolean {
	const slack = 0.35 * (parseFloat(getComputedStyle(node).fontSize) || 0) + 1;
	return node.scrollHeight > node.clientHeight + slack || node.scrollWidth > node.clientWidth + 1;
}

function shrink(node: HTMLElement, max: number, min: number): number {
	let size = max;
	node.style.fontSize = `${size}pt`;
	while (overflowing(node) && size > min) {
		size = Math.max(min, size - 0.5);
		node.style.fontSize = `${size}pt`;
	}
	return size;
}

/** How many characters of `text` fit the box at its current size (the longest start that does). */
function fitting(node: HTMLElement, text: string): number {
	let fits = 0;
	let over = text.length;
	while (over - fits > 1) {
		const mid = Math.floor((fits + over) / 2);
		node.textContent = text.slice(0, mid);
		if (overflowing(node)) over = mid;
		else fits = mid;
	}
	node.textContent = text;
	return fits;
}

export function fit(node: HTMLElement, options: FitOptions) {
	let current = options;
	function run() {
		const min = current.min ?? 7;
		const all = Array.isArray(current.text) ? current.text : [current.text];
		const forms = all.filter((form, i) => i === 0 || form !== all[i - 1]);
		let index = 0;
		let size = current.max;
		for (; index < forms.length; index++) {
			node.textContent = forms[index];
			size = shrink(node, current.max, min);
			if (!overflowing(node) || index === forms.length - 1) break;
		}
		const text = forms[index];
		const excess = overflowing(node) ? text.length - fitting(node, text) : 0;
		node.dataset.overflow = String(excess > 0);
		current.onfit?.({ text, index, excess, size });
	}
	run();
	void document.fonts?.ready.then(run);
	return {
		update(next: FitOptions) {
			current = next;
			run();
		}
	};
}
