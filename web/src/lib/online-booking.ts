/**
 * Online booking settings of a practice (section 11.2). The admin API takes them nested as `onlineBooking`;
 * `readOnlineBooking` also understands the flat column names, so the page works with either answer shape.
 */
export interface OnlineBooking {
	enabled: boolean;
	autoConfirm: boolean;
	horizonDays: number;
	minNoticeHours: number;
	maxPerDay: number;
	/** 0 = never block */
	blockNoShows: number;
}

export const DEFAULT_ONLINE_BOOKING: Readonly<OnlineBooking> = Object.freeze({
	enabled: false,
	autoConfirm: false,
	horizonDays: 30,
	minNoticeHours: 2,
	maxPerDay: 20,
	blockNoShows: 2
});

const FLAT: Record<keyof OnlineBooking, string> = {
	enabled: 'onlineBookingEnabled',
	autoConfirm: 'onlineAutoConfirm',
	horizonDays: 'bookingHorizonDays',
	minNoticeHours: 'bookingMinNoticeHours',
	maxPerDay: 'bookingMaxPerDay',
	blockNoShows: 'bookingBlockNoShows'
};

export function readOnlineBooking(practice: Record<string, unknown>): OnlineBooking {
	const nested = (practice.onlineBooking ?? {}) as Partial<Record<keyof OnlineBooking, unknown>>;
	const result = { ...DEFAULT_ONLINE_BOOKING } as OnlineBooking;
	for (const key of Object.keys(FLAT) as (keyof OnlineBooking)[]) {
		const value = nested[key] ?? practice[FLAT[key]];
		if (typeof value === typeof DEFAULT_ONLINE_BOOKING[key]) (result as unknown as Record<string, unknown>)[key] = value;
	}
	return result;
}
