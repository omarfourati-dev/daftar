/** API shapes of the hygiene module (spec stock-hygiène 5.1, 5.2; backend daftar/hygiene.py). */

export type Frequency = 'daily' | 'weekly' | 'monthly' | 'yearly' | 'every_n_days';
export type EquipmentKind = 'autoclave' | 'thermodesinfecteur' | 'ultrasons' | 'compresseur' | 'aspiration' | 'fauteuil' | 'radiographie' | 'autre';
export type HygieneResult = 'ok' | 'not_ok';

export interface Equipment {
	id: number;
	name: string;
	kind: EquipmentKind;
	serialNumber: string;
	note: string;
	active: boolean;
	tasks: number;
}

export interface HygieneTask {
	id: number;
	title: string;
	equipmentId: number | null;
	equipmentName: string | null;
	frequency: Frequency;
	weekday: number | null;
	intervalDays: number | null;
	startsOn: string;
	instructions: string;
	active: boolean;
	/** The open occurrence, else the next one; null for a deactivated task. */
	nextDueOn: string | null;
}

export interface HygieneDone {
	id: number;
	doneBy: string;
	doneAt: string;
	result: HygieneResult;
	note: string;
	/** The author within 15 minutes, the owner always. */
	undoable?: boolean;
}

export interface HygieneItem {
	taskId: number;
	title: string;
	equipmentName: string | null;
	frequency: Frequency;
	instructions: string;
	dueOn: string;
	state: 'overdue' | 'due' | 'done';
	done: HygieneDone | null;
}

/** `GET /api/hygiene/today` and `hygiene` of the dashboard. */
export interface HygieneToday {
	day: string;
	open: number;
	items: HygieneItem[];
}

export interface HistoryRow {
	dueOn: string;
	taskId: number;
	title: string;
	equipmentName: string | null;
	status: 'done' | 'missed' | 'due';
	late: boolean;
	done: HygieneDone | null;
}

export interface HygieneHistory {
	from: string;
	to: string;
	rows: HistoryRow[];
}
