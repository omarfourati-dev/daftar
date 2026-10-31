import type { Messages } from '../fr';

export const rappels: Messages['rappels'] = {
	title: 'التذكيرات',
	subtitle: 'مواعيد يوم {date}',
	previousDay: 'اليوم السابق',
	nextDay: 'اليوم التالي',
	tomorrow: 'غدًا',
	nextOpenDay: 'يوم العمل التالي',
	intro: 'الرسالة جاهزة بلغة المريض. نقرة واحدة تفتح واتساب أو الإرساليات القصيرة، ويُسجَّل التذكير كمُرسَل.',
	summary: '{count} موعد، {sent} تذكير مُرسَل',
	whatsapp: 'واتساب',
	sms: 'إرسالية قصيرة',
	markSent: 'تسجيل كمُرسَل',
	sent: 'أُرسل',
	sentAt: 'أُرسل على الساعة {time}',
	noConsent: 'لا يقبل التذكير',
	demo: 'نسخة تجريبية: لا يُرسل أي شيء. في عيادتك يفتح هذا الزر واتساب أو الإرساليات القصيرة بهذه الرسالة.',
	empty: 'لا توجد مواعيد في ذلك اليوم.',
	loadError: 'تعذّر تحميل التذكيرات.',
	showMessage: 'عرض الرسالة'
};
