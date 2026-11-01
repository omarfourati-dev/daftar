import type { Messages } from '../fr';

/** سجلّ التعديلات في المخزون والنظافة: من غيّر ماذا ومتى، القديم ← الجديد. */
export const audit: Messages['audit'] = {
	entry: '{date} – {user} {what}',
	reason: 'السبب: {reason}',
	change: '{field}: {before} ← {after}',
	empty: 'لا توجد تصحيحات بعد.',
	loadError: 'تعذّر تحميل السجلّ.',
	yes: 'نعم',
	no: 'لا',
	none: '–',
	what: {
		stock_receipt: { delete: 'حذف استلام يوم {date} ({total})' },
		stock_receipt_line: { update: 'صحّح استلام يوم {date}: {product}' },
		stock_movement: { delete: 'حذف: {kind} {quantity} {product}' },
		stock_product: { update: 'عدّل المنتج «{name}»', delete: 'حذف المنتج «{name}»' },
		supplier: { update: 'عدّل المزوّد «{name}»', delete: 'حذف المزوّد «{name}»' },
		hygiene_task: { update: 'عدّل المهمة «{name}»', delete: 'حذف المهمة «{name}»' },
		equipment: { update: 'عدّل الجهاز «{name}»', delete: 'حذف الجهاز «{name}»' },
		hygiene_task_done: {
			update: 'صحّح «{name}» بتاريخ {date} (أنجزها {by})',
			delete: 'ألغى «{name}» بتاريخ {date} (أنجزها {by})'
		},
		other: 'عدّل معطًى'
	},
	fields: {
		name: 'الاسم',
		category: 'الصنف',
		unit: 'الوحدة',
		supplier: 'المزوّد',
		minQuantity: 'حدّ الطلب',
		note: 'ملاحظة',
		ean: 'رمز EAN',
		active: 'مفعّل',
		phone: 'الهاتف',
		whatsapp: 'واتساب',
		title: 'المهمة',
		equipment: 'الجهاز',
		frequency: 'التواتر',
		weekday: 'اليوم',
		intervalDays: 'عدد الأيام',
		startsOn: 'المرة الأولى',
		instructions: 'التعليمات',
		kind: 'النوع',
		serialNumber: 'الرقم التسلسلي',
		quantity: 'الكمية',
		unitPriceMillimes: 'سعر الوحدة',
		result: 'النتيجة'
	}
};
