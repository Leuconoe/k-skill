import contextlib
import importlib.util
import io
import json
import os
import pathlib
import sys
import tempfile
import threading
import unittest
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
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
        self.proxy_base_url_env = "KSKILL_PROXY_BASE_URL"
        self.previous = {name: os.environ.get(name) for name in (self.proxy_base_url_env, "KSKILL_SEOUL_WEATHER_RISK_API_KEY")}
        os.environ[self.proxy_base_url_env] = self.api.base_url
        os.environ["KSKILL_SEOUL_WEATHER_RISK_API_KEY"] = "legacy-user-key-must-not-be-used"
        self.api.responses = {
            "/v1/ask-seoul/weather-risk/bundle": (200, "application/json", bundle(), {}),
            "/v1/ask-seoul/weather-risk/product": (200, "application/json", detail(), {}),
            "/v1/ask-seoul/weather-risk/data": (200, "application/json", data(), {}),
        }

    def tearDown(self):
        self.api.close()
        for name, value in self.previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_query_uses_narrow_proxy_paths_without_user_bearer_auth(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = seoul_weather_risk.run([
                "query", "--product-id", PRODUCT_ID, "--filter", "place_id=place-a",
                "--from", "2026-08-01", "--to", "2026-08-05", "--limit", "100", "--cursor", "cursor-1",
            ])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["row_count"], 1)
        self.assertEqual([request["path"] for request in self.api.requests], [
            "/v1/ask-seoul/weather-risk/bundle",
            "/v1/ask-seoul/weather-risk/product",
            "/v1/ask-seoul/weather-risk/data",
        ])
        query = self.api.requests[-1]["query"]
        self.assertEqual(query, {
            "place_id": ["place-a"],
            "from": ["2026-08-01 00:00:00"],
            "to": ["2026-08-05 23:59:59"],
            "limit": ["100"],
            "cursor": ["cursor-1"],
        })
        self.assertTrue(all(request["authorization"] is None for request in self.api.requests))

    def test_query_keeps_explicit_datetime_bounds_unchanged(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = seoul_weather_risk.run([
                "query", "--product-id", PRODUCT_ID, "--filter", "place_id=place-a",
                "--from", "2026-08-01 09:00:00", "--to", "2026-08-01 18:00:00", "--limit", "100",
            ])

        self.assertEqual(code, 0)
        self.assertEqual(self.api.requests[-1]["query"], {
            "place_id": ["place-a"],
            "from": ["2026-08-01 09:00:00"],
            "to": ["2026-08-01 18:00:00"],
            "limit": ["100"],
        })

    def test_local_direct_mode_uses_marketplace_bearer_and_skill_paths(self):
        self.api.responses = {
            "/skill/v1/bundles/seoul-weather-risk": (200, "application/json", bundle(), {}),
            f"/skill/v1/products/{PRODUCT_ID}": (200, "application/json", detail(), {}),
            f"/skill/v1/products/{PRODUCT_ID}/data": (200, "application/json", data(limit=1), {}),
        }
        names = ("KSKILL_LOCAL_DIRECT", "ASK_SEOUL_SKILL_API_BASE_URL", "MARKETPLACE_API_KEY")
        previous = {name: os.environ.get(name) for name in names}
        self.addCleanup(lambda: [os.environ.pop(name, None) if value is None else os.environ.__setitem__(name, value) for name, value in previous.items()])
        os.environ["KSKILL_LOCAL_DIRECT"] = "1"
        os.environ["ASK_SEOUL_SKILL_API_BASE_URL"] = self.api.base_url
        os.environ["MARKETPLACE_API_KEY"] = "test-marketplace-key"

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = seoul_weather_risk.run([
                "query", "--product-id", PRODUCT_ID, "--admin-dong", "성수2가3동", "--limit", "1",
            ])

        self.assertEqual(code, 0)
        self.assertEqual([request["path"] for request in self.api.requests], [
            "/skill/v1/bundles/seoul-weather-risk",
            f"/skill/v1/products/{PRODUCT_ID}",
            f"/skill/v1/products/{PRODUCT_ID}/data",
        ])
        self.assertTrue(all(request["authorization"] == "Bearer test-marketplace-key" for request in self.api.requests))
        self.assertEqual(self.api.requests[-1]["query"]["place_id"], ["seoul_admd_1120069000"])

    def test_local_direct_mode_loads_current_directory_dotenv(self):
        self.api.responses = {
            "/skill/v1/bundles/seoul-weather-risk": (200, "application/json", bundle(), {}),
        }
        names = ("KSKILL_LOCAL_DIRECT", "ASK_SEOUL_SKILL_API_BASE_URL", "MARKETPLACE_API_KEY")
        previous = {name: os.environ.get(name) for name in names}
        self.addCleanup(lambda: [os.environ.pop(name, None) if value is None else os.environ.__setitem__(name, value) for name, value in previous.items()])
        for name in names:
            os.environ.pop(name, None)

        with tempfile.TemporaryDirectory() as directory:
            pathlib.Path(directory, ".env").write_text(
                "KSKILL_LOCAL_DIRECT=1\n"
                f"ASK_SEOUL_SKILL_API_BASE_URL={self.api.base_url}\n"
                "MARKETPLACE_API_KEY=test-marketplace-key\n",
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with patch.object(seoul_weather_risk.pathlib.Path, "cwd", return_value=pathlib.Path(directory)):
                with contextlib.redirect_stdout(stdout):
                    code = seoul_weather_risk.run(["catalog"])

        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["bundle_id"], "seoul-weather-risk")
        self.assertEqual(self.api.requests[0]["path"], "/skill/v1/bundles/seoul-weather-risk")
        self.assertEqual(self.api.requests[0]["authorization"], "Bearer test-marketplace-key")

    def test_local_direct_preflight_reports_direct_not_proxy_configuration(self):
        stdout = io.StringIO()
        with patch.dict(os.environ, {
            "KSKILL_LOCAL_DIRECT": "1",
            "ASK_SEOUL_SKILL_API_BASE_URL": self.api.base_url,
            "MARKETPLACE_API_KEY": "test-marketplace-key",
        }, clear=False):
            with contextlib.redirect_stdout(stdout):
                code = seoul_weather_risk.run(["preflight"])

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["mode"], "local_direct")
        self.assertTrue(payload["user_api_key_required"])
        self.assertFalse(payload["proxy_base_url_configured"])
        self.assertTrue(payload["local_direct_base_url_configured"])

    def test_query_maps_admin_dong_to_place_id_before_proxy_request(self):
        self.api.responses["/v1/ask-seoul/weather-risk/data"] = (
            200, "application/json", data(limit=1), {},
        )
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = seoul_weather_risk.run([
                "query", "--product-id", PRODUCT_ID,
                "--admin-dong", "잠실본동", "--limit", "1",
            ])

        self.assertEqual(code, 0)
        query = self.api.requests[-1]["query"]
        self.assertEqual(query, {
            "place_id": ["seoul_admd_1171065000"],
            "limit": ["1"],
        })
        self.assertNotIn("admin_dong", query)
        self.assertNotIn("gu", query)

    def test_query_rejects_gu_without_admin_dong(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = seoul_weather_risk.run([
                "query", "--product-id", PRODUCT_ID, "--gu", "송파구",
            ])

        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], "invalid_location_input")
        self.assertEqual(len(self.api.requests), 2)

    def test_query_rejects_admin_dong_with_place_id_filter(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = seoul_weather_risk.run([
                "query", "--product-id", PRODUCT_ID,
                "--admin-dong", "잠실본동", "--filter", "place_id=place-a",
            ])

        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], "conflicting_location_input")
        self.assertEqual(len(self.api.requests), 2)

    def test_bundle_single_product_drift_fails_closed(self):
        self.api.responses["/v1/ask-seoul/weather-risk/bundle"] = (200, "application/json", bundle([]), {})
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = seoul_weather_risk.run(["catalog"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], "response_contract_invalid")

    def test_malformed_success_response_fails_closed(self):
        self.api.responses["/v1/ask-seoul/weather-risk/bundle"] = (200, "application/json", b"not-json", {})
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = seoul_weather_risk.run(["catalog"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], "malformed_response")

    def test_http_problem_statuses_are_typed_and_preserve_safe_details(self):
        endpoint = "/v1/ask-seoul/weather-risk/bundle"
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

    def test_disabled_proxy_never_echoes_legacy_user_credentials(self):
        os.environ[self.proxy_base_url_env] = "off"
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = seoul_weather_risk.run(["preflight"])
        self.assertEqual(code, 2)
        self.assertNotIn("legacy-user-key-must-not-be-used", stderr.getvalue())
        self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], "proxy_disabled")

    def test_non_https_base_url_is_rejected_except_loopback_mock(self):
        with self.assertRaisesRegex(seoul_weather_risk.SkillError, "HTTPS"):
            seoul_weather_risk._api_config({
                self.proxy_base_url_env: "http://example.test",
            })
        config = seoul_weather_risk._api_config({
            self.proxy_base_url_env: self.api.base_url,
        })
        self.assertFalse(config.base_url.endswith("/"))
        with self.assertRaisesRegex(seoul_weather_risk.SkillError, "origin"):
            seoul_weather_risk._api_config({
                self.proxy_base_url_env: "https://api.example.test/untrusted-path",
            })

    def test_redirect_is_not_followed_through_proxy_client(self):
        endpoint = "/v1/ask-seoul/weather-risk/bundle"
        self.api.responses[endpoint] = (302, "application/problem+json", {"detail": "redirect blocked"}, {
            "Location": f"{self.api.base_url}redirect-target",
        })
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = seoul_weather_risk.run(["catalog"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], "api_error")
        self.assertEqual([request["path"] for request in self.api.requests], [endpoint])


