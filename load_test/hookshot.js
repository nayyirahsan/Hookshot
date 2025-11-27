// Hookshot ingestion load test: 50,000 events split across three endpoint
// classes of varying reliability (100% / 90% / 50%, see receivers.py).
//
// Setup (each in its own terminal, from the repo root):
//   python load_test/receivers.py
//   uvicorn api.main:app --port 8000
//   celery -A worker.celery_app worker --beat --concurrency=8
//   # register the three endpoints:  python load_test/setup_endpoints.py
//
// Run:      k6 run load_test/hookshot.js
// Analyze:  python -m load_test.report   (after the queue drains)

import http from 'k6/http';
import { check } from 'k6';

// Default: 500 events/s for 100s = 50,000 events (saturation burst).
// Steady-state run: k6 run -e SCALE=0.5 -e DURATION=200s load_test/hookshot.js
const SCALE = Number(__ENV.SCALE || 1);
const DURATION = __ENV.DURATION || '100s';

function scenario(rate, eventType) {
  return {
    executor: 'constant-arrival-rate',
    rate: Math.round(rate * SCALE),
    timeUnit: '1s',
    duration: DURATION,
    preAllocatedVUs: 40,
    maxVUs: 200,
    env: { EVENT_TYPE: eventType },
  };
}

export const options = {
  scenarios: {
    reliable: scenario(250, 'load.reliable'),    // -> 100% receiver
    mostly: scenario(150, 'load.mostly'),        // -> 90% receiver
    flaky: scenario(100, 'load.flaky'),          // -> 50% receiver
  },
  thresholds: {
    http_req_duration: ['p(99)<500'],
    http_req_failed: ['rate<0.01'],
  },
};

export default function () {
  const eventType = __ENV.EVENT_TYPE;
  const payload = {
    event_type: eventType,
    data: { order_id: `${__VU}-${__ITER}`, amount: 99.99 },
  };

  const res = http.post('http://localhost:8000/api/events', JSON.stringify(payload), {
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': `k6-${eventType}-${__VU}-${__ITER}`,
    },
  });

  check(res, { 'ingestion accepted': (r) => r.status === 202 });
}
