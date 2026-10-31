// The id of the file, reactive when the app goes from one patient to another (same page component).
export const load = ({ params }: { params: { id: string } }) => ({ id: Number(params.id) });
