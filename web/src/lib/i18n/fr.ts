/**
 * French dictionary – the reference: its shape defines `Messages`, and ar.ts must match it key by key
 * (a missing or extra key in Arabic is a svelte-check error).
 *
 * One file per namespace under ./fr and ./ar so feature work on different pages never edits the same file.
 * A new page: add `fr/<page>.ts` + `ar/<page>.ts` and one line in this file and in ar.ts.
 */
import { admin } from './fr/admin';
import { agenda } from './fr/agenda';
import { auth } from './fr/auth';
import { billing } from './fr/billing';
import { booking } from './fr/booking';
import { caisse } from './fr/caisse';
import { common } from './fr/common';
import { demo } from './fr/demo';
import { display } from './fr/display';
import { errors } from './fr/errors';
import { feedback } from './fr/feedback';
import { importer } from './fr/importer';
import { installer } from './fr/installer';
import { invitation } from './fr/invitation';
import { kit } from './fr/kit';
import { nav } from './fr/nav';
import { patients } from './fr/patients';
import { poster } from './fr/poster';
import { practice } from './fr/practice';
import { rappels } from './fr/rappels';
import { recu } from './fr/recu';
import { reglages } from './fr/reglages';
import { reset } from './fr/reset';
import { roles } from './fr/roles';
import { salle } from './fr/salle';
import { shell } from './fr/shell';
import { appointmentStatus, paymentMethod, queueStatus } from './fr/status';
import { statistiques } from './fr/statistiques';
import { ticket } from './fr/ticket';
import { today } from './fr/today';
import { governorate, specialty } from './fr/vocabulary';

export const fr = {
	common,
	errors,
	roles,
	nav,
	shell,
	auth,
	invitation,
	appointmentStatus,
	queueStatus,
	paymentMethod,
	governorate,
	specialty,
	today,
	agenda,
	salle,
	patients,
	caisse,
	rappels,
	reglages,
	admin,
	demo,
	display,
	ticket,
	recu,
	statistiques,
	kit,
	practice,
	poster,
	booking,
	reset,
	feedback,
	billing,
	installer,
	importer
};

export type Messages = typeof fr;
