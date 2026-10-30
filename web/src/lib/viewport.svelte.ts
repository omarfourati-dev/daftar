/**
 * `viewport.narrow` – true on phones (< 768 px, Tailwind `md`). Pages render one layout or the other (e.g. the
 * agenda list instead of the grid) instead of hiding a duplicate with CSS. Tests set `viewport.narrow` directly.
 */
class Viewport {
	narrow = $state(false);

	constructor() {
		const query = globalThis.matchMedia?.('(max-width: 767px)');
		if (!query) return;
		this.narrow = query.matches;
		query.addEventListener?.('change', (e) => (this.narrow = e.matches));
	}
}

export const viewport = new Viewport();
