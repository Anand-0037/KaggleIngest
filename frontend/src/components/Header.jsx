import React from 'react';
import { useTheme } from '../context/ThemeContext';
import styles from './Header.module.css';

const Header = () => {
  const { theme, toggleTheme } = useTheme();

  return (
    <div className={styles.header}>
      <div className={styles.logoContainer}>
        <img src="/logo.svg" alt="KI" style={{ width: '28px', height: '28px', borderRadius: '6px' }} />
        <span style={{ color: '#20BEFF' }}>Kaggle</span><span style={{ color: 'var(--color-text)' }}>Ingest</span>
      </div>
      <div className={styles.navLinks}>
        {/* Theme Toggle */}
        <button onClick={toggleTheme} className="btn-icon" title="Toggle Theme" style={{ fontSize: '14px' }}>
          {theme === 'dark' ? (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="5" /><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          )}
        </button>

        <a href="/llms.txt" target="_blank" className={styles.llmsLink}>
          /llms.txt
        </a>
        <a href="#" className={styles.githubLink}>GitHub</a>
      </div>
    </div>
  );
};

export default Header;
