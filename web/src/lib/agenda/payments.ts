/** Payment methods (backend tables.PAYMENT_METHODS); texts: `t(\`paymentMethod.${m}\`)`. */
export const PAYMENT_METHODS = ['cash', 'd17', 'flouci', 'card', 'cheque', 'transfer', 'other'] as const;
export type PaymentMethod = (typeof PAYMENT_METHODS)[number];
