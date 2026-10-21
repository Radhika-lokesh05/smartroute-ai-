export function formatAuthError(err: any, fallbackMessage: string): string {
  if (err?.response?.data?.detail) {
    const detail = err.response.data.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail.map((d: any) => d.msg || JSON.stringify(d)).join(', ');
    }
  }
  if (err?.code === 'ERR_NETWORK' || err?.message === 'Network Error' || !err?.response) {
    return 'Cannot connect to backend server at http://127.0.0.1:8000. Please ensure the backend is running.';
  }
  return fallbackMessage;
}
