/**
 * @file PageHeader.tsx
 * @description Top-of-page header component with optional back navigation,
 * title/subtitle display, and a right-side actions slot.
 * Supports a transparent variant for screens with image or dark backgrounds.
 */

import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import styles from './PageHeader.module.css';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  /** Route to navigate back to; without it, back goes through history. */
  backHref?: string;
  /** Screen-reader label for the back button. */
  backLabel?: string;
  /** Right-side action elements (e.g. buttons). */
  actions?: ReactNode;
  variant?: 'default' | 'transparent';
}

/**
 * Left-arrow chevron SVG icon for the back button.
 */
function ChevronLeft() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 20 20"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M12.5 15L7.5 10L12.5 5"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/**
 * PageHeader component — consistent top navigation / title bar.
 */
function PageHeader({
  title,
  subtitle,
  backHref,
  backLabel = 'Back',
  actions,
  variant = 'default',
}: PageHeaderProps) {
  const navigate = useNavigate();

  const handleBack = () => {
    if (backHref) {
      navigate(backHref);
    } else {
      navigate(-1);
    }
  };

  const headerClass = [
    styles.header,
    styles[`variant-${variant}`],
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <header className={headerClass}>
      <div className={styles.inner}>
        {/* Left: back button */}
        <div className={styles.left}>
          {backHref !== undefined && (
            <button
              type="button"
              className={styles.backButton}
              onClick={handleBack}
              aria-label={backLabel}
            >
              <ChevronLeft />
            </button>
          )}
        </div>

        {/* Center: title block */}
        <div className={styles.center}>
          {title && <h1 className={styles.title}>{title}</h1>}
          {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
        </div>

        {/* Right: action slot */}
        <div className={styles.right}>
          {actions || null}
        </div>
      </div>
    </header>
  );
}

export default PageHeader;
