/** Page /app/installer (section 13, story A4). Owner: fe-kunden. */
export const installer = {
	title: 'Installer l’application',
	intro: 'Daftar s’installe comme une application, sans store : une icône sur l’écran d’accueil ou le bureau, et les mises à jour arrivent toutes seules.',
	installed: 'L’application est installée sur cet appareil.',
	install: 'Installer l’application',
	ownAddress: 'Pour installer l’application de votre cabinet (avec son nom et son icône), ouvrez cette page à l’adresse du cabinet. Vous vous reconnecterez une fois.',
	openOwn: 'Ouvrir l’adresse du cabinet',
	thisDevice: 'Sur cet appareil',
	otherDevices: 'Sur un autre appareil',
	platforms: {
		ios: 'iPhone et iPad (Safari)',
		android: 'Android (Chrome)',
		desktop: 'Ordinateur (Chrome ou Edge)'
	},
	steps: {
		ios: { '1': 'Ouvrez l’adresse du cabinet dans Safari.', '2': 'Touchez le bouton Partager (le carré avec une flèche).', '3': 'Choisissez « Sur l’écran d’accueil », puis « Ajouter ».' },
		android: { '1': 'Ouvrez l’adresse du cabinet dans Chrome.', '2': 'Touchez le menu ⋮ en haut à droite.', '3': 'Choisissez « Installer l’application » (ou « Ajouter à l’écran d’accueil »).' },
		desktop: { '1': 'Ouvrez l’adresse du cabinet dans Chrome ou Edge.', '2': 'Cliquez sur l’icône d’installation dans la barre d’adresse (un écran avec une flèche).', '3': 'Confirmez avec « Installer ».' }
	},
	team: 'Pour les téléphones de l’équipe',
	teamText: 'Scannez ce code avec l’appareil photo : il ouvre l’application du cabinet. Ensuite, suivez les étapes de votre téléphone.',
	qr: 'QR code de l’application du cabinet',
	done: 'C’est fait, l’application est installée',
	thanks: 'Parfait ! L’étape « Installer l’application » est cochée.'
};
