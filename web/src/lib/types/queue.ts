/** API shapes of the waiting room (design section 5, 15). */
export type QueueStatus = 'waiting' | 'called' | 'in_treatment' | 'done' | 'left';

export interface QueueEntry {
	id: number;
	ticketNo: number;
	name: string;
	phone: string | null;
	patientId: number | null;
	appointmentId: number | null;
	appointmentAt: string | null;
	status: QueueStatus;
	arrivedAt: string;
	calledAt: string | null;
	doneAt: string | null;
	ticketToken: string;
	/** Only for `waiting`, 1-based. */
	position: number | null;
	/** Waiting and called people before this ticket (0 when not waiting). */
	peopleAhead: number | null;
	estimatedWaitMin: number | null;
	/** Medical alert of the linked patient (internal only). */
	alerts?: string;
}

/** `GET /api/public/display/{displayToken}` – numbers only, never names. */
export interface PublicDisplay {
	practiceName: string;
	called: number[];
	next: number[];
	waiting: number;
}

/** `GET /api/public/ticket/{ticketToken}` – numbers only, never names. */
export interface PublicTicket {
	practiceName: string;
	practicePhone: string;
	ticketNo: number;
	status: QueueStatus;
	position?: number | null;
	peopleAhead: number | null;
	estimatedWaitMin: number | null;
	day: string;
}
