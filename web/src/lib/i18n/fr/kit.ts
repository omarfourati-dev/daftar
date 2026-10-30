/** Shared pieces of the customer pages (links, QR codes, dialogs, hours editor, form checks). Owner: fe-kunden. */
export const kit = {
	copy: 'Copier',
	copied: 'Copié',
	copyFailed: 'Copie impossible – sélectionnez le lien et copiez-le.',
	open: 'Ouvrir',
	sendWhatsapp: 'Envoyer par WhatsApp',
	saved: 'Modifications enregistrées.',
	saving: 'Enregistrement…',
	required: 'obligatoire',
	optional: 'facultatif',
	fieldRequired: 'Ce champ est obligatoire.',
	invalidEmail: 'Adresse e-mail invalide.',
	invalidPhone: 'Numéro invalide. Exemple : 20 123 456 ou +216 20 123 456.',
	invalidUrl: 'Adresse web invalide. Elle commence par https://',
	invalidAmount: 'Montant invalide. Exemple : 35 ou 35,500.',
	invalidNumber: 'Nombre entre {min} et {max}.',
	loadFailed: 'Cette page n’a pas pu être chargée.',
	confirm: 'Confirmer',
	closeDialog: 'Fermer la fenêtre',
	typeToConfirm: 'Tapez « {text} » pour confirmer',
	linkOnce: 'Ce lien ne s’affiche qu’une fois : copiez-le ou envoyez-le maintenant.',
	validUntil: 'Valable jusqu’au {date}.',
	ownerOnly: 'Cette page est réservée au titulaire du cabinet.',
	minutes: '{n} min',
	none: '—',
	weekdays: {
		'1': 'Lundi',
		'2': 'Mardi',
		'3': 'Mercredi',
		'4': 'Jeudi',
		'5': 'Vendredi',
		'6': 'Samedi',
		'7': 'Dimanche'
	},
	/** "du lundi" – used inside sentences */
	weekdaysOf: {
		'1': 'du lundi',
		'2': 'du mardi',
		'3': 'du mercredi',
		'4': 'du jeudi',
		'5': 'du vendredi',
		'6': 'du samedi',
		'7': 'du dimanche'
	},
	weekdaysOn: {
		'1': 'le lundi',
		'2': 'le mardi',
		'3': 'le mercredi',
		'4': 'le jeudi',
		'5': 'le vendredi',
		'6': 'le samedi',
		'7': 'le dimanche'
	},
	weekdaysShort: {
		'1': 'Lun.',
		'2': 'Mar.',
		'3': 'Mer.',
		'4': 'Jeu.',
		'5': 'Ven.',
		'6': 'Sam.',
		'7': 'Dim.'
	},
	hours: {
		hint: 'Une pause = deux plages, par exemple 08:00–12:30 et 14:00–18:00.',
		closed: 'Fermé',
		start: '{day} – début de la plage {n}',
		end: '{day} – fin de la plage {n}',
		addWindow: 'Ajouter une plage {day}',
		addWindowShort: 'Ajouter une plage',
		removeWindow: 'Supprimer la plage {from}–{to} {day}',
		copy: 'Copier les horaires {day} sur les autres jours ouverts',
		copyShort: 'Copier sur les autres jours',
		problem: {
			missing: '{day} : indiquez le début et la fin de chaque plage.',
			order: '{day} : la fin doit être après le début.',
			overlap: '{day} : deux plages se chevauchent.'
		},
		fixFirst: 'Corrigez les horaires signalés avant d’enregistrer.'
	}
};
