import type { Messages } from '../fr';
import { errorsKunden } from './errors-kunden';

export const errors: Messages['errors'] = {
	network: 'لا يوجد اتصال بالخادم. يرجى التحقق من اتصال الإنترنت.',
	server: 'الخادم لا يستجيب حاليًا. يرجى المحاولة بعد لحظات.',
	unexpected: 'ردّ غير متوقع من الخادم.',
	generic: 'لم تنجح العملية.',
	unauthorized: 'يرجى تسجيل الدخول.',
	forbidden: 'لا تملكون صلاحية هذا الإجراء.',
	not_found: 'غير موجود.',
	validation: 'البيانات المدخلة غير صالحة.',
	too_many_requests: 'محاولات كثيرة. يرجى المحاولة لاحقًا.',
	invalid_credentials: 'البريد الإلكتروني أو كلمة المرور غير صحيحة.',
	wrong_password: 'كلمة المرور الحالية غير صحيحة.',
	password_too_short: 'يجب أن تحتوي كلمة المرور على 10 أحرف على الأقل.',
	password_too_long: 'كلمة المرور طويلة جدًا.',
	passwords_differ: 'كلمتا المرور غير متطابقتين.',
	invitation_invalid: 'هذه الدعوة غير صالحة أو منتهية أو سبق استعمالها.',
	invitation_incomplete: 'هذا الرابط غير مكتمل. افتحوا الرابط كاملًا كما وصلكم في الدعوة.',
	email_taken: 'يوجد حساب مسجّل بهذا البريد الإلكتروني.',
	invalid_phone: 'رقم الهاتف غير صالح.',
	demo_expired: 'انتهت النسخة التجريبية. يمكنكم بدء نسخة جديدة.',
	server_error: 'حدث خطأ.',
	...errorsKunden
};
