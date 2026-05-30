import axios from 'axios';

// In development, leave baseURL empty so Vite's dev-server proxy handles
// all /api/* requests (forwarding them to http://localhost:8000).
// In production, VITE_API_URL must be set to the Render backend URL.
const API_BASE = import.meta.env.VITE_API_URL || '';

const api = axios.create({ baseURL: API_BASE });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    if (err.response?.status === 401) {
      const refresh = localStorage.getItem('refresh_token');
      if (refresh) {
        try {
          const refreshUrl = API_BASE
            ? `${API_BASE}/api/auth/refresh/`
            : '/api/auth/refresh/';
          const res = await axios.post(refreshUrl, { refresh });
          localStorage.setItem('access_token', res.data.access);
          err.config.headers.Authorization = `Bearer ${res.data.access}`;
          return api(err.config);
        } catch {
          localStorage.clear();
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(err);
  }
);

export const authAPI = {
  login: (email, password) => api.post('/api/auth/token/', { username: email, password }),
  me: () => api.get('/api/auth/me/'),
};

export const ingestionAPI = {
  upload: (file, sourceType) => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('source_type', sourceType);
    return api.post('/api/ingestion/upload/', fd);
  },
  batches: (params) => api.get('/api/ingestion/batches/', { params }),
  records: (params) => api.get('/api/ingestion/records/', { params }),
  record: (id) => api.get(`/api/ingestion/records/${id}/`),
  updateRecord: (id, data) => api.patch(`/api/ingestion/records/${id}/`, data),
  approve: (id) => api.post(`/api/ingestion/records/${id}/approve/`),
  flag: (id, note) => api.post(`/api/ingestion/records/${id}/flag/`, { note }),
  lock: (id) => api.post(`/api/ingestion/records/${id}/lock/`),
  bulkApprove: (ids) => api.post('/api/ingestion/records/bulk-approve/', { ids }),
  summary: (params) => api.get('/api/ingestion/records/summary/', { params }),
  auditLog: (params) => api.get('/api/ingestion/audit-log/', { params }),
};

export default api;
