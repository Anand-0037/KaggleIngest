// Use environment variable if present, otherwise fallback to empty string (relative path for proxy)
export const API_BASE = import.meta.env.VITE_API_URL || '';

/**
 * Ingest context for a competition or dataset
 */
export async function ingestContext(payload) {
  try {
    let response;

    // Extract slug from URL if it's a competition
    const compMatch = payload.url.match(/kaggle\.com\/competitions\/([a-z0-9-]+)/i);
    const competitionSlug = compMatch ? compMatch[1] : null;

    if (competitionSlug && !payload.token_file) {
      // Use the new competition endpoint
      response = await fetch(`${API_BASE}/api/competitions/${competitionSlug}`, {
        method: 'GET',
      });
    } else if (payload.token_file) {
      // Legacy/Private path with file upload
      const params = new URLSearchParams({
        url: payload.url,
        top_n: payload.top_n,
      });

      const formData = new FormData();
      formData.append('token_file', payload.token_file);

      response = await fetch(`${API_BASE}/api/get-context-upload?${params.toString()}`, {
        method: 'POST',
        body: formData,
      });
    } else {
      // Generic context endpoint
      response = await fetch(`${API_BASE}/api/get-context`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: payload.url,
          top_n: payload.top_n,
          stream: false
        }),
      });
    }

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || `Server error: ${response.status}`);
    }

    const data = await response.json();
    return { success: true, ...data };

  } catch (error) {
    let message = error.message;
    if (message === 'Failed to fetch' || message.includes('NetworkError')) {
      message = "Unable to connect to server. The backend might be offline.";
    }
    return { success: false, error: message };
  }
}

/**
 * Search competitions
 */
export async function searchCompetitions(query) {
  try {
    const response = await fetch(`${API_BASE}/api/search?query=${encodeURIComponent(query)}`);
    if (!response.ok) throw new Error('Search failed');
    return await response.json();
  } catch (error) {
    console.error('Search error:', error);
    return [];
  }
}

/**
 * Check API health
 */
export async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    return await res.json();
  } catch (e) {
    return { status: 'offline', error: e.message };
  }
}
