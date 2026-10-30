// The payment of the receipt (reactive when another receipt is opened from the same page component).
export const load = ({ params }: { params: { paymentId: string } }) => ({ paymentId: Number(params.paymentId) });
