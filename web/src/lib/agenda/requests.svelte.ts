/** Requests between the app frame (shortcuts, header) and the agenda page, which may or may not be open. */

/** "New appointment" asked from outside the agenda page while it is open (keyboard shortcut `N`). */
class NewAppointment {
	count = $state(0);

	request(): void {
		this.count++;
	}
}

export const newAppointment = new NewAppointment();

/** The phone booking dialog of the header (section 16.1, key `T`). */
class PhoneBookingState {
	open = $state(false);
}

export const phoneBooking = new PhoneBookingState();

/** Appointments changed outside the agenda page (e.g. booked on the phone): the agenda reloads. */
class AgendaChanges {
	version = $state(0);

	bump(): void {
		this.version++;
	}
}

export const agendaChanges = new AgendaChanges();
