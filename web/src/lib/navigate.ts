/** Leaving the app for another site (payment page). Swappable in tests. */
export const navigation = {
	assign: (url: string): void => location.assign(url)
};
