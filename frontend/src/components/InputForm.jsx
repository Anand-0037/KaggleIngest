import React, { useState, useRef, useEffect } from 'react';
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

  const [showDetails, setShowDetails] = useState(false);
  const [placeholder, setPlaceholder] = useState('');

  // Smart Placeholder Animation
  useEffect(() => {
    const examples = [
      'kaggle.com/c/titanic...',
      'kaggle.com/competitions/house-prices...',
      'kaggle.com/code/alexisbcook/titanic-tutorial...'
    ];
    let currentIdx = 0;
    let charIdx = 0;
    let isDeleting = false;
    let timeoutId;

    const type = () => {
      const currentText = examples[currentIdx];
      if (isDeleting) {
        setPlaceholder(currentText.substring(0, charIdx - 1));
        charIdx--;
      } else {
        setPlaceholder(currentText.substring(0, charIdx + 1));
        charIdx++;
      }

      let speed = 50; // Typing speed (faster)
      if (isDeleting) speed = 30; // Deleting speed

      if (!isDeleting && charIdx === currentText.length) {
        speed = 2000; // Pause at end
        isDeleting = true;
      } else if (isDeleting && charIdx === 0) {
        isDeleting = false;
        currentIdx = (currentIdx + 1) % examples.length;
        speed = 500; // Pause before next word
      }

      timeoutId = setTimeout(type, speed);
    };

    timeoutId = setTimeout(type, 500);
    return () => clearTimeout(timeoutId);
  }, []);

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
        One-click context for <strong>GPT-5.2</strong>, <strong>Claude 4.5</strong>, and <strong>Gemini 3.0</strong>.
      </p>

      <div className={styles.card}>
        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.inputWrapper}>
            <input
              type="text"
              placeholder={placeholder || "Paste Kaggle URL..."}
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
              <li>Token-Optimized Context</li>
              <li>Gold-Medal Patterns</li>
              <li>Instant Feature Engineering</li>
            </ul>
            <div className={styles.toonBox}>
              <span className={styles.toonLabel}>LLM Optimized</span> — <a href="https://github.com/toon-format/toon" target="_blank" rel="noopener noreferrer" className={styles.toonLink}>TOON</a> saves tokens
            </div>
          </div>
        </div>
      </div>

      {/* SEO Content Section */}
      <section className={styles.seoContent}>
        {!showDetails ? (
           <div style={{ textAlign: 'center', marginTop: '2rem', paddingBottom: '2rem' }}>
             <button
               type="button"
               onClick={() => setShowDetails(true)}
               className={styles.fileToggle}
               style={{ fontSize: '14px', color: 'var(--color-text-secondary)', cursor: 'pointer', background: 'none', border: 'none' }}
             >
               Learn how it works ↓
             </button>
           </div>
        ) : (
          <div className={styles.detailsFadeIn}>
            <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
                <button
                type="button"
                onClick={() => setShowDetails(false)}
                className={styles.fileToggle}
                style={{ fontSize: '14px', color: 'var(--color-text-secondary)', cursor: 'pointer', background: 'none', border: 'none' }}
                >
                Close details ↑
                </button>
            </div>

            <h2 className={styles.sectionHeader}>How It Works</h2>
            <div className={styles.contentGrid}>
            <div className={styles.contentCard}>
                <h3>1. Paste URL</h3>
                <p>
                Supports Competitions, Datasets, and Notebooks. We automatically detect and crawl the relevant metadata.
                </p>
            </div>
            <div className={styles.contentCard}>
                <h3>2. We Analyze</h3>
                <p>
                Our engine scans top-scoring notebooks to extract winning architectures and preprocessing steps.
                </p>
            </div>
            <div className={styles.contentCard}>
                <h3>3. You Generate</h3>
                <p>
                Get a TOON-formatted prompt that saves 60% tokens. Paste it into your LLM and start coding.
                </p>
            </div>
            </div>

            <h2 className={styles.sectionHeader}>Why It Matters</h2>
            <p className={styles.longText}>
            Coding assistants hallucinate without context. KaggleIngest gives them the full picture—metrics, schemas, and best practices—so you get working, high-quality code instantly.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}

export default InputForm;
