import { errorsKunden } from './errors-kunden';

/** Texts for the `code` of API problems (backend daftar/problems.py) and for client-side errors. Owner: foundation. */
export const errors = {
	network: 'Pas de connexion au serveur. Vérifiez votre connexion internet.',
	server: 'Le serveur ne répond pas pour le moment. Veuillez réessayer dans un instant.',
	unexpected: 'Réponse inattendue du serveur.',
	generic: 'Cela n’a pas fonctionné.',
	unauthorized: 'Veuillez vous connecter.',
	forbidden: 'Vous n’avez pas accès à cette action.',
	not_found: 'Introuvable.',
	validation: 'Les données saisies sont invalides.',
	too_many_requests: 'Trop de tentatives. Veuillez réessayer plus tard.',
	invalid_credentials: 'E-mail ou mot de passe incorrect.',
	wrong_password: 'Le mot de passe actuel est incorrect.',
	password_too_short: 'Le mot de passe doit contenir au moins 10 caractères.',
	password_too_long: 'Le mot de passe est trop long.',
	password_repeated: 'Le mot de passe ne peut pas être un seul caractère répété.',
	password_sequence: 'Le mot de passe ne peut pas être une simple suite comme 1234567890 ou azertyuiop.',
	password_contains_email: 'Le mot de passe ne doit pas contenir votre adresse e-mail.',
	passwords_differ: 'Les deux mots de passe ne sont pas identiques.',
	invitation_invalid: 'Cette invitation n’est pas valide, a expiré ou a déjà été utilisée.',
	invitation_incomplete: 'Ce lien est incomplet. Ouvrez le lien entier reçu dans votre invitation.',
	email_taken: 'Un compte existe déjà avec cette adresse e-mail.',
	invalid_phone: 'Numéro de téléphone invalide.',
	demo_expired: 'La démo est terminée. Vous pouvez en lancer une nouvelle.',
	demo_invitation: 'Cette invitation vient d’une démo : aucun compte n’est créé. Dans votre cabinet, la personne invitée crée ici son propre compte.',
	server_error: 'Une erreur est survenue.',
	...errorsKunden
};
