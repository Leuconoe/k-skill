import contextlib
import importlib.util
import io
import json
import os
import pathlib
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "seoul-weather-risk" / "scripts" / "seoul_weather_risk.py"
SPEC = importlib.util.spec_from_file_location("seoul_weather_risk", MODULE_PATH)
seoul_weather_risk = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = seoul_weather_risk
SPEC.loader.exec_module(seoul_weather_risk)


PRODUCT_ID = "weather_place_risk_window"
PRODUCT_IDS = sorted(seoul_weather_risk.EXACT_PRODUCT_IDS)


def bundle(product_ids=PRODUCT_IDS):
    return {
        "bundle_id": "seoul-weather-risk",
        "registration_ready": True,
        "products": [
            {"product_id": product_id, "publication_id": "publication-1", "registration_ready": True, "blockers": []}
            for product_id in product_ids
        ],
    }


def detail(product_id=PRODUCT_ID):
    return {
        "bundle_id": "seoul-weather-risk",
        "product_id": product_id,
        "publication_id": "publication-1",
        "registration_ready": True,
        "blockers": [],
        "metadata": {
            "columns": [
                {"name": "place_id", "type": "string"},
                {"name": "forecast_at", "type": "string"},
                {"name": "risk_labels", "type": "string"},
            ]
        },
    }


def data(product_id=PRODUCT_ID, limit=100):
    return {
        "bundle_id": "seoul-weather-risk",
        "product_id": product_id,
        "publication_id": "publication-1",
        "row_count": 1,
        "limit": limit,
        "has_more": False,
        "next_cursor": None,
        "rows": [{"place_id": "place-a", "forecast_at": "2026-08-05T09:00:00+09:00", "risk_labels": "폭염후보"}],
    }


class MockApi:
    def __init__(self):
        self.responses = {}
        self.requests = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def handler(self):
        api = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                api.requests.append({"path": parsed.path, "query": parse_qs(parsed.query), "authorization": self.headers.get("Authorization")})
                status, content_type, body, headers = api.responses.get(parsed.path, (404, "application/problem+json", {"code": "unknown_product", "detail": "not found"}, {}))
                encoded = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, *_args):
                return

        return Handler

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.server.server_port}/"

    def start(self):
        self.thread.start()
        return self

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