class LocationMappingTests(unittest.TestCase):
    def test_admin_dong_reference_has_expected_version_and_unique_place_ids(self):
        mapping_path = ROOT / "seoul-weather-risk" / "references" / "admin-dong-place-map.json"
        payload = json.loads(mapping_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["mapping_version"], "kma_admin_dong_grid_20260325")
        self.assertEqual(len(payload["locations"]), 427)
        self.assertEqual(len({row["place_id"] for row in payload["locations"]}), 427)
        self.assertEqual(
            sorted(row["gu"] for row in payload["locations"] if row["admin_dong"] == "신사동"),
            ["강남구", "관악구"],
        )

    def test_resolve_admin_dong_returns_canonical_place_id(self):
        resolved = seoul_weather_risk._resolve_admin_dong("  잠실본동  ")

        self.assertEqual(resolved, {
            "admin_dong": "잠실본동",
            "gu": "송파구",
            "place_id": "seoul_admd_1171065000",
        })

    def test_resolve_admin_dong_normalizes_unicode_nfc(self):
        resolved = seoul_weather_risk._resolve_admin_dong(unicodedata.normalize("NFD", "잠실본동"))

        self.assertEqual(resolved["place_id"], "seoul_admd_1171065000")

    def test_resolve_admin_dong_recognizes_explicit_spelling_alias(self):
        resolved = seoul_weather_risk._resolve_admin_dong("성수2가3동")

        self.assertEqual(resolved, {
            "admin_dong": "성수2가제3동",
            "gu": "성동구",
            "place_id": "seoul_admd_1120069000",
        })

    def test_resolve_admin_dong_accepts_je_omission_aliases(self):
        self.assertEqual(
            seoul_weather_risk._resolve_admin_dong("창신1동")["place_id"],
            "seoul_admd_1111067000",
        )
        self.assertEqual(
            seoul_weather_risk._resolve_admin_dong("자양1동")["place_id"],
            "seoul_admd_1121582000",
        )

    def test_resolve_admin_dong_accepts_numeric_punctuation_aliases(self):
        expected = "seoul_admd_1111061500"

        self.assertEqual(
            seoul_weather_risk._resolve_admin_dong("종로1·2·3·4가동")["place_id"],
            expected,
        )
        self.assertEqual(
            seoul_weather_risk._resolve_admin_dong("종로1234가동")["place_id"],
            expected,
        )

    def test_resolve_admin_dong_requires_gu_for_duplicate_name(self):
        with self.assertRaises(seoul_weather_risk.SkillError) as raised:
            seoul_weather_risk._resolve_admin_dong("신사동")

        self.assertEqual(raised.exception.code, "ambiguous_admin_dong")
        self.assertEqual(raised.exception.details["candidates"], [
            {"admin_dong": "신사동", "gu": "강남구", "place_id": "seoul_admd_1168051000"},
            {"admin_dong": "신사동", "gu": "관악구", "place_id": "seoul_admd_1162068500"},
        ])

    def test_resolve_admin_dong_uses_gu_to_disambiguate(self):
        resolved = seoul_weather_risk._resolve_admin_dong("신사동", "강남구")

        self.assertEqual(resolved["place_id"], "seoul_admd_1168051000")

    def test_resolve_admin_dong_rejects_unknown_dong_and_gu(self):
        with self.assertRaises(seoul_weather_risk.SkillError) as unknown_dong:
            seoul_weather_risk._resolve_admin_dong("없는동")
        self.assertEqual(unknown_dong.exception.code, "unknown_admin_dong")

        with self.assertRaises(seoul_weather_risk.SkillError) as unknown_gu:
            seoul_weather_risk._resolve_admin_dong("잠실본동", "없는구")
        self.assertEqual(unknown_gu.exception.code, "unknown_gu")

    def test_load_location_mapping_rejects_invalid_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            invalid_path = pathlib.Path(directory) / "mapping.json"
            invalid_path.write_text(json.dumps({
                "mapping_version": "wrong-version",
                "locations": [],
            }), encoding="utf-8")

            with self.assertRaises(seoul_weather_risk.SkillError) as raised:
                seoul_weather_risk._load_location_mapping(invalid_path)

        self.assertEqual(raised.exception.code, "location_mapping_invalid")


