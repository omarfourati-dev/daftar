/** Shared domain vocabulary (appointment and queue statuses, payment methods). Owner: foundation. */
export const appointmentStatus = {
	scheduled: 'Prévu',
	confirmed: 'Confirmé',
	arrived: 'Arrivé',
	in_treatment: 'En soins',
	done: 'Terminé',
	no_show: 'Absent',
	cancelled: 'Annulé'
};

export const queueStatus = {
	waiting: 'En attente',
	called: 'Appelé',
	in_treatment: 'En soins',
	done: 'Terminé',
	left: 'Parti'
};

export const paymentMethod = {
	cash: 'Espèces',
	d17: 'D17',
	flouci: 'Flouci',
	card: 'Carte',
	cheque: 'Chèque',
	transfer: 'Virement',
	other: 'Autre'
};
