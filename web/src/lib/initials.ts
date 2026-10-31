/**
 * One or two Latin initials of a practice – the same rule as its app icon (backend daftar/branding.py), so the
 * booking page and the poster show what the installed app shows.
 */
const GENERIC = new Set(['cabinet', 'centre', 'clinique', 'polyclinique', 'dr', 'dr.', 'docteur', 'dentaire', 'medical', 'médical', 'medicale', 'médicale', 'de', 'du', 'des']);
const ARTICLES = new Set(['el', 'la', 'le', 'les', 'l', 'd', 'et', '&']);

const latin = (word: string) =>
	word
		.normalize('NFKD')
		.replace(/[^\x00-\x7f]/g, '')
		.toLowerCase()
		.replace(/[^a-z0-9]/g, '');

export function initials(name: string): string {
	const all = name.split(/\s+/).filter(Boolean);
	const kept = all.filter((w) => !GENERIC.has(w.toLowerCase()));
	const words = (kept.length ? kept : all)
		.filter((w) => !ARTICLES.has(w.toLowerCase()))
		.map(latin)
		.filter(Boolean);
	if (!words.length) return 'D';
	if (words.length === 1) return words[0][0].toUpperCase();
	return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}
