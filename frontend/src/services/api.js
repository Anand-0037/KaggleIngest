export const API_BASE = import.meta.env.VITE_API_URL || '';


export async function ingestContext(payload) {
  try {
    let response;

    if (payload.token_file) {
      // File upload: Use multipart/form-data + query params (works with legacy GET endpoint)
      const params = new URLSearchParams({
        url: payload.url,
        top_n: payload.top_n,
        output_format: payload.output_format,
        dry_run: payload.dry_run,
      });

      const formData = new FormData();
      formData.append('token_file', payload.token_file);

      response = await fetch(`${API_BASE}/get-context-upload?${params.toString()}`, {
        method: 'POST',
        body: formData,
      });
    } else {
      // No file: Use JSON body (new POST endpoint contract)
      response = await fetch(`${API_BASE}/get-context`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: payload.url,
          top_n: payload.top_n,
          output_format: payload.output_format,
          dry_run: payload.dry_run,
          stream: false
        }),
      });
    }

    if (!response.ok) {
      let errorMsg = 'Unknown error';
      try {
        const errData = await response.json();
        if (errData.detail) {
          errorMsg = typeof errData.detail === 'string'
            ? errData.detail
            : JSON.stringify(errData.detail);
        } else {
          errorMsg = JSON.stringify(errData);
        }
      } catch {
        errorMsg = response.statusText;
      }
      throw new Error(errorMsg);
    }

    // Return JSON response (Job ID)
    const data = await response.json();
    return { success: true, ...data }; // data includes job_id, status, message

  } catch (error) {
    console.error("API Error:", error);
    return { success: false, error: error.message };
  }
}

export async function pollJobStatus(jobId) {
  try {
    const res = await fetch(`${API_BASE}/jobs/${jobId}`);
    if (!res.ok) throw new Error("Failed to check status");
    return await res.json();
  } catch (error) {
    return { status: 'error', error: error.message };
  }
}

export function getJobDownloadUrl(jobId, format = 'txt') {
  return `${API_BASE}/jobs/${jobId}/download?format=${format}`;
}

export async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    return await res.json();
  } catch (e) {
    return { status: 'offline', error: e.message };
  }
}
