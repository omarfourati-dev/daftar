import type { Messages } from '../fr';

export const caisse: Messages['caisse'] = {
	title: 'الصندوق',
	previousDay: 'اليوم السابق',
	nextDay: 'اليوم التالي',
	today: 'اليوم',
	pickDay: 'اختيار اليوم',
	total: 'المقبوض اليوم',
	byMethod: 'حسب طريقة الدفع',
	payments: 'دفعات اليوم',
	noPayments: 'لا توجد دفعات في هذا اليوم.',
	receipt: 'وصل',
	deposit: 'عربون',
	loadError: 'تعذّر تحميل الصندوق.',
	closing: {
		title: 'غلق الصندوق',
		hint: 'عُدّ النقود الموجودة في الصندوق وسجّل المبلغ.',
		expected: 'النقد المنتظر',
		counted: 'النقد المعدود (د.ت)',
		countedShort: 'النقد المعدود',
		note: 'ملاحظة (اختياري)',
		close: 'غلق الصندوق',
		recount: 'إعادة العدّ',
		difference: 'الفارق',
		exact: 'الصندوق مضبوط.',
		missing: 'نقص {amount}',
		surplus: 'زيادة {amount}',
		closedBy: 'أغلقه {name} على الساعة {time}',
		verify: 'المصادقة على الغلق',
		verifiedBy: 'صادق عليه {name} في {date}',
		waiting: 'في انتظار مصادقة صاحب العيادة.',
		stale: 'تغيّرت الدفعات بعد الغلق. أعد عدّ الصندوق.',
		invalid: 'أدخل المبلغ المعدود (0 إن كان الصندوق فارغًا).'
	},
	balances: {
		title: 'المبالغ المستحقّة',
		hint: 'المرضى الذين ما زالوا مدينين، من الأكبر إلى الأصغر.',
		total: 'المجموع المستحقّ: {amount}',
		largest: 'أكبر {shown} مبلغًا من أصل {count} مريضًا',
		lastPayment: 'آخر دفعة: {date}',
		never: 'لا توجد دفعات',
		empty: 'لا توجد مبالغ مستحقّة. تمّ دفع كل شيء.'
	}
};
