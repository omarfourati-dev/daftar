import type { Messages } from '../fr';

export const statistiques: Messages['statistiques'] = {
	title: 'الإحصائيات',
	previousMonth: 'الشهر السابق',
	nextMonth: 'الشهر التالي',
	ownerOnly: 'الإحصائيات متاحة لصاحب العيادة فقط.',
	loadError: 'تعذّر تحميل الإحصائيات.',
	compared: 'مقارنة بـ {month}',
	same: 'مثل الشهر السابق',
	up: '+{value} مقارنة بـ {month}',
	down: '−{value} مقارنة بـ {month}',
	kpis: {
		appointments: 'المواعيد',
		done: 'المرضى الحاضرون',
		noShowRate: 'نسبة الغياب',
		noShowCount: '{count} غيابات',
		cancelled: 'الملغاة',
		online: 'المحجوزة عبر الإنترنت',
		onlineShare: '{share} من المواعيد',
		revenue: 'المقبوض',
		newPatients: 'مرضى جدد'
	},
	chart: {
		title: 'هذا الشهر والشهر السابق',
		thisMonth: 'هذا الشهر',
		lastMonth: 'الشهر السابق'
	},
	top: {
		title: 'الخدمات الأكثر تكرارًا',
		empty: 'لا توجد خدمات هذا الشهر.',
		count: '{count} مرّة'
	},
	points: '{value} نقطة'
};
