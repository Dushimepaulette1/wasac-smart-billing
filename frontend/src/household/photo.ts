/**
 * @file photo.ts
 * @description Turn a camera frame or a chosen file into a JPEG of a sensible size.
 * Phone photos are often 3-5 MB. The backend reads at most 1600 px on the long
 * edge, so anything larger only costs mobile data; live-check frames are 640 px.
 */

/** The photo that is read: the backend's own maximum. */
export const PHOTO_MAX_EDGE = 1600;
const PHOTO_QUALITY = 0.85;
/** Live-check frames: small and cheap to send. */
export const FRAME_MAX_EDGE = 640;
const FRAME_QUALITY = 0.6;

function drawScaled(source: CanvasImageSource, width: number, height: number, maxEdge: number): HTMLCanvasElement {
  const scale = Math.min(1, maxEdge / Math.max(width, height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Canvas 2D is not available');
  context.drawImage(source, 0, 0, canvas.width, canvas.height);
  return canvas;
}

/** The current camera frame as the photo to read, or null if the camera has no frame yet. */
export function frameToDataUrl(video: HTMLVideoElement): string | null {
  if (!video.videoWidth) return null;
  return drawScaled(video, video.videoWidth, video.videoHeight, PHOTO_MAX_EDGE).toDataURL('image/jpeg', PHOTO_QUALITY);
}

/** The current camera frame as a small live-check JPEG, or null if there is no frame yet. */
export function frameToBlob(video: HTMLVideoElement): Promise<Blob | null> {
  if (!video.videoWidth) return Promise.resolve(null);
  const canvas = drawScaled(video, video.videoWidth, video.videoHeight, FRAME_MAX_EDGE);
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', FRAME_QUALITY));
}

export function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      try {
        resolve(drawScaled(img, img.naturalWidth, img.naturalHeight, PHOTO_MAX_EDGE).toDataURL('image/jpeg', PHOTO_QUALITY));
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
