import type { Messages } from '../fr';

export const appointmentStatus: Messages['appointmentStatus'] = {
	scheduled: 'مبرمج',
	confirmed: 'مؤكَّد',
	arrived: 'وصل',
	in_treatment: 'في الفحص',
	done: 'انتهى',
	no_show: 'غائب',
	cancelled: 'ملغى'
};

export const queueStatus: Messages['queueStatus'] = {
	waiting: 'في الانتظار',
	called: 'تمّت المناداة',
	in_treatment: 'في الفحص',
	done: 'انتهى',
	left: 'غادر'
};

export const paymentMethod: Messages['paymentMethod'] = {
	cash: 'نقدًا',
	d17: 'D17',
	flouci: 'Flouci',
	card: 'بطاقة',
	cheque: 'صكّ',
	transfer: 'تحويل',
	other: 'أخرى'
};
