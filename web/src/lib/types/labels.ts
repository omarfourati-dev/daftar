/** API shapes of sterilisation, traceability and labels (spec stock-hygiène 5.3, 6, 7; backend daftar/sterilization.py, daftar/labels.py). */

export type LabelFormat = 'roll62' | 'label57x32' | 'a4_3x8';
export type LabelKind = 'sterile' | 'specimen';
export type Packaging = 'sachet' | 'double_sachet' | 'conteneur' | 'champ';
export type SpecimenKind = 'edta' | 'sec' | 'citrate' | 'heparine' | 'urine' | 'selles' | 'frottis' | 'autre';
export type PackState = 'usable' | 'expired' | 'used' | 'not_sterile' | 'cancelled';
export type CycleResult = 'ok' | 'not_ok';

export interface LabelSettings {
	formats: Record<LabelKind, LabelFormat>;
	shelfLifeDays: Record<Packaging, number>;
}

/** The use of a pack in a list of packs: whom it went to only for the owner (`patient*` null for the desk). */
export interface PackUseBrief {
	id: number;
	patientId: number | null;
	patientName: string | null;
	patientNo: number | null;
	/** The patient was erased: the pack stays used, only the number is kept. */
	patientDeleted: boolean;
	appointmentId: number | null;
	usedAt: string;
	usedBy: string;
}

export interface Pack {
	id: number;
	seq: number;
	code: string;
	content: string;
	packaging: Packaging;
	expiresOn: string;
	state: PackState;
	use: PackUseBrief | null;
}

/** `GET /api/hygiene/packs`: a pack with its cycle. */
export interface PackFound extends Pack {
	cycleId: number;
	labelCode: string;
	number: number;
	equipmentName: string;
	runAt: string;
	/** Why its cycle was cancelled (null: not cancelled). */
	cancelReason: string | null;
}

export interface Cycle {
	id: number;
	equipmentId: number;
	equipmentName: string;
	labelCode: string;
	number: number;
	runAt: string;
	program: string;
	result: CycleResult;
	packCount: number;
	note: string;
	/** Who ran the cycle (its initials are on the labels) and who entered it. */
	performedBy: string;
	performedById: number | null;
	initials: string;
	recordedBy: string;
	createdAt: string;
	/** Cancelled by the owner (entered by mistake): its number and codes stay taken, its labels are void. */
	cancelledAt: string | null;
	cancelledBy: string | null;
	cancelReason: string | null;
	packs: Pack[];
}

export interface CycleList {
	from: string;
	to: string;
	cycles: Cycle[];
}

export interface Autoclave {
	id: number;
	name: string;
	labelCode: string | null;
	nextNumber: number;
	lastRunAt: string | null;
}

export interface CycleSetup {
	autoclaves: Autoclave[];
	programs: string[];
	contents: string[];
	/** Who may have run the cycle ("fait par"). */
	team: { id: number; name: string; initials: string }[];
}

/** A pack opened for a patient (`POST /api/hygiene/pack-uses`, `GET …?appointmentId=`). */
export interface PackUse {
	id: number;
	packId: number;
	code: string;
	content: string;
	packaging: Packaging;
	expiresOn: string;
	cycle: { id: number; labelCode: string; number: number; equipmentName: string; runAt: string; result: CycleResult };
	/** null once the patient was erased (`patientDeleted`); the number stays. */
	patientId: number | null;
	patientName: string | null;
	patientNo: number;
	patientDeleted: boolean;
	appointmentId: number | null;
	usedAt: string;
	usedBy: string;
	undoable: boolean;
}

export interface PackTrace {
	pack: PackFound;
	use: PackUse | null;
}

export interface PatientTrace {
	patient: { id: number; name: string };
	uses: PackUse[];
}

export interface SpecimenItem {
	kind: SpecimenKind;
	count: number;
	label: string;
}

/** `POST /api/labels/specimens` and `GET /api/labels/specimens[/{id}]`. */
export interface SpecimenPrint {
	id: number;
	patient: { id: number; firstName: string; lastName: string; birthDate: string | null; birthYear: number | null };
	appointmentId: number | null;
	items: SpecimenItem[];
	labelCount: number;
	labels: { code: string; kind: SpecimenKind; label: string }[];
	collectedAt: string;
	collectedBy: string;
	printedBy: string;
	printedAt: string;
}
