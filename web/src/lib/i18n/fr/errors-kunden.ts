/** Problem codes of the practice, team, admin and subscription APIs (be-termine report, section 11.4). Owner: fe-kunden. */
export const errorsKunden = {
	practitioner_in_use: 'Ce praticien a des rendez-vous. Décochez « Actif » pour le retirer de l’agenda sans rien perdre.',
	invalid_user: 'Ce compte n’appartient pas au cabinet.',
	invalid_range: 'Période invalide : la fin doit suivre le début, sur un an au plus.',
	self_not_allowed: 'Vous ne pouvez pas faire cela pour votre propre compte.',
	owner_protected: 'Le compte du titulaire ne peut pas être modifié ici.',
	reset_invalid: 'Ce lien n’est pas valide, a expiré ou a déjà été utilisé. Demandez un nouveau lien au cabinet.',
	slug_invalid: 'Sous-domaine invalide : 3 à 40 lettres minuscules, chiffres et tirets.',
	slug_reserved: 'Ce sous-domaine est réservé. Choisissez-en un autre.',
	slug_taken: 'Ce sous-domaine est déjà utilisé par un autre cabinet.',
	invalid_plan: 'Formule inconnue.',
	invalid_hours: 'Horaires invalides : vérifiez le début et la fin de chaque plage.',
	owner_missing: 'Ce cabinet n’a pas encore de titulaire : envoyez d’abord une invitation.',
	onboarding_derived: 'Cette étape se coche toute seule dès qu’elle est faite.',
	subscription_suspended: 'Abonnement suspendu : vous pouvez consulter vos données, mais plus les modifier.',
	file_too_large: 'Le fichier dépasse 2 Mo. Enregistrez seulement les colonnes utiles ou divisez le fichier.',
	unsupported_file: 'Format non reconnu. Utilisez un fichier Excel (.xlsx, .xls) ou CSV.',
	too_many_rows: 'Le fichier dépasse 20 000 lignes. Divisez-le en plusieurs fichiers.',
	empty_file: 'Le fichier est vide.',
	payment_unavailable: 'Le paiement en ligne n’est pas disponible. Réglez par virement : contactez-nous.'
};
