import React from 'react';
import styles from './Footer.module.css';

const Footer = () => {
  return (
    <footer className={styles.footer}>
      <div className={styles.divider}></div>
      <p className={styles.copyright} style={{textAlign: 'center', color: 'var(--color-text-dim)', fontSize: '0.8rem', margin: '1rem 0'}}>&copy; 2026 KaggleIngest v1.2</p>
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
            <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
              <path d="M20.317 4.3698a19.7913 19.7913 0 0 0-4.8851-1.5152.0741.0741 0 0 0-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 0 0-.0785-.037 19.7363 19.7363 0 0 0-4.8852 1.515.0699.0699 0 0 0-.0321.0272C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 0 0 .0312.0561 19.9035 19.9035 0 0 0 5.9937 3.0314.0777.0777 0 0 0 .0842-.0276 14.09 14.09 0 0 0 1.2265-1.9942.076.076 0 0 0-.0416-.1057 13.1141 13.1141 0 0 1-1.872-1.249.0763.0763 0 0 1-.0067-.1278c.0894-.0696.179-.1402.2612-.213a.075.075 0 0 1 .0816-.0104c3.9634 1.833 8.2693 1.833 12.069 0a.0759.0759 0 0 1 .0817.0105c.0822.0728.1718.1434.2612.213a.0763.0763 0 0 1-.0067.1278 12.721 12.721 0 0 1-1.8732 1.2497.0758.0758 0 0 0-.041.1052c.368.669.773 1.3485 1.2265 1.9942a.0773.0773 0 0 0 .0842.0276 19.7944 19.7944 0 0 0 6.0028-3.0314.077.077 0 0 0 .0321-.0544c.501-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 0 0-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189z"/>
            </svg>
          </a>
        </div>
    </footer>
  );
};

export default Footer;
