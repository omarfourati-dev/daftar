import { describe, expect, it } from 'vitest';
import { displayPhone, millimesToInput, parseDinars, phoneDigits, smsUrl, telUrl, whatsappUrl } from './links';

describe('links to WhatsApp, SMS and phone', () => {
	it('builds wa.me links with the message (digits only, no plus)', () => {
		expect(phoneDigits('+216 20 123 456')).toBe('21620123456');
		expect(whatsappUrl('+21620123456', 'Bonjour Amira, à demain 09:30 ?')).toBe(
			'https://wa.me/21620123456?text=Bonjour%20Amira%2C%20%C3%A0%20demain%2009%3A30%20%3F'
		);
		expect(whatsappUrl('21620123456')).toBe('https://wa.me/21620123456');
	});

	it('builds sms: links that work on Android and iPhone', () => {
		expect(smsUrl('21620123456', 'A demain')).toBe('sms:+21620123456?&body=A%20demain');
	});

	it('builds tel: links and readable Tunisian numbers', () => {
		expect(telUrl('+21620123456')).toBe('tel:+21620123456');
		expect(displayPhone('+21620123456')).toBe('+216 20 123 456');
		expect(displayPhone('+33612345678')).toBe('+33612345678');
		expect(displayPhone('')).toBe('');
	});
});

describe('money input in dinars', () => {
	it('reads what people type into millimes', () => {
		expect(parseDinars('12')).toBe(12000);
		expect(parseDinars('12,5')).toBe(12500);
		expect(parseDinars('12.5')).toBe(12500);
		expect(parseDinars('12,500')).toBe(12500);
		expect(parseDinars(' 1 250 ')).toBe(1250000);
		expect(parseDinars('0,050')).toBe(50);
		expect(parseDinars('')).toBeNull();
		expect(parseDinars('abc')).toBeNull();
		expect(parseDinars('-5')).toBeNull();
		expect(parseDinars('1,2345')).toBeNull();
	});

	it('shows millimes back in an input', () => {
		expect(millimesToInput(12500)).toBe('12,5');
		expect(millimesToInput(12000)).toBe('12');
		expect(millimesToInput(50)).toBe('0,05');
		expect(millimesToInput(0)).toBe('');
	});
});
