import React from 'react';
import styles from './Footer.module.css';

const Footer = () => {
  return (
    <footer className={styles.footer}>
      <div className={styles.divider}></div>
      <p className={styles.copyright} style={{textAlign: 'center', color: 'var(--color-text-dim)', fontSize: '0.8rem', margin: '1rem 0'}}>&copy; 2026 KaggleIngest v1.1</p>
        <div className={styles.socialLinks}>
          <a
            href="https://github.com/Anand-0037"
            target="_blank"
            rel="noopener noreferrer"
            className={styles.socialLink}
            title="GitHub Profile"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path></svg>
          </a>
          <a
            href="https://x.com/AnandVashisht15"
            target="_blank"
            rel="noopener noreferrer"
            className={styles.socialLink}
            title="Follow on X"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 4l11.733 16h4.267l-11.733-16zM4 20l6.768-6.768m2.464-2.464L20 4"></path></svg>
          </a>
          <a
            href="https://discord.gg/b478fmg47q"
            target="_blank"
            rel="noopener noreferrer"
            className={styles.socialLink}
            title="Join Discord"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M7 18.13V22"></path><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="12" r="3"></circle><path d="M6 15h12"></path></svg>
          </a>
        </div>
    </footer>
  );
};

export default Footer;
