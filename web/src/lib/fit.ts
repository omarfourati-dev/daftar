/**
 * `use:fit={{ max: 9 }}` – a label line that may wrap (content of a pack, name of a patient) gets smaller, half a
 * point at a time, until it fits its box – never below 7 pt (spec stock-hygiène 7). If it still does not fit,
 * `data-overflow="true"` marks it, and the label page asks to shorten the text instead of printing it cut off.
 */
export interface FitOptions {
	max: number;
	min?: number;
	/** Anything that changes the text or the box (format, content) – a new value fits again. */
	key?: unknown;
}

const overflowing = (node: HTMLElement) => node.scrollHeight > node.clientHeight + 1 || node.scrollWidth > node.clientWidth + 1;

export function fit(node: HTMLElement, options: FitOptions) {
	let current = options;
	function run() {
		const min = current.min ?? 7;
		let size = current.max;
		node.style.fontSize = `${size}pt`;
		while (overflowing(node) && size > min) {
			size = Math.max(min, size - 0.5);
			node.style.fontSize = `${size}pt`;
		}
		node.dataset.overflow = String(overflowing(node));
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
