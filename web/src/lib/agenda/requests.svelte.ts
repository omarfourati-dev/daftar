/** Requests between the app frame (shortcuts, header) and the agenda page, which may or may not be open. */
import { flushSync } from 'svelte';

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

/** The patient search of the header – folded away on phones until asked for (menu "Plus", "Aujourd'hui"). */
class PatientSearchState {
	open = $state(false);

	/** Shows the search and puts the cursor into it – synchronously, so phones open the keyboard (user gesture). */
	show(): void {
		flushSync(() => (this.open = true));
		document.getElementById('global-search')?.focus();
	}
}

export const patientSearch = new PatientSearchState();

/** Appointments changed outside the agenda page (e.g. booked on the phone): the agenda reloads. */
class AgendaChanges {
	version = $state(0);

	bump(): void {
		this.version++;
	}
}

export const agendaChanges = new AgendaChanges();
