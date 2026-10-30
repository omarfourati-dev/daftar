/**
 * Specialties (design section 12) and the default service catalog of each – a mirror of backend daftar/catalog.py
 * (catalog.test.ts compares both). The admin wizard pre-fills step "Actes & tarifs" from it; prices stay empty.
 */
import type { Specialty } from './types';

export interface CatalogService {
	nameFr: string;
	nameAr: string;
	durationMin: number;
	priceMillimes: number | null;
	onlineBookable: boolean;
}

export const SPECIALTIES: readonly Specialty[] = [
	'generaliste',
	'dentiste',
	'pediatre',
	'gynecologue',
	'dermatologue',
	'ophtalmologue',
	'cardiologue',
	'orl',
	'kinesitherapeute',
	'psychologue',
	'autre'
];

/** The choice offered on /app/demo (section 12). */
export const DEMO_SPECIALTIES: readonly Specialty[] = ['generaliste', 'dentiste', 'pediatre', 'kinesitherapeute', 'autre'];

const CONSULTATION_AR = 'معاينة';
const CONTROLE_AR = 'مراقبة';
type Item = Omit<CatalogService, 'priceMillimes'>;
const i = (nameFr: string, nameAr: string, durationMin: number, onlineBookable: boolean): Item => ({
	nameFr,
	nameAr,
	durationMin,
	onlineBookable
});

export const DEFAULT_CATALOGS: Record<Specialty, readonly Item[]> = {
	generaliste: [
		i('Consultation', CONSULTATION_AR, 20, true),
		i('Contrôle', CONTROLE_AR, 15, true),
		i('Certificat médical', 'شهادة طبية', 10, true),
		i('Vaccination', 'تلقيح', 15, true),
		i('Urgence', 'حالة مستعجلة', 20, false)
	],
	dentiste: [
		i('Consultation', CONSULTATION_AR, 30, true),
		i('Contrôle', CONTROLE_AR, 20, true),
		i('Détartrage', 'إزالة الجير', 45, true),
		i('Soin carie / composite', 'علاج تسوّس / حشوة', 45, false),
		i('Extraction', 'قلع سنّ', 30, false),
		i('Traitement de canal', 'علاج العصب', 60, false),
		i('Couronne – séance', 'تاج – حصّة', 60, false),
		i('Blanchiment', 'تبييض الأسنان', 60, false),
		i('Urgence / douleur', 'حالة مستعجلة / ألم', 30, false)
	],
	pediatre: [
		i('Consultation', CONSULTATION_AR, 30, true),
		i('Suivi croissance', 'متابعة النموّ', 20, true),
		i('Vaccination', 'تلقيح', 15, true),
		i('Urgence', 'حالة مستعجلة', 20, false)
	],
	gynecologue: [
		i('Consultation', CONSULTATION_AR, 30, true),
		i('Suivi de grossesse', 'متابعة الحمل', 30, true),
		i('Échographie', 'تصوير بالصدى', 20, true),
		i('Frottis', 'مسحة عنق الرحم', 15, true)
	],
	dermatologue: [
		i('Consultation', CONSULTATION_AR, 20, true),
		i('Contrôle', CONTROLE_AR, 15, true),
		i('Petite chirurgie', 'جراحة صغرى', 30, false)
	],
	ophtalmologue: [
		i('Consultation', CONSULTATION_AR, 20, true),
		i('Mesure de la vue / réfraction', 'قيس النظر', 20, true),
		i("Fond d'œil", 'فحص قاع العين', 20, false),
		i('Tension oculaire', 'قيس ضغط العين', 15, false),
		i('Adaptation lentilles', 'تركيب العدسات اللاصقة', 30, false)
	],
	cardiologue: [
		i('Consultation', CONSULTATION_AR, 30, true),
		i('ECG', 'تخطيط القلب', 15, false),
		i('Échographie cardiaque', 'تصوير القلب بالصدى', 30, false),
		i('Pose Holter', 'تركيب جهاز هولتر', 15, false)
	],
	orl: [i('Consultation', CONSULTATION_AR, 20, true), i('Audiogramme', 'قياس السمع', 30, false), i("Lavage d'oreille", 'غسل الأذن', 15, true)],
	kinesitherapeute: [i('Séance', 'حصّة', 45, true), i('Bilan', 'تقييم', 60, true)],
	psychologue: [i('Séance', 'حصّة', 50, true), i('Premier entretien', 'مقابلة أولى', 60, true)],
	autre: [i('Consultation', CONSULTATION_AR, 30, true), i('Contrôle', CONTROLE_AR, 20, true)]
};

/** A fresh, editable copy of the default catalog of `specialty` (prices empty). */
export function catalogFor(specialty: Specialty): CatalogService[] {
	return DEFAULT_CATALOGS[specialty].map((item) => ({ ...item, priceMillimes: null }));
}
