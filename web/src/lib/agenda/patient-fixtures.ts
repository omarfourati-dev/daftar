/** Patient test data shared by the route tests (never imported by app code). */
import type { Ledger, Patient, PatientSummary } from '../types/patients';

export function summary(over: Partial<PatientSummary> = {}): PatientSummary {
	return {
		id: 7,
		firstName: 'Sami',
		lastName: 'Trabelsi',
		phone: '+21620123456',
		birthYear: 1978,
		lang: 'fr',
		reminderConsent: true,
		noShows: 0,
		attended: 4,
		dueMillimes: 0,
		nextAppointmentAt: null,
		hasAlerts: false,
		...over
	};
}

export function patientFile(over: Partial<Patient> = {}): Patient {
	return {
		...summary(),
		notes: 'Préfère les rendez-vous le matin.',
		alerts: '',
		createdAt: '2025-03-02T10:00:00+01:00',
		cancelled: 1,
		totalMillimes: 990000,
		paidMillimes: 600000,
		dueMillimes: 390000,
		samePhone: [],
		...over
	};
}

export const ledger: Ledger = {
	treatments: [
		{ id: 1, label: 'Détartrage', tooth: null, priceMillimes: 60000, performedOn: '2026-09-12', appointmentId: null, createdAt: '2026-09-12T10:00:00+01:00' },
		{ id: 2, label: 'Traitement de canal', tooth: '26', priceMillimes: 280000, performedOn: '2026-09-12', appointmentId: null, createdAt: '2026-09-12T10:05:00+01:00' },
		{ id: 3, label: 'Couronne', tooth: '26', priceMillimes: 650000, performedOn: '2026-10-03', appointmentId: null, createdAt: '2026-10-03T10:00:00+01:00' }
	],
	payments: [
		{ id: 70, patientId: 7, patientName: 'Sami Trabelsi', amountMillimes: 200000, method: 'cash', paidAt: '2026-09-12T11:00:00+01:00', appointmentId: null, isDeposit: false, note: '', receivedByName: 'Salma' },
		{ id: 71, patientId: 7, patientName: 'Sami Trabelsi', amountMillimes: 400000, method: 'd17', paidAt: '2026-10-03T11:00:00+01:00', appointmentId: null, isDeposit: false, note: '', receivedByName: 'Salma' }
	],
	totalMillimes: 990000,
	paidMillimes: 600000,
	dueMillimes: 390000
};
