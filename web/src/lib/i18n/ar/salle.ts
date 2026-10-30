import type { Messages } from '../fr';

export const salle: Messages['salle'] = {
	title: 'قاعة الانتظار',
	screen: 'شاشة القاعة',
	newTicket: 'رقم جديد',
	loadError: 'تعذّر تحميل قاعة الانتظار.',
	empty: 'لا أحد في قاعة الانتظار.',
	emptyHint: 'يُعطى رقم عند وصول المريض: زر «رقم جديد» أو «وصل» في المواعيد.',
	sections: {
		in_treatment: 'في الفحص',
		called: 'تمّت مناداتهم',
		waiting: 'في الانتظار',
		finished: 'انتهوا اليوم'
	},
	ticket: 'الرقم {number}',
	appointmentAt: 'موعد {time}',
	walkIn: 'دون موعد',
	position: 'الترتيب {position}',
	wait: 'حوالي {min} دقيقة',
	since: 'منذ {time}',
	updated: 'الرقم {number}: {status}.',
	actions: {
		call: 'مناداة',
		start: 'في الفحص',
		done: 'انتهى',
		left: 'غادر',
		qr: 'رمز QR',
		whatsapp: 'واتساب'
	},
	form: {
		title: 'رقم جديد',
		forPatient: 'مريض مسجّل',
		walkIn: 'اسم فقط',
		name: 'الاسم',
		phone: 'الهاتف (اختياري)',
		create: 'إعطاء الرقم',
		needName: 'اكتب اسمًا أو اختر مريضًا.',
		created: 'الرقم {number} لـ {name}'
	},
	qr: {
		title: 'الرقم {number}',
		image: 'رمز QR للرقم {number}',
		hint: 'يصوّر المريض هذا الرمز ليتابع دوره على هاتفه.',
		open: 'فتح صفحة الرقم'
	},
	message: 'مرحبًا، هذا رقمك في {practice}: رقم {number}. تابع دورك هنا: {url}',
	next: {
		title: 'المريض التالي',
		link: 'المريض التالي',
		now: 'الآن',
		then: 'بعد ذلك',
		late: 'متأخّرون',
		lateHint: 'مواعيد بدأت منذ أكثر من 10 دقائق ولم يصل المريض بعد.',
		reasonAppointment: 'موعد {time}',
		reasonWaiting: 'قائمة الانتظار (الرقم {number})',
		nobody: 'لا أحد في الانتظار.',
		call: 'مناداة التالي',
		called: 'تمّت مناداة الرقم {number}: {name}.',
		everyone: 'كل الأطباء',
		loadError: 'تعذّر تحميل قائمة الانتظار.'
	},
	preview: {
		title: 'شاشة قاعة الانتظار',
		called: 'الرقم المنادى',
		next: 'الأرقام القادمة',
		waiting: '{count} في الانتظار – أرقام فقط، دون أسماء'
	}
};
