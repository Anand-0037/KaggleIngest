import React, { useState, useRef } from 'react';
import styles from './InputForm.module.css';

function InputForm({ onSubmit, isLoading, status, initialUrl }) {
  const [url, setUrl] = useState(initialUrl || '');
  const [error, setError] = useState('');

  // Load recent jobs from localStorage during initialization to avoid useEffect setState
  const [recentJobs, setRecentJobs] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('kaggle_recent_jobs') || '[]');
    } catch {
      return [];
    }
  });

  const [showFileUpload, setShowFileUpload] = useState(false);
  const [tokenFile, setTokenFile] = useState(null);
  const fileInputRef = useRef(null);

  const [options, setOptions] = useState({
    top_n: 3,
    output_format: 'toon',
    dry_run: false
  });

  // Handle initial URL from parent (auto-ingest) - using state adjustment during render
  // as recommended by React docs for syncing props to state to avoid cascading renders
  const [prevInitialUrl, setPrevInitialUrl] = useState(initialUrl);
  if (initialUrl !== prevInitialUrl) {
    setPrevInitialUrl(initialUrl);
    setUrl(initialUrl || '');
  }

  const addToHistory = (validUrl) => {
    let newHistory = [validUrl, ...recentJobs.filter(u => u !== validUrl)].slice(0, 5);
    setRecentJobs(newHistory);
    localStorage.setItem('kaggle_recent_jobs', JSON.stringify(newHistory));
  };

  const validateUrl = (inputUrl) => {
    // Allow underscores, dots in slugs, and optional query params
    const kaggleRegex = /^https:\/\/(www\.)?kaggle\.com\/(competitions|datasets|code)\/[\w.-]+(\/[\w.-]+)*\/?(\?.*)?$/;
    if (!inputUrl.match(kaggleRegex)) {
      return "Please enter a valid Kaggle Competition, Dataset, or Notebook URL.";
    }
    return null;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!url) return;

    const validationError = validateUrl(url);
    if (validationError) {
      setError(validationError);
      return;
    }
    setError('');
    addToHistory(url);
    onSubmit({ url, ...options, token_file: tokenFile });
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setTokenFile(e.target.files[0]);
    }
  };

  const loadExample = (exUrl) => {
    setUrl(exUrl);
    setError('');
  };

  const handleNumberChange = (value) => {
    const num = Math.max(1, Math.min(10, parseInt(value) || 1));
    setOptions({ ...options, top_n: num });
  };

  const incrementNumber = () => {
    if (options.top_n < 10) {
      setOptions({ ...options, top_n: options.top_n + 1 });
    }
  };

  const decrementNumber = () => {
    if (options.top_n > 1) {
      setOptions({ ...options, top_n: options.top_n - 1 });
    }
  };

  const getButtonText = () => {
    if (isLoading) {
      if (status?.progress) {
        const { processed, total } = status.progress;
        return `Processing ${processed}/${total}...`;
      }
      return 'Processing...';
    }
    return 'Ingest Context';
  };

  return (
    <div className={styles.heroSection} style={{ padding: '20px 0', marginBottom: '20px' }}>
      <h1 className={styles.heroTitle} style={{ fontSize: '2rem', marginBottom: '8px' }}>
        Welcome to <span style={{ color: 'var(--color-primary)' }}>Kaggle</span>Ingest
      </h1>

      <p className={styles.heroSubtitle} style={{ fontSize: '1rem', margin: 0 }}>
        Turn any Kaggle competition metadata into a simple text digest for your LLM.
      </p>

      <div className={styles.card}>
        {isLoading && status?.progress && (
          <div style={{ marginBottom: '16px', width: '100%' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '12px', color: '#666' }}>
              <span>Progress</span>
              <span>{status.progress.percent}%</span>
            </div>
            <div style={{ height: '6px', background: '#eee', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                width: `${status.progress.percent}%`,
                background: 'var(--color-primary)',
                transition: 'width 0.5s ease'
              }} />
            </div>
          </div>
        )}
        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.inputWrapper}>
            <input
              type="text"
              placeholder="Paste Kaggle URL (Competition or Dataset)..."
              value={url}
              onChange={(e) => { setUrl(e.target.value); setError(''); }}
              disabled={isLoading}
              required
              className={`${styles.input} ${error ? styles.inputError : ''}`}
            />
            {error && <div className={styles.errorMessage}>⚠ {error}</div>}
          </div>
          <button
            type="submit"
            className={styles.submitBtn}
            disabled={isLoading}
          >
            {getButtonText()}
          </button>
        </form>

        {/* Options */}
        <div className={styles.optionsRow}>
          <label className={styles.optionLabel}>
            <span>Output Format</span>
            <select
              value={options.output_format}
              onChange={(e) => setOptions({ ...options, output_format: e.target.value })}
              disabled={isLoading}
              className={styles.select}
            >
              <option value="txt">Text (.txt)</option>
              <option value="toon">TOON (.toon)</option>
              <option value="md">Markdown (.md)</option>
            </select>
          </label>
          <label className={styles.optionLabel}>
            <span>Notebooks</span>
            <div className={styles.numberWrapper}>
              <button
                type="button"
                onClick={decrementNumber}
                disabled={isLoading || options.top_n <= 1}
                className={styles.stepperBtn}
              >
                −
              </button>
              <input
                type="number"
                min="1"
                max="10"
                value={options.top_n}
                onChange={(e) => handleNumberChange(e.target.value)}
                disabled={isLoading}
                className={styles.numberInput}
              />
              <button
                type="button"
                onClick={incrementNumber}
                disabled={isLoading || options.top_n >= 10}
                className={styles.stepperBtn}
              >
                +
              </button>
            </div>
          </label>
        </div>

        {/* File Upload */}
        <div className={styles.fileUploadSection}>
          <button type="button" onClick={() => setShowFileUpload(!showFileUpload)} className={styles.fileToggle}>
            {showFileUpload ? '− Hide Credentials' : '+ Add Private Credentials (kaggle.json)'}
          </button>
          {showFileUpload && (
            <div className={styles.fileInputWrapper}>
              <p style={{ marginBottom: '8px', fontSize: '14px', color: 'var(--color-text-secondary)' }}>
                Upload <code>kaggle.json</code> to access private competitions/datasets.
              </p>
              <input
                type="file"
                accept=".json"
                onChange={handleFileChange}
                ref={fileInputRef}
                style={{ fontSize: '14px' }}
              />
              {tokenFile && <p style={{ marginTop: '8px', fontSize: '13px', color: 'var(--color-success)' }}>✓ {tokenFile.name}</p>}
            </div>
          )}
        </div>

        {/* History */}
        {/* Two-column layout for History and Features */}
        <div className={styles.gridContainer}>

          {/* Left Col: History & Quick Start */}
          <div className={styles.historySection} style={{ marginTop: 0 }}>
            {recentJobs.length > 0 && (
              <div style={{ marginBottom: '16px' }}>
                <p className={styles.sectionTitle} style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>Your History</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {recentJobs.slice(0, 3).map((j, i) => (
                    <button key={i} type="button" className={styles.examplePill} onClick={() => loadExample(j)} title={j} style={{ fontSize: '13px', padding: '6px 12px' }}>
                      {j.replace('https://www.kaggle.com/', '').split('/').pop()}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div>
              <p className={styles.sectionTitle} style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>Try These Competitions</p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                <button type="button" className={styles.examplePill} onClick={() => loadExample('https://www.kaggle.com/competitions/titanic')} style={{ fontSize: '13px', padding: '6px 12px' }}>Titanic</button>
                <button type="button" className={styles.examplePill} onClick={() => loadExample('https://www.kaggle.com/competitions/house-prices-advanced-regression-techniques')} style={{ fontSize: '13px', padding: '6px 12px' }}>House Prices</button>
                <button type="button" className={styles.examplePill} onClick={() => loadExample('https://www.kaggle.com/competitions/digit-recognizer')} style={{ fontSize: '13px', padding: '6px 12px' }}>Digit Recognizer</button>
                <button type="button" className={styles.examplePill} onClick={() => loadExample('https://www.kaggle.com/competitions/store-sales-time-series-forecasting')} style={{ fontSize: '13px', padding: '6px 12px' }}>Store Sales</button>
                <button type="button" className={styles.examplePill} onClick={() => loadExample('https://www.kaggle.com/competitions/nlp-getting-started')} style={{ fontSize: '13px', padding: '6px 12px' }}>NLP Disaster Tweets</button>
              </div>
            </div>
          </div>

          {/* Right Col: Features */}
          <div className={styles.featuresCard}>
            <p className={styles.sectionTitle} style={{ marginBottom: '10px', fontSize: '11px' }}>Capabilities</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--color-text-secondary)' }}>• Feed context to ChatGPT/Claude</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--color-text-secondary)' }}>• Learn from top notebooks</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--color-text-secondary)' }}>• Jumpstart your submission</span>
            </div>
            <p style={{ marginTop: '12px', fontSize: '10px', color: 'var(--color-text-secondary)', borderTop: '1px solid var(--color-border)', paddingTop: '8px' }}>
              <span style={{ color: 'var(--color-primary)', fontWeight: 'bold' }}>LLM Optimized</span> — <a href="/toon.html" target="_blank" style={{ color: 'inherit', textDecoration: 'underline', cursor: 'pointer' }}>TOON</a> saves tokens
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default InputForm;
