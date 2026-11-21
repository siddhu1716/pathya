/** When a photo was taken: EXIF DateTimeOriginal for JPEGs (the camera's local time), else the file's time.
 * A photo taken with the camera right now gets "now" either way. */
export async function photoTime(file: File): Promise<number> {
  try {
    const exif = await exifTime(file);
    if (exif) return exif;
  } catch { /* not a readable JPEG */ }
  return file.lastModified || Date.now();
}

async function exifTime(file: File): Promise<number | null> {
  const v = new DataView(await file.slice(0, 256 * 1024).arrayBuffer());
  if (v.byteLength < 4 || v.getUint16(0) !== 0xffd8) return null;
  let off = 2;
  while (off + 4 < v.byteLength) {
    const marker = v.getUint16(off);
    const size = v.getUint16(off + 2);
    if (marker === 0xffe1 && v.getUint32(off + 4) === 0x45786966) return tiffTime(v, off + 10);   // "Exif"
    if ((marker & 0xff00) !== 0xff00) return null;
    off += 2 + size;
  }
  return null;
}

function tiffTime(v: DataView, tiff: number): number | null {
  const little = v.getUint16(tiff) === 0x4949;
  const u16 = (o: number) => v.getUint16(tiff + o, little);
  const u32 = (o: number) => v.getUint32(tiff + o, little);
  const entries = (ifd: number) => Array.from({ length: u16(ifd) }, (_, i) => ifd + 2 + i * 12);
  const text = (e: number) => {
    const n = u32(e + 4), at = n > 4 ? u32(e + 8) : e + 8;
    return Array.from({ length: Math.min(n, 19) }, (_, i) => String.fromCharCode(v.getUint8(tiff + at + i))).join("");
  };
  const ifd0 = u32(4);
  let found: string | null = null;
  for (const e of entries(ifd0)) {
    const tag = u16(e);
    if (tag === 0x0132) found = found ?? text(e);                         // DateTime
    if (tag === 0x8769) {                                                  // Exif sub-IFD
      for (const x of entries(u32(e + 8))) if (u16(x) === 0x9003) found = text(x);   // DateTimeOriginal
    }
  }
  const m = found?.match(/^(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})/);
  if (!m) return null;
  const t = new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]).getTime();
  return Number.isFinite(t) && t > 0 ? t : null;
}

/** A smaller JPEG for upload (quicker on mobile data, still sharp enough to read a prescription). Falls back to the
 * original when the browser cannot decode it (e.g. HEIC outside Safari). */
export async function shrink(file: File, max = 1800, quality = 0.85): Promise<Blob> {
  try {
    const img = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, max / Math.max(img.width, img.height));
    if (scale === 1 && file.type === "image/jpeg" && file.size < 1.5 * 1024 * 1024) return file;
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(img.width * scale);
    canvas.height = Math.round(img.height * scale);
    canvas.getContext("2d")!.drawImage(img, 0, 0, canvas.width, canvas.height);
    img.close();
    const blob = await new Promise<Blob | null>((ok) => canvas.toBlob(ok, "image/jpeg", quality));
    return blob && blob.size < file.size ? blob : file;
  } catch {
    return file;
  }
}
