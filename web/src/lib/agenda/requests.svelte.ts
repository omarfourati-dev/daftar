/** "New appointment" asked from outside the agenda page while it is open (keyboard shortcut `N`). */
class NewAppointment {
	count = $state(0);

	request(): void {
		this.count++;
	}
}

export const newAppointment = new NewAppointment();
