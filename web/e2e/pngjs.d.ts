/** The part of `pngjs` the label E2E test uses (reading a PNG to decode its QR code). */
declare module 'pngjs' {
	export const PNG: { sync: { read(buffer: Buffer): { width: number; height: number; data: Buffer } } };
}
