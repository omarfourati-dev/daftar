import { describe, expect, it } from 'vitest';
import {
	bookingProblems,
	emptyProfile,
	practitionerFromContact,
	practitionerProblems,
	profileBody,
	profileProblems,
	serviceDrafts,
	serviceProblems,
	servicesBody
} from './practice-form';
import { DEFAULT_ONLINE_BOOKING } from './online-booking';

describe('practice forms', () => {
	it('requires name, contact and a plausible phone; checks optional e-mail and WhatsApp', () => {
		const p = emptyProfile('dentiste');
		expect(profileProblems(p, ['identity'])).toEqual({
			name: { key: 'kit.fieldRequired' },
			contactName: { key: 'kit.fieldRequired' },
			phone: { key: 'kit.fieldRequired' }
		});
		Object.assign(p, { name: 'Cabinet', contactName: 'Dr X', phone: '123', email: 'x@', whatsapp: 'abc' });
		expect(profileProblems(p, ['identity'])).toEqual({
			phone: { key: 'kit.invalidPhone' },
			email: { key: 'kit.invalidEmail' },
			whatsapp: { key: 'kit.invalidPhone' }
		});
	});

	it('requires address, city and governorate; checks the maps link', () => {
		const p = { ...emptyProfile(), mapsUrl: 'maps.google.com/x' };
		expect(profileProblems(p, ['address'])).toEqual({
			address: { key: 'kit.fieldRequired' },
			city: { key: 'kit.fieldRequired' },
			governorate: { key: 'kit.fieldRequired' },
			mapsUrl: { key: 'kit.invalidUrl' }
		});
	});

	it('trims and turns empty optional contacts into null for the API', () => {
		const p = { ...emptyProfile(), name: ' Cabinet ', email: ' ', whatsapp: '', governorate: '' };
		expect(profileBody(p)).toMatchObject({ name: 'Cabinet', email: null, whatsapp: null, governorate: null });
	});

	it('takes the first practitioner from the contact person', () => {
		expect(practitionerFromContact('Dr Amira Ben Salah', 'dentiste')).toEqual({ title: 'Dr.', name: 'Amira Ben Salah', specialty: '' });
		expect(practitionerFromContact('Pr. Hédi Ayari', 'cardiologue')).toEqual({ title: 'Pr.', name: 'Hédi Ayari', specialty: '' });
		expect(practitionerFromContact('Rim Haddad', 'kinesitherapeute')).toEqual({ title: '', name: 'Rim Haddad', specialty: '' });
	});

	it('checks practitioners and services row by row', () => {
		expect(practitionerProblems([])).toEqual({ list: { key: 'practice.practitioners.atLeastOne' } });
		expect(practitionerProblems([{ title: 'Dr.', name: ' ', specialty: '' }])).toEqual({ 'name-0': { key: 'kit.fieldRequired' } });
		const drafts = serviceDrafts([{ nameFr: 'Consultation', nameAr: '', durationMin: 30, priceMillimes: 40000, onlineBookable: true }]);
		expect(drafts).toEqual([{ nameFr: 'Consultation', nameAr: '', durationMin: '30', priceText: '40', onlineBookable: true }]);
		expect(serviceProblems(drafts)).toEqual({});
		expect(serviceProblems([{ ...drafts[0], nameFr: '', durationMin: '2', priceText: 'x' }])).toEqual({
			'nameFr-0': { key: 'kit.fieldRequired' },
			'durationMin-0': { key: 'practice.services.durationInvalid' },
			'price-0': { key: 'kit.invalidAmount' }
		});
		expect(servicesBody([{ ...drafts[0], priceText: '' }])).toEqual([
			{ nameFr: 'Consultation', nameAr: '', durationMin: 30, priceMillimes: null, onlineBookable: true }
		]);
	});

	it('keeps the online booking numbers in range', () => {
		expect(bookingProblems({ ...DEFAULT_ONLINE_BOOKING })).toEqual({});
		expect(bookingProblems({ ...DEFAULT_ONLINE_BOOKING, horizonDays: 0, blockNoShows: 11, maxPerDay: 1.5 })).toEqual({
			horizonDays: { key: 'kit.invalidNumber', params: { min: 1, max: 365 } },
			maxPerDay: { key: 'kit.invalidNumber', params: { min: 1, max: 200 } },
			blockNoShows: { key: 'kit.invalidNumber', params: { min: 0, max: 10 } }
		});
	});
});