class CliTests(unittest.TestCase):
    def test_preflight_is_user_secret_free_and_offline(self):
        proxy_base_url_env = "KSKILL_PROXY_BASE_URL"
        previous = {name: os.environ.get(name) for name in (proxy_base_url_env, "KSKILL_SEOUL_WEATHER_RISK_API_KEY")}
        self.addCleanup(lambda: [os.environ.pop(name, None) if value is None else os.environ.__setitem__(name, value) for name, value in previous.items()])
        os.environ[proxy_base_url_env] = "https://proxy.example.test/"
        os.environ["KSKILL_SEOUL_WEATHER_RISK_API_KEY"] = "legacy-user-key-must-not-be-used"
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = seoul_weather_risk.run(["preflight"])
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["mode"], "hosted_proxy")
        self.assertFalse(payload["live_network"])
        self.assertFalse(payload["user_api_key_required"])
        self.assertNotIn("legacy-user-key-must-not-be-used", stdout.getvalue())

    def test_parser_has_no_credential_or_base_url_option(self):
        parser = seoul_weather_risk._parser()
        option_strings = {option for action in parser._actions for option in action.option_strings}
        self.assertFalse(any("key" in option.lower() or "url" in option.lower() for option in option_strings))


if __name__ == "__main__":
    unittest.main()
