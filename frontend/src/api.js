import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api",
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const refresh = localStorage.getItem("refresh_token");
    const url = String(originalRequest?.url ?? "");

    const shouldRefresh =
      error.response?.status === 401 &&
      Boolean(refresh) &&
      Boolean(originalRequest) &&
      !originalRequest._retried &&
      !url.includes("/auth/login/") &&
      !url.includes("/auth/register/") &&
      !url.includes("/auth/refresh/");

    if (!shouldRefresh) return Promise.reject(error);

    originalRequest._retried = true;

    try {
      const { data } = await axios.post(
        `${api.defaults.baseURL}/auth/refresh/`,
        { refresh }
      );

      if (!data?.access) {
        throw new Error("Refresh endpoint did not return an access token.");
      }

      localStorage.setItem("access_token", data.access);
      originalRequest.headers = originalRequest.headers ?? {};
      originalRequest.headers.Authorization = `Bearer ${data.access}`;
      return api(originalRequest);
    } catch (refreshError) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("username");
      return Promise.reject(refreshError);
    }
  }
);

export const authApi = {
  register: (data) => api.post("/auth/register/", data),
  login: (data) => api.post("/auth/login/", data),
};

export const searchApi = {
  search: (data) => api.post("/search/", data),
};

export const favoritesApi = {
  list: () => api.get("/favorites/"),
  add: (repo) => api.post("/favorites/", repo),
  // Backend urls.py uses favorites/<int:repo_id>/.
  remove: (repoId) => api.delete(`/favorites/${encodeURIComponent(repoId)}/`),
};

export default api;
