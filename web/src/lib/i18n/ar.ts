/** Arabic dictionary – typed as `Messages`, so it must have exactly the keys of fr.ts. */
import type { Messages } from './fr';
import { admin } from './ar/admin';
import { agenda } from './ar/agenda';
import { auth } from './ar/auth';
import { caisse } from './ar/caisse';
import { common } from './ar/common';
import { demo } from './ar/demo';
import { display } from './ar/display';
import { errors } from './ar/errors';
import { invitation } from './ar/invitation';
import { kit } from './ar/kit';
import { nav } from './ar/nav';
import { patients } from './ar/patients';
import { poster } from './ar/poster';
import { practice } from './ar/practice';
import { rappels } from './ar/rappels';
import { recu } from './ar/recu';
import { reglages } from './ar/reglages';
import { roles } from './ar/roles';
import { salle } from './ar/salle';
import { shell } from './ar/shell';
import { appointmentStatus, paymentMethod, queueStatus } from './ar/status';
import { ticket } from './ar/ticket';
import { today } from './ar/today';
import { governorate, specialty } from './ar/vocabulary';

export const ar: Messages = {
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
	kit,
	practice,
	poster
};
