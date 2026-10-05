/**
 * @file SkeletonLoader.jsx
 * @description Shimmer placeholder component for async content loading states.
 * Renders warm-toned animated skeleton blocks matching the shape of expected content.
 */

import React from 'react';
import styles from './SkeletonLoader.module.css';

/**
 * @typedef {Object} SkeletonLoaderProps
 * @property {string|number} [width='100%'] - Width of the skeleton block
 * @property {string|number} [height=16] - Height of the skeleton block in px (or CSS string)
 * @property {string} [borderRadius] - Border radius override (uses CSS string)
 * @property {number} [count=1] - Number of skeleton lines to render
 * @property {string} [className] - Additional class names
 */

/**
 * SkeletonLoader component — shimmer-animated placeholder blocks.
 */
function SkeletonLoader({
  width = '100%',
  height = 16,
  borderRadius,
  count = 1,
  className = '',
}) {
  const normalizeSize = (val) =>
    typeof val === 'number' ? `${val}px` : val;

  const inlineStyle = {
    width: normalizeSize(width),
    height: normalizeSize(height),
    ...(borderRadius ? { borderRadius } : {}),
  };

  const items = Array.from({ length: count }, (_, i) => (
    <span
      key={i}
      className={[styles.skeleton, className].filter(Boolean).join(' ')}
      style={inlineStyle}
      aria-hidden="true"
    />
  ));

  if (count === 1) {
    return items[0];
  }

  return (
    <div
      className={styles.stack}
      role="status"
      aria-label="Loading content"
    >
      {items}
    </div>
  );
}

export default SkeletonLoader;
