/**
 * @file photo.ts
 * @description Turn a camera frame or a chosen file into a small JPEG.
 * Phone photos are often 3-5 MB; at most 1280px on the long edge is enough
 * for the digit reader and much cheaper to send on mobile data.
 */

const MAX_EDGE = 1280;
const QUALITY = 0.85;

function drawScaled(source: CanvasImageSource, width: number, height: number): string {
  const scale = Math.min(1, MAX_EDGE / Math.max(width, height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Canvas 2D is not available');
  context.drawImage(source, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL('image/jpeg', QUALITY);
}

export function frameToDataUrl(video: HTMLVideoElement): string {
  return drawScaled(video, video.videoWidth, video.videoHeight);
}

export function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      try {
        resolve(drawScaled(img, img.naturalWidth, img.naturalHeight));
      } catch (err) {
        reject(err);
      } finally {
        URL.revokeObjectURL(url);
      }
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Not an image'));
    };
    img.src = url;
  });
}

export function dataUrlToBlob(dataUrl: string): Blob {
  const [head = '', base64 = ''] = dataUrl.split(',');
  const type = /data:([^;]+)/.exec(head)?.[1] || 'image/jpeg';
  const bytes = atob(base64);
  const array = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i += 1) array[i] = bytes.charCodeAt(i);
  return new Blob([array], { type });
}
