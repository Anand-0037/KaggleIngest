import React, { useState, useRef } from 'react';
import styles from './InputForm.module.css';

function InputForm({ onSubmit, isLoading, initialUrl }) {
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
    top_n: 3
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
    // Robust Kaggle URL validation (competitions, datasets, kernels/code)
    const kaggleRegex = /^https:\/\/(www\.)?kaggle\.com\/([a-z0-9-]+)\/([a-z0-9.-]+)(\/[a-z0-9.-]+)*\/?(\?.*)?$/i;
    const match = inputUrl.match(kaggleRegex);
    if (!match) {
      return "Please enter a valid Kaggle Competition, Dataset, or Notebook URL.";
    }
    const type = match[2];
    if (!['competitions', 'datasets', 'code', 'kernels', 'c'].includes(type)) {
      return "Unsupported Kaggle resource type. Please provide a Competition, Dataset, or Notebook.";
    }
    return null;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!url) return;

    const validationError = validateUrl(url.trim());
    if (validationError) {
      setError(validationError);
      return;
    }
    setError('');
    addToHistory(url.trim());
    onSubmit({ url: url.trim(), ...options, token_file: tokenFile });
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
      return 'Ingesting Context...';
    }
    return 'Ingest Context';
  };

  return (
    <div className={styles.heroSection}>
      <h1 className={styles.heroTitle}>
        Welcome to <span style={{ color: 'var(--color-primary)' }}>Kaggle</span>Ingest
      </h1>

      <p className={styles.heroSubtitle}>
        Bridge the gap between Kaggle's vast data and your favorite AI coding assistant. KaggleIngest transforms complex competition metadata into a single, token-optimized context file.
      </p>

      <div className={styles.card}>
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

        {/* Options - Notebook Count Only */}
        <div className={styles.optionsRow}>
          <div className={styles.optionLabel}>
            <span>Notebooks to Analyze</span>
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
          </div>
        </div>

        {/* File Upload */}
        <div className={styles.fileUploadSection}>
          <button type="button" onClick={() => setShowFileUpload(!showFileUpload)} className={styles.fileToggle} style={{ color: showFileUpload ? 'var(--color-text-secondary)' : 'var(--color-primary)' }}>
            {showFileUpload ? '− Hide Credentials' : '+ Add Private Credentials (kaggle.json)'}
          </button>
          {showFileUpload && (
            <div className={styles.fileInputWrapper}>
              <p style={{ marginBottom: '12px', fontSize: '13px', color: 'var(--color-text-secondary)', lineHeight: '1.4' }}>
                Upload <code>kaggle.json</code> to access your private competitions and datasets.
                <span style={{ display: 'block', marginTop: '4px', opacity: 0.7 }}>We never store your keys.</span>
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <input
                  type="file"
                  accept=".json"
                  onChange={handleFileChange}
                  ref={fileInputRef}
                  style={{ fontSize: '13px' }}
                />
                {tokenFile && <span style={{ fontSize: '13px', color: 'var(--color-success)', fontWeight: '500' }}>✓ {tokenFile.name}</span>}
              </div>
            </div>
          )}
        </div>

        {/* History and Discovery */}
        <div className={styles.gridContainer}>

          {/* Left Col: History & Discovery */}
          <div className={styles.discoverySection}>
            {recentJobs.length > 0 && (
              <div style={{ marginBottom: '24px' }}>
                <p className={styles.sectionTitle}>Your History</p>
                <div className={styles.pillCloud}>
                  {recentJobs.slice(0, 3).map((j, i) => (
                    <button key={i} type="button" className={styles.examplePill} onClick={() => loadExample(j)} title={j}>
                      {j.replace('https://www.kaggle.com/', '').split('/').pop().split('?')[0]}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div>
              <p className={styles.sectionTitle}>Try These Competitions</p>
              <div className={styles.pillCloud}>
                <button type="button" className={styles.examplePill} onClick={() => loadExample('https://www.kaggle.com/competitions/titanic')}>Titanic</button>
                <button type="button" className={styles.examplePill} onClick={() => loadExample('https://www.kaggle.com/competitions/house-prices-advanced-regression-techniques')}>House Prices</button>
                <button type="button" className={styles.examplePill} onClick={() => loadExample('https://www.kaggle.com/competitions/digit-recognizer')}>Digit Recognizer</button>
                <button type="button" className={styles.examplePill} onClick={() => loadExample('https://www.kaggle.com/competitions/store-sales-time-series-forecasting')}>Store Sales</button>
                <button type="button" className={styles.examplePill} onClick={() => loadExample('https://www.kaggle.com/competitions/nlp-getting-started')}>NLP Disaster Tweets</button>
              </div>
            </div>
          </div>

          {/* Right Col: Capabilities */}
          <div className={styles.featuresCard}>
            <p className={styles.sectionTitle}>Capabilities</p>
            <ul className={styles.featureList}>
              <li>Feed context to ChatGPT/Claude</li>
              <li>Learn from top notebooks</li>
              <li>Jumpstart your submission</li>
            </ul>
            <div className={styles.toonBox}>
              <span className={styles.toonLabel}>LLM Optimized</span> — <a href="https://github.com/toon-format/toon" target="_blank" rel="noopener noreferrer" className={styles.toonLink}>TOON</a> saves tokens
            </div>
          </div>
        </div>
      </div>

      {/* SEO Content Section */}
      <section className={styles.seoContent}>
        <h2 className={styles.sectionHeader}>How KaggleIngest Works</h2>
        <div className={styles.contentGrid}>
          <div className={styles.contentCard}>
            <h3>1. Intelligent Ingestion</h3>
            <p>
              Paste any Kaggle URL — whether it's a <strong>competition</strong>, a <strong>dataset</strong>, or a <strong>notebook (kernel)</strong>. Our backend identifies the resource and prepares to crawl the most relevant metadata, including overview descriptions, evaluation metrics, and discussion themes.
            </p>
          </div>
          <div className={styles.contentCard}>
            <h3>2. Top Notebook Analysis</h3>
            <p>
              Don't just look at the data; learn from the best. KaggleIngest can analyze the top performing notebooks for any competition. It extracts high-level code patterns, preprocessing steps, and model architectures, giving your AI assistant the deep insight it needs to generate winning code.
            </p>
          </div>
          <div className={styles.contentCard}>
            <h3>3. TOON Format Optimization</h3>
            <p>
              Context is expensive. Large datasets can easily overflow an LLM's context window. We use the <strong>TOON (Token Optimized Object Notation)</strong> format to drastically reduce token usage without losing critical information. This ensures you can fit more historical context and structural metadata into every prompt.
            </p>
          </div>
        </div>

        <h2 className={styles.sectionHeader}>Why use LLM Context for Kaggle?</h2>
        <p className={styles.longText}>
          Traditional coding assistants struggle with the specific constraints and hidden details of Kaggle competitions. By providing a curated <strong>LLM context</strong>, you allow models like GPT-4, Claude 3.5, or Gemini 1.5 Pro to understand the competition's unique evaluation metric, the underlying data structure, and the community's best practices. This leads to fewer hallucinations, better feature engineering suggestions, and a significantly faster iteration cycle. Whether you are aiming for a Gold medal or just getting started with a new dataset, KaggleIngest is your shortcut to professional-grade machine learning workflows.
        </p>
      </section>
    </div>
  );
}

export default InputForm;
