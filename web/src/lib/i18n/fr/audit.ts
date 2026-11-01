/** The change log of stock and hygiene (spec stock-hygiène 8): who changed what, when, old → new – in words. */
export const audit = {
	entry: '{date} – {user} {what}',
	reason: 'Motif : {reason}',
	change: '{field} : {before} → {after}',
	empty: 'Aucune correction pour l’instant.',
	loadError: 'Le journal n’a pas pu être chargé.',
	yes: 'oui',
	no: 'non',
	none: '–',
	what: {
		stock_receipt: { delete: 'a supprimé la réception du {date} ({total})' },
		stock_receipt_line: { update: 'a corrigé la réception du {date} : {product}' },
		stock_movement: { delete: 'a supprimé : {kind} de {quantity} {product}' },
		stock_product: { update: 'a modifié le produit « {name} »', delete: 'a supprimé le produit « {name} »' },
		supplier: { update: 'a modifié le fournisseur « {name} »', delete: 'a supprimé le fournisseur « {name} »' },
		hygiene_task: { update: 'a modifié la tâche « {name} »', delete: 'a supprimé la tâche « {name} »' },
		equipment: { update: 'a modifié l’équipement « {name} »', delete: 'a supprimé l’équipement « {name} »' },
		hygiene_task_done: {
			update: 'a corrigé « {name} » du {date} (fait par {by})',
			delete: 'a annulé « {name} » du {date} (fait par {by})'
		},
		other: 'a modifié une donnée'
	},
	fields: {
		name: 'Nom',
		category: 'Catégorie',
		unit: 'Unité',
		supplier: 'Fournisseur',
		minQuantity: 'Seuil de commande',
		note: 'Note',
		ean: 'Code EAN',
		active: 'Actif',
		phone: 'Téléphone',
		whatsapp: 'WhatsApp',
		title: 'Tâche',
		equipment: 'Équipement',
		frequency: 'Fréquence',
		weekday: 'Jour',
		intervalDays: 'Nombre de jours',
		startsOn: 'Première fois',
		instructions: 'Consignes',
		kind: 'Type',
		serialNumber: 'N° de série',
		quantity: 'Quantité',
		unitPriceMillimes: 'Prix unitaire',
		result: 'Résultat'
	}
};
