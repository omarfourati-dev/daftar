/** Page /app/salle (waiting room at the desk). Owner: web agent "Tagesgeschäft". */
export const salle = {
	title: 'Salle d’attente',
	screen: 'Écran de la salle',
	newTicket: 'Nouveau ticket',
	loadError: 'La salle d’attente n’a pas pu être chargée.',
	empty: 'Personne en salle d’attente.',
	emptyHint: 'Un ticket est créé à l’arrivée d’un patient : bouton « Nouveau ticket », ou « Arrivé » dans l’agenda.',
	sections: {
		in_treatment: 'En consultation',
		called: 'Appelés',
		waiting: 'En attente',
		finished: 'Terminés aujourd’hui'
	},
	ticket: 'Ticket {number}',
	appointmentAt: 'RDV {time}',
	walkIn: 'Sans rendez-vous',
	position: 'Position {position}',
	wait: 'env. {min} min',
	since: 'depuis {time}',
	updated: 'Ticket {number} : {status}.',
	actions: {
		call: 'Appeler',
		start: 'En consultation',
		done: 'Terminé',
		left: 'Parti',
		qr: 'QR code',
		whatsapp: 'WhatsApp'
	},
	form: {
		title: 'Nouveau ticket',
		forPatient: 'Patient du cabinet',
		walkIn: 'Juste un nom',
		name: 'Nom',
		phone: 'Téléphone (facultatif)',
		create: 'Donner le ticket',
		needName: 'Indiquez un nom ou choisissez un patient.',
		created: 'Ticket {number} pour {name}'
	},
	qr: {
		title: 'Ticket {number}',
		image: 'QR code du ticket {number}',
		hint: 'Le patient prend ce code en photo pour suivre son tour sur son téléphone.',
		open: 'Ouvrir la page du ticket'
	},
	message: 'Bonjour, voici votre ticket au {practice} : n° {number}. Suivez votre tour ici : {url}',
	preview: {
		title: 'Écran de la salle d’attente',
		called: 'Ticket appelé',
		next: 'Prochains tickets',
		waiting: '{count} en attente – numéros uniquement, aucun nom'
	}
};
