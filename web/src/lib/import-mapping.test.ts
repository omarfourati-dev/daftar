import { describe, expect, it } from 'vitest';
import { DEFAULT_OPTIONS, FIELDS, mappingFor, missingRequired, sharedColumns } from './import-mapping';

const suggested = { lastName: 0, firstName: 1, fullName: null, phone: 2, birthDate: 3, date: 4, time: null, service: null, notes: null };

describe('import column mapping (section 14)', () => {
	it('knows the Daftar fields of each kind, like the backend', () => {
		expect(FIELDS.patients).toEqual([
			'lastName',
			'firstName',
			'fullName',
			'phone',
			'birthDate',
			'birthYear',
			'notes',
			'alerts',
			'lang',
			'reminderConsent',
			'openingBalance',
			'externalRef'
		]);
		expect(FIELDS.appointments).toEqual(['date', 'time', 'datetime', 'durationMin', 'endTime', 'lastName', 'firstName', 'fullName', 'phone', 'service', 'practitioner', 'notes']);
	});

	it('takes only the fields of the chosen kind from the suggestion and fills the others with null', () => {
		const patients = mappingFor('patients', suggested);
		expect(Object.keys(patients)).toEqual(FIELDS.patients);
		expect(patients).toMatchObject({ lastName: 0, firstName: 1, phone: 2, birthDate: 3, birthYear: null, alerts: null });
		expect(patients).not.toHaveProperty('date');
		expect(mappingFor('appointments', suggested)).toMatchObject({ date: 4, time: null, lastName: 0 });
	});

	it('names the missing required fields: name, phone (patients), date and time (appointments)', () => {
		expect(missingRequired('patients', mappingFor('patients', {}))).toEqual(['name', 'phone']);
		expect(missingRequired('patients', mappingFor('patients', { lastName: 0, phone: 2 }))).toEqual(['name']); // first name too
		expect(missingRequired('patients', mappingFor('patients', { fullName: 0, phone: 2 }))).toEqual([]);
		expect(missingRequired('appointments', mappingFor('appointments', { fullName: 0 }))).toEqual(['when']);
		expect(missingRequired('appointments', mappingFor('appointments', { fullName: 0, date: 1 }))).toEqual(['when']);
		expect(missingRequired('appointments', mappingFor('appointments', { fullName: 0, datetime: 1 }))).toEqual([]);
	});

	it('finds a column used for two fields', () => {
		expect(sharedColumns({ lastName: 0, firstName: 0, phone: 2, notes: null })).toEqual([0]);
		expect(sharedColumns({ lastName: 0, phone: 2 })).toEqual([]);
	});

	it('starts with the backend defaults', () => {
		expect(DEFAULT_OPTIONS).toEqual({ nameOrder: 'last_first', dateFormat: 'dmy', defaultLang: 'fr', reminderConsent: false, duplicates: 'skip' });
	});
});
