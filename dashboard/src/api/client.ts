const API_BASE = "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  return response.json();
}

export interface Endpoint {
  id: string;
  url: string;
  event_types: string[];
  active: boolean;
  ema_recovery_ms: number;
  failure_rate: number;
  consecutive_failures: number;
  last_success_at: string | null;
  last_failure_at: string | null;
  health_score: number;
  created_at: string;
}

export interface Delivery {
  id: string;
  event_id: string;
  endpoint_id: string;
  event_type: string;
  endpoint_url: string;
  attempt_number: number;
  status_code: number | null;
  latency_ms: number | null;
  outcome: string;
  attempted_at: string;
}

export interface DeadLetter {
  id: string;
  event_id: string;
  endpoint_id: string;
  final_attempt_at: string | null;
  retry_count: number;
  last_error: string | null;
  created_at: string;
  event_type: string | null;
  endpoint_url: string | null;
}

export interface Stats {
  events_today: number;
  delivery_success_rate: number;
  mean_delivery_latency_ms: number;
  dead_letter_count: number;
}

export interface PaginatedDeliveries {
  items: Delivery[];
  total: number;
  page: number;
  page_size: number;
}

export interface PaginatedDeadLetters {
  items: DeadLetter[];
  total: number;
  page: number;
  page_size: number;
}

export const api = {
  getEndpoints: () => request<Endpoint[]>("/api/endpoints"),
  getEndpoint: (id: string) => request<Endpoint>(`/api/endpoints/${id}`),
  getDeliveries: (limit = 50) => request<Delivery[]>(`/api/deliveries?limit=${limit}`),
  getEndpointDeliveries: (id: string, page = 1) =>
    request<PaginatedDeliveries>(`/api/endpoints/${id}/deliveries?page=${page}&page_size=20`),
  getStats: () => request<Stats>("/api/stats"),
  getDeadLetters: (page = 1) =>
    request<PaginatedDeadLetters>(`/api/dead-letters?page=${page}&page_size=20`),
  retryDeadLetter: (id: string) =>
    request<DeadLetter>(`/api/dead-letters/${id}/retry`, { method: "POST" }),
  retryAllDeadLetters: () =>
    request<{ retried_count: number }>("/api/dead-letters/retry-all", { method: "POST" }),
};