class ApiClientTests(unittest.TestCase):
    def setUp(self):
        self.api = MockApi().start()
        self.previous = {name: os.environ.get(name) for name in (seoul_weather_risk.API_KEY_ENV, seoul_weather_risk.API_BASE_URL_ENV)}
        os.environ[seoul_weather_risk.API_KEY_ENV] = "test-api-key"
        os.environ[seoul_weather_risk.API_BASE_URL_ENV] = self.api.base_url
        self.api.responses = {
            "/skill/v1/bundles/seoul-weather-risk": (200, "application/json", bundle(), {}),
            f"/skill/v1/products/{PRODUCT_ID}": (200, "application/json", detail(), {}),
            f"/skill/v1/products/{PRODUCT_ID}/data": (200, "application/json", data(), {}),
        }

    def tearDown(self):
        self.api.close()
        for name, value in self.previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_query_uses_skill_paths_bearer_auth_and_bounded_parameters(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = seoul_weather_risk.run([
                "query", "--product-id", PRODUCT_ID, "--filter", "place_id=place-a",
                "--from", "2026-08-01", "--to", "2026-08-05", "--limit", "100", "--cursor", "cursor-1",
            ])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["row_count"], 1)
        self.assertEqual([request["path"] for request in self.api.requests], [
            "/skill/v1/bundles/seoul-weather-risk",
            f"/skill/v1/products/{PRODUCT_ID}",
            f"/skill/v1/products/{PRODUCT_ID}/data",
        ])
        query = self.api.requests[-1]["query"]
        self.assertEqual(query, {"place_id": ["place-a"], "from": ["2026-08-01"], "to": ["2026-08-05"], "limit": ["100"], "cursor": ["cursor-1"]})
        self.assertTrue(all(request["authorization"] == "Bearer test-api-key" for request in self.api.requests))

    def test_bundle_single_product_drift_fails_closed(self):
        self.api.responses["/skill/v1/bundles/seoul-weather-risk"] = (200, "application/json", bundle([]), {})
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = seoul_weather_risk.run(["catalog"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], "response_contract_invalid")

    def test_malformed_success_response_fails_closed(self):
        self.api.responses["/skill/v1/bundles/seoul-weather-risk"] = (200, "application/json", b"not-json", {})
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = seoul_weather_risk.run(["catalog"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], "malformed_response")

    def test_http_problem_statuses_are_typed_and_preserve_safe_details(self):
        endpoint = "/skill/v1/bundles/seoul-weather-risk"
        cases = {
            401: "api_key_missing",
            403: "api_key_forbidden",
            404: "unknown_product",
            409: "cursor_expired",
            429: "rate_limited",
            503: "product_not_ready",
        }
        for status, expected_code in cases.items():
            with self.subTest(status=status):
                headers = {"Retry-After": "60"} if status == 429 else {}
                self.api.responses[endpoint] = (status, "application/problem+json", {
                    "title": "API failure", "detail": "safe problem detail", "code": expected_code,
                    "request_id": "req-1", "product_id": PRODUCT_ID,
                }, headers)
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    code = seoul_weather_risk.run(["catalog"])
                error = json.loads(stderr.getvalue())["error"]
                self.assertEqual(code, 2)
                self.assertEqual(error["code"], expected_code)
                self.assertEqual(error["details"]["status"], status)
                self.assertEqual(error["details"]["request_id"], "req-1")
                if status == 429:
                    self.assertEqual(error["details"]["retry_after"], "60")

    def test_missing_environment_never_echoes_credentials(self):
        os.environ.pop(seoul_weather_risk.API_KEY_ENV)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = seoul_weather_risk.run(["preflight"])
        self.assertEqual(code, 2)
        self.assertNotIn("test-api-key", stderr.getvalue())
        self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], "missing_api_key")

    def test_non_https_base_url_is_rejected_except_loopback_mock(self):
        with self.assertRaisesRegex(seoul_weather_risk.SkillError, "HTTPS"):
            seoul_weather_risk._api_config({
                seoul_weather_risk.API_KEY_ENV: "key",
                seoul_weather_risk.API_BASE_URL_ENV: "http://example.test",
            })
        config = seoul_weather_risk._api_config({
            seoul_weather_risk.API_KEY_ENV: "key",
            seoul_weather_risk.API_BASE_URL_ENV: self.api.base_url,
        })
        self.assertFalse(config.base_url.endswith("/"))
        with self.assertRaisesRegex(seoul_weather_risk.SkillError, "origin"):
            seoul_weather_risk._api_config({
                seoul_weather_risk.API_KEY_ENV: "key",
                seoul_weather_risk.API_BASE_URL_ENV: "https://api.example.test/untrusted-path",
            })

    def test_redirect_is_not_followed_with_bearer_credential(self):
        endpoint = "/skill/v1/bundles/seoul-weather-risk"
        self.api.responses[endpoint] = (302, "application/problem+json", {"detail": "redirect blocked"}, {
            "Location": f"{self.api.base_url}redirect-target",
        })
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = seoul_weather_risk.run(["catalog"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], "api_error")
        self.assertEqual([request["path"] for request in self.api.requests], [endpoint])


class CliTests(unittest.TestCase):
    def test_preflight_is_secret_free_and_offline(self):
        previous = {name: os.environ.get(name) for name in (seoul_weather_risk.API_KEY_ENV, seoul_weather_risk.API_BASE_URL_ENV)}
        self.addCleanup(lambda: [os.environ.pop(name, None) if value is None else os.environ.__setitem__(name, value) for name, value in previous.items()])
        os.environ[seoul_weather_risk.API_KEY_ENV] = "secret"
        os.environ[seoul_weather_risk.API_BASE_URL_ENV] = "https://api.example.test/"
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = seoul_weather_risk.run(["preflight"])
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["mode"], "live_https")
        self.assertFalse(payload["live_network"])
        self.assertNotIn("secret", stdout.getvalue())

    def test_parser_has_no_credential_or_base_url_option(self):
        parser = seoul_weather_risk._parser()
        option_strings = {option for action in parser._actions for option in action.option_strings}
        self.assertFalse(any("key" in option.lower() or "url" in option.lower() for option in option_strings))


if __name__ == "__main__":
    unittest.main()
