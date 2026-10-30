/** Page /app/caisse (cash book of the day, closing, open balances). Owner: web agent "Tagesgeschäft". */
export const caisse = {
	title: 'Caisse',
	previousDay: 'Jour précédent',
	nextDay: 'Jour suivant',
	today: 'Aujourd’hui',
	pickDay: 'Choisir le jour',
	total: 'Encaissé ce jour',
	byMethod: 'Par mode de paiement',
	payments: 'Paiements du jour',
	noPayments: 'Aucun paiement ce jour.',
	receipt: 'Reçu',
	deposit: 'Acompte',
	loadError: 'La caisse n’a pas pu être chargée.',
	closing: {
		title: 'Clôture de caisse',
		hint: 'Comptez les espèces dans la caisse et notez le montant.',
		expected: 'Espèces attendues',
		counted: 'Espèces comptées (DT)',
		countedShort: 'Espèces comptées',
		note: 'Note (facultatif)',
		close: 'Clôturer la caisse',
		recount: 'Recompter',
		difference: 'Écart',
		exact: 'La caisse est juste.',
		missing: 'Manque {amount}',
		surplus: 'Excédent {amount}',
		closedBy: 'Clôturée par {name} à {time}',
		verify: 'Valider la clôture',
		verifiedBy: 'Validée par {name} le {date}',
		waiting: 'En attente de validation par le titulaire.',
		stale: 'Des paiements ont changé depuis la clôture. Recomptez la caisse.',
		invalid: 'Indiquez le montant compté (0 si la caisse est vide).'
	},
	balances: {
		title: 'Montants dus',
		hint: 'Patients qui doivent encore de l’argent, du plus grand montant au plus petit.',
		total: 'Total dû : {amount}',
		lastPayment: 'Dernier paiement : {date}',
		never: 'Aucun paiement',
		empty: 'Aucun montant dû. Tout est payé.'
	}
};
