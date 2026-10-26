/**
 * @file Reveal.tsx
 * @description A section that fades up (from a 2-degree turn) the first time it scrolls into
 * view (.on-scroll in base.css). Without IntersectionObserver, or with reduced motion, it is
 * simply shown.
 */

import { useEffect, useRef, useState, type ElementType, type ReactNode } from 'react';

interface RevealProps {
  as?: ElementType;
  className?: string;
  children: ReactNode;
  [attribute: string]: unknown;
}

function Reveal({ as: Tag = 'div', className, children, ...rest }: RevealProps) {
  const ref = useRef<HTMLElement>(null);
  const [visible, setVisible] = useState(() => typeof IntersectionObserver === 'undefined');
  useEffect(() => {
    if (visible || !ref.current) return undefined;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: '0px 0px -10% 0px' },
    );
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [visible]);
  return (
    <Tag ref={ref} className={['on-scroll', visible ? 'is-visible' : '', className].filter(Boolean).join(' ')} {...rest}>
      {children}
    </Tag>
  );
}

export default Reveal;
