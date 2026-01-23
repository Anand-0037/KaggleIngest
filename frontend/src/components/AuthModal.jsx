import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import styles from './AuthModal.module.css';

const AuthModal = ({ isOpen, onClose }) => {
  const { signup, login, isAuthenticated, user, logout } = useAuth();
  const [isSignup, setIsSignup] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      if (isSignup) {
        const res = await signup(email, password);
        if (res.success) {
          onClose();
        } else {
          setError(res.error);
        }
      } else {
        // Simple API Key entry
        if (!apiKey.trim()) {
          setError('API Key is required');
          return;
        }
        login(apiKey.trim());
        onClose();
      }
    } catch {
      setError('An error occurred. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={e => e.stopPropagation()}>
        <button className={styles.closeBtn} onClick={onClose}>&times;</button>

        {isAuthenticated ? (
          <div className={styles.profile}>
            <h2>Account</h2>
            <div className={styles.userInfo}>
              <p><strong>Email:</strong> {user?.email}</p>
              <p><strong>Tier:</strong> <span className={styles.tier}>{user?.tier}</span></p>
              <p><strong>Credits:</strong> {user?.credits}</p>
            </div>
            <button onClick={logout} className={styles.logoutBtn}>Logout</button>
          </div>
        ) : (
          <>
            <h2>{isSignup ? 'Create Account' : 'Existing User'}</h2>
            <p className={styles.subtitle}>
              {isSignup
                ? 'Join KaggleIngest to get your own API key and credits.'
                : 'Enter your API key to continue.'}
            </p>

            <form onSubmit={handleSubmit} className={styles.form}>
              {isSignup ? (
                <>
                  <div className={styles.inputGroup}>
                    <label>Email</label>
                    <input
                      type="email"
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                      placeholder="you@example.com"
                      required
                    />
                  </div>
                  <div className={styles.inputGroup}>
                    <label>Password</label>
                    <input
                      type="password"
                      value={password}
                      onChange={e => setPassword(e.target.value)}
                      placeholder="Min 8 characters"
                      required
                    />
                  </div>
                </>
              ) : (
                <div className={styles.inputGroup}>
                  <label>API Key</label>
                  <input
                    type="text"
                    value={apiKey}
                    onChange={e => setApiKey(e.target.value)}
                    placeholder="ki_..."
                    required
                  />
                </div>
              )}

              {error && <div className={styles.error}>{error}</div>}

              <button type="submit" className={styles.submitBtn} disabled={isLoading}>
                {isLoading ? 'Processing...' : (isSignup ? 'Sign Up' : 'Authenticate')}
              </button>
            </form>

            <div className={styles.toggle}>
              {isSignup ? (
                <span>Already have a key? <button onClick={() => setIsSignup(false)}>Enter Key</button></span>
              ) : (
                <span>New here? <button onClick={() => setIsSignup(true)}>Create Account</button></span>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default AuthModal;
