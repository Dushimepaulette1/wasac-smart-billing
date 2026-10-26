/**
 * @file useScrolled.ts
 * @description True once the page has scrolled a little: headers are transparent (the same as
 * the page) at the top and only take a blurred background when content passes under them.
 */

import { useEffect, useState } from 'react';

export default function useScrolled(threshold = 8): boolean {
  const [scrolled, setScrolled] = useState(() => typeof window !== 'undefined' && window.scrollY > threshold);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > threshold);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [threshold]);
  return scrolled;
}
