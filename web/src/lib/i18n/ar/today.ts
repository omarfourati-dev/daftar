import type { Messages } from '../fr';

export const today: Messages['today'] = {
	title: 'اليوم',
	newAppointment: 'موعد جديد',
	newTicket: 'رقم جديد',
	loadError: 'تعذّر تحميل لوحة اليوم.',
	tiles: {
		label: 'ملخّص اليوم',
		appointments: 'المواعيد',
		appointmentsHint: '{done} انتهت، {left} قادمة',
		waiting: 'في قاعة الانتظار',
		waitingHint: '{called} تمّت مناداتهم',
		cash: 'صندوق اليوم',
		reminders: 'تذكيرات الغد',
		remindersHint: 'للإرسال',
		due: 'المبالغ المستحقّة',
		dueHint: 'كل المرضى'
	},
	requests: {
		title: 'طلبات جديدة عبر الإنترنت',
		hint: 'أكّد أو ارفض، ثم أعلم المريض عبر واتساب.',
		done: '{patient}: {status}.'
	},
	overdue: {
		title: 'لم يحضروا؟',
		hint: 'فات الموعد ولم يُسجَّل الوصول.',
		noShow: 'غائب',
		came: 'حضر',
		done: '{patient}: {status}.'
	},
	upcoming: {
		title: 'المواعيد القادمة',
		empty: 'لا توجد مواعيد أخرى اليوم.',
		all: 'عرض المواعيد'
	},
	onboarding: {
		title: 'الخطوات الأولى',
		progress: 'تمّ {done} من {total}',
		hide: 'إخفاء',
		markDone: 'تمّ',
		open: 'فتح',
		steps: {
			hours: 'أوقات العمل',
			services: 'الخدمات والأسعار',
			practitioners: 'الأطباء',
			team: 'دعوة الفريق',
			booking: 'تفعيل الحجز عبر الإنترنت',
			import: 'استيراد المرضى (Excel)',
			install: 'تثبيت التطبيق',
			poster: 'طباعة الملصق لقاعة الانتظار'
		}
	}
};
