"""Register the three load-test endpoints against a running API."""

import httpx

ENDPOINTS = [
    ("http://127.0.0.1:9201/hooks", ["load.reliable"]),
    ("http://127.0.0.1:9202/hooks", ["load.mostly"]),
    ("http://127.0.0.1:9203/hooks", ["load.flaky"]),
]


def main() -> None:
    for url, event_types in ENDPOINTS:
        response = httpx.post(
            "http://localhost:8000/api/endpoints",
            json={"url": url, "secret": "load-test-secret", "event_types": event_types},
        )
        response.raise_for_status()
        print(f"registered {url} -> {event_types}")


if __name__ == "__main__":
    main()
