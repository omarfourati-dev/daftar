/**
 * Colours of appointment statuses (design section 6): scheduled slate, confirmed sky, arrived amber,
 * in_treatment violet, done emerald, no_show rose, cancelled zinc (struck through); online requests dashed.
 * Texts: `t(\`appointmentStatus.${status}\`)`.
 */
export const APPOINTMENT_STATUSES = [
	'requested',
	'scheduled',
	'confirmed',
	'arrived',
	'in_treatment',
	'done',
	'no_show',
	'cancelled'
] as const;
export type AppointmentStatus = (typeof APPOINTMENT_STATUSES)[number];

const CLASSES: Record<AppointmentStatus, string> = {
	requested: 'bg-white text-slate-700 border border-dashed border-slate-400',
	scheduled: 'bg-slate-100 text-slate-800 border border-slate-300',
	confirmed: 'bg-sky-100 text-sky-900 border border-sky-300',
	arrived: 'bg-amber-100 text-amber-900 border border-amber-300',
	in_treatment: 'bg-violet-100 text-violet-900 border border-violet-300',
	done: 'bg-emerald-100 text-emerald-900 border border-emerald-300',
	no_show: 'bg-rose-100 text-rose-900 border border-rose-300',
	cancelled: 'bg-zinc-100 text-zinc-500 border border-zinc-300 line-through'
};

export function appointmentStatusClass(status: AppointmentStatus): string {
	return CLASSES[status];
}
