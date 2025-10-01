import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter } from 'k6/metrics';

const failedDeliveries = new Counter('failed_deliveries');

export const options = {
  scenarios: {
    reliable_endpoint: {
      executor: 'constant-arrival-rate',
      rate: 100,
      duration: '60s',
      preAllocatedVUs: 20,
    },
    unreliable_endpoint: {
      executor: 'constant-arrival-rate',
      rate: 50,
      duration: '60s',
      preAllocatedVUs: 10,
      startTime: '10s',
    }
  },
  thresholds: {
    http_req_duration: ['p99<500'],
    http_req_failed: ['rate<0.01'],
  },
};

export default function () {
  const payload = {
    event_type: 'order.created',
    data: { order_id: Math.random().toString(36).substr(2, 9), amount: 99.99 }
  };

  const res = http.post(
    'http://localhost:8000/api/events',
    JSON.stringify(payload),
    {
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': `k6-${Date.now()}-${Math.random()}`,
      }
    }
  );

  check(res, { 'ingestion accepted': r => r.status === 202 });
  sleep(0.01);
}
