import { describe, expect, it } from 'vitest';
import { appUrl, mainUrl, practiceUrl, telUrl, whatsappUrl } from './links';

const at = (href: string) => new URL(href);

describe('links', () => {
	it('builds the address of a practice from the main domain', () => {
		expect(practiceUrl('cabinet-lac', '/', at('https://daftar.omarfourati.de/app/admin'))).toBe('https://cabinet-lac.daftar.omarfourati.de/');
		expect(practiceUrl('cabinet-lac', '/invitation#abc', at('http://localhost:18085/app'))).toBe('http://cabinet-lac.localhost:18085/invitation#abc');
	});

	it('builds the address of a practice from another practice sub-domain', () => {
		expect(practiceUrl('cabinet-lac', '/app', at('https://autre.daftar.omarfourati.de/app'))).toBe('https://cabinet-lac.daftar.omarfourati.de/app');
		expect(practiceUrl('cabinet-lac', '/', at('http://cabinet-lac.localhost:5173/'))).toBe('http://cabinet-lac.localhost:5173/');
	});

	it('falls back to /r/<slug> for the booking page where sub-domains cannot work (IP addresses)', () => {
		expect(practiceUrl('cabinet-lac', '/', at('http://127.0.0.1:4173/app'))).toBe('http://127.0.0.1:4173/r/cabinet-lac');
		expect(practiceUrl('cabinet-lac', '/invitation#x', at('http://127.0.0.1:4173/app'))).toBe('http://127.0.0.1:4173/invitation#x');
	});

	it('builds the address of a practice from the app host (not <slug>.app.<base>)', () => {
		expect(practiceUrl('cabinet-lac', '/', at('https://app.daftar.omarfourati.de/app/admin'))).toBe('https://cabinet-lac.daftar.omarfourati.de/');
		expect(practiceUrl('cabinet-lac', '/invitation#abc', at('http://app.localhost:18083/app/admin'))).toBe(
			'http://cabinet-lac.localhost:18083/invitation#abc'
		);
	});

	it('builds addresses on the main domain, also from a practice sub-domain and the app host', () => {
		expect(mainUrl('/confidentialite/', at('https://cabinet-lac.daftar.omarfourati.de/app'))).toBe('https://daftar.omarfourati.de/confidentialite/');
		expect(mainUrl('/confidentialite/', at('http://localhost:18085/app'))).toBe('http://localhost:18085/confidentialite/');
		expect(mainUrl('/ar/confidentialite/', at('https://app.daftar.omarfourati.de/r/cabinet-lac'))).toBe('https://daftar.omarfourati.de/ar/confidentialite/');
	});

	it('builds addresses on the app host (waiting-room screen), from wherever the page runs', () => {
		expect(appUrl('/salle/tok', at('https://app.daftar.omarfourati.de/app/reglages/ecran'))).toBe('https://app.daftar.omarfourati.de/salle/tok');
		expect(appUrl('/salle/tok', at('https://cabinet-lac.daftar.omarfourati.de/app'))).toBe('https://app.daftar.omarfourati.de/salle/tok');
		expect(appUrl('/salle/tok', at('http://cabinet-lac.localhost:18083/app'))).toBe('http://app.localhost:18083/salle/tok');
		expect(appUrl('/salle/tok', at('http://127.0.0.1:4173/app'))).toBe('http://127.0.0.1:4173/salle/tok');
	});

	it('opens WhatsApp with a ready message, to a number or to any contact', () => {
		expect(whatsappUrl('Bonjour & merci', '+216 20 123 456')).toBe('https://wa.me/21620123456?text=Bonjour%20%26%20merci');
		expect(whatsappUrl('Lien : https://x.tn/a')).toBe('https://wa.me/?text=Lien%20%3A%20https%3A%2F%2Fx.tn%2Fa');
		expect(telUrl('+216 20 123 456')).toBe('tel:+21620123456');
	});

	it('completes numbers typed the Tunisian way (8 digits, 00216…)', () => {
		expect(whatsappUrl('x', '20 123 456')).toBe('https://wa.me/21620123456?text=x');
		expect(whatsappUrl('x', '0021620123456')).toBe('https://wa.me/21620123456?text=x');
		expect(telUrl('20123456')).toBe('tel:+21620123456');
	});
});
