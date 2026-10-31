/** Page /app (dashboard "Aujourd'hui"). Owner: web agent "Tagesgeschäft". */
export const today = {
	title: 'Aujourd’hui',
	newAppointment: 'Nouveau rendez-vous',
	newTicket: 'Nouveau ticket',
	loadError: 'Le tableau de bord n’a pas pu être chargé.',
	tiles: {
		label: 'Résumé de la journée',
		appointments: 'Rendez-vous',
		appointmentsHint: '{done} terminés, {left} à venir',
		waiting: 'En salle d’attente',
		waitingHint: '{called} appelé(s)',
		cash: 'Caisse du jour',
		reminders: 'Rappels de demain',
		remindersHint: 'à envoyer',
		due: 'Montants dus',
		dueHint: 'tous patients'
	},
	requests: {
		title: 'Nouvelles demandes en ligne',
		hint: 'Confirmez ou refusez, puis prévenez le patient par WhatsApp.',
		done: '{patient} : {status}.'
	},
	overdue: {
		title: 'Non venus ?',
		hint: 'L’heure est passée et l’arrivée n’a pas été notée.',
		noShow: 'Absent',
		came: 'Venu',
		left: 'Parti avant la consultation',
		done: '{patient} : {status}.'
	},
	cashCheck: {
		title: 'Caisses à vérifier',
		difference: '{date} : écart {amount}',
		exact: '{date} : caisse juste'
	},
	upcoming: {
		title: 'Prochains rendez-vous',
		empty: 'Plus aucun rendez-vous prévu aujourd’hui.',
		all: 'Voir l’agenda'
	},
	onboarding: {
		title: 'Premiers pas',
		progress: '{done} sur {total} terminés',
		hide: 'Masquer',
		markDone: 'C’est fait',
		open: 'Ouvrir',
		steps: {
			hours: 'Horaires d’ouverture',
			services: 'Actes et tarifs',
			practitioners: 'Praticiens',
			team: 'Inviter l’équipe',
			booking: 'Activer la réservation en ligne',
			import: 'Importer vos patients (Excel)',
			install: 'Installer l’application',
			poster: 'Imprimer l’affiche pour la salle d’attente'
		}
	}
};
