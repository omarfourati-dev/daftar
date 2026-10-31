import { describe, expect, it } from 'vitest';
import { DEFAULT_ONLINE_BOOKING, readOnlineBooking } from './online-booking';

describe('online booking settings', () => {
	it('has the defaults of section 11.2', () => {
		expect(DEFAULT_ONLINE_BOOKING).toEqual({ enabled: false, autoConfirm: false, horizonDays: 30, minNoticeHours: 2, maxPerDay: 20, blockNoShows: 2 });
	});

	it('reads the nested form', () => {
		const nested = { enabled: true, autoConfirm: true, horizonDays: 14, minNoticeHours: 4, maxPerDay: 10, blockNoShows: 0 };
		expect(readOnlineBooking({ onlineBooking: nested })).toEqual(nested);
	});

	it('also reads flat column names and fills gaps with defaults', () => {
		expect(readOnlineBooking({ onlineBookingEnabled: true, onlineAutoConfirm: false, bookingHorizonDays: 60, bookingMinNoticeHours: 1 })).toEqual({
			...DEFAULT_ONLINE_BOOKING,
			enabled: true,
			horizonDays: 60,
			minNoticeHours: 1
		});
		expect(readOnlineBooking({})).toEqual(DEFAULT_ONLINE_BOOKING);
	});
});
