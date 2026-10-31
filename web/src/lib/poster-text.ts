/**
 * The words printed on the A4 poster. The poster always speaks both languages side by side, whatever language
 * the app is in, so these texts are not part of the per-language dictionaries.
 */
export const POSTER_TEXT = {
	fr: {
		headline: 'Prenez rendez-vous en ligne',
		sub: 'Sans attendre au téléphone, à toute heure.',
		steps: ['Scannez le code avec l’appareil photo', 'Choisissez l’acte, le jour et l’heure', 'Recevez la confirmation du cabinet'],
		call: 'Ou appelez-nous'
	},
	ar: {
		headline: 'احجزوا موعدكم عبر الإنترنت',
		sub: 'دون انتظار على الهاتف، في أي وقت.',
		steps: ['امسحوا الرمز بكاميرا الهاتف', 'اختاروا الخدمة واليوم والساعة', 'يصلكم تأكيد العيادة'],
		call: 'أو اتصلوا بنا'
	}
} as const;
