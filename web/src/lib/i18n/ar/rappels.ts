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
	sentAt: 'أُرسل يوم {date} على الساعة {time}',
	resend: 'إعادة الإرسال',
	resendTitle: 'إعادة إرسال التذكير؟',
	resendMessage: 'أُرسل تذكير {patient} يوم {date} على الساعة {time}. هل تريد إرساله مرة ثانية؟',
	resendConfirm: 'نعم، أعد الإرسال',
	noConsent: 'لا يقبل التذكير',
	demo: 'نسخة تجريبية: لا يُرسل أي شيء. في عيادتك يفتح هذا الزر واتساب أو الإرساليات القصيرة بهذه الرسالة.',
	empty: 'لا توجد مواعيد في ذلك اليوم.',
	loadError: 'تعذّر تحميل التذكيرات.',
	showMessage: 'عرض الرسالة'
};
