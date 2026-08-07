#!/usr/bin/env python3
"""Read-only HTTPS client for the ASK Seoul seoul-weather-risk skill API."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


SKILL_BUNDLE_ID = "seoul-weather-risk"
API_KEY_ENV = "KSKILL_SEOUL_WEATHER_RISK_API_KEY"
API_BASE_URL_ENV = "KSKILL_SEOUL_WEATHER_RISK_API_BASE_URL"
EXACT_PRODUCT_IDS = frozenset({
    "weather_place_risk_window",
})
STATUS_CODES = {
    401: "unauthorized",
    403: "forbidden",
    404: "unknown_product",
    409: "cursor_expired",
    429: "rate_limited",
    503: "product_not_ready",
}


class SkillError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class _NoRedirect(HTTPRedirectHandler):
    """Keep the bearer credential on the configured API origin."""

    def redirect_request(self, _req: Request, _fp: Any, _code: int, _msg: str, _headers: Any, _newurl: str) -> None:
        return None


@dataclass(frozen=True)
class ApiConfig:
    base_url: str
    api_key: str


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _api_config(environ: dict[str, str] | None = None) -> ApiConfig:
    values = os.environ if environ is None else environ
    api_key = values.get(API_KEY_ENV, "").strip()
    base_url = values.get(API_BASE_URL_ENV, "").strip().rstrip("/")
    if not api_key:
        raise SkillError("missing_api_key", f"{API_KEY_ENV} 환경변수가 필요합니다.")
    if not base_url:
        raise SkillError("missing_api_base_url", f"{API_BASE_URL_ENV} 환경변수가 필요합니다.")

    parsed = urlparse(base_url)
    local_http = parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if (parsed.scheme != "https" and not local_http) or not parsed.netloc or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise SkillError("invalid_api_base_url", "API base URL은 HTTPS origin이어야 합니다.")
    if parsed.username or parsed.password:
        raise SkillError("invalid_api_base_url", "API base URL에 사용자 정보는 포함할 수 없습니다.")
    return ApiConfig(base_url=base_url, api_key=api_key)


def _error_payload(raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _problem_error(status: int, raw: bytes, headers: Any) -> SkillError:
    problem = _error_payload(raw)
    code = problem.get("code") if isinstance(problem.get("code"), str) else STATUS_CODES.get(status, "api_error")
    message = problem.get("detail") if isinstance(problem.get("detail"), str) else problem.get("title")
    if not isinstance(message, str) or not message:
        message = f"ASK Seoul API가 HTTP {status} 응답을 반환했습니다."
    details = {"status": status}
    for name in ("type", "title", "product_id", "blockers", "request_id"):
        if name in problem:
            details[name] = problem[name]
    retry_after = headers.get("Retry-After") if headers else None
    if retry_after:
        details["retry_after"] = retry_after
    return SkillError(code, message, details)


def _request_json(config: ApiConfig, path: str, query: dict[str, str] | None = None) -> dict[str, Any]:
    url = f"{config.base_url}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    request = Request(url, headers={
        "Accept": "application/json",
        "Authorization": f"Bearer {config.api_key}",
        "User-Agent": "k-skill-seoul-weather-risk/1",
    })
    try:
        with build_opener(_NoRedirect).open(request, timeout=15) as response:
            raw = response.read()
            content_type = response.headers.get_content_type()
    except HTTPError as exc:
        raise _problem_error(exc.code, exc.read(), exc.headers) from exc
    except URLError as exc:
        raise SkillError("network_error", "ASK Seoul API에 연결할 수 없습니다.") from exc

    if content_type != "application/json":
        raise SkillError("malformed_response", "ASK Seoul API 성공 응답의 Content-Type이 JSON이 아닙니다.")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SkillError("malformed_response", "ASK Seoul API 성공 응답이 JSON 객체가 아닙니다.") from exc
    if not isinstance(payload, dict):
        raise SkillError("malformed_response", "ASK Seoul API 성공 응답이 JSON 객체가 아닙니다.")
    return payload


def _contract_error(message: str) -> SkillError:
    return SkillError("response_contract_invalid", message)


def _require(value: dict[str, Any], name: str, expected: type | tuple[type, ...]) -> Any:
    item = value.get(name)
    if not isinstance(item, expected):
        raise _contract_error(f"ASK Seoul API 응답의 {name} 계약이 올바르지 않습니다.")
    return item


def _validate_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("bundle_id") != SKILL_BUNDLE_ID:
        raise _contract_error("ASK Seoul API 응답의 bundle_id가 일치하지 않습니다.")
    _require(payload, "registration_ready", bool)
    products = _require(payload, "products", list)
    ids: list[str] = []
    for product in products:
        if not isinstance(product, dict):
            raise _contract_error("ASK Seoul API bundle의 product 항목이 객체가 아닙니다.")
        product_id = _require(product, "product_id", str)
        _require(product, "registration_ready", bool)
        blockers = _require(product, "blockers", list)
        if not all(isinstance(blocker, str) for blocker in blockers):
            raise _contract_error("ASK Seoul API bundle의 blockers 계약이 올바르지 않습니다.")
        publication_id = product.get("publication_id")
        if publication_id is not None and not isinstance(publication_id, str):
            raise _contract_error("ASK Seoul API bundle의 publication_id 계약이 올바르지 않습니다.")
        ids.append(product_id)
    if set(ids) != EXACT_PRODUCT_IDS or len(ids) != len(EXACT_PRODUCT_IDS):
        raise _contract_error("ASK Seoul API bundle의 제품 목록이 이 스킬의 단일 제품과 다릅니다.")
    return payload


def _validate_product(payload: dict[str, Any], product_id: str) -> dict[str, Any]:
    if payload.get("bundle_id") != SKILL_BUNDLE_ID or payload.get("product_id") != product_id:
        raise _contract_error("ASK Seoul API product 응답의 bundle_id 또는 product_id가 일치하지 않습니다.")
    _require(payload, "registration_ready", bool)
    blockers = _require(payload, "blockers", list)
    if not all(isinstance(blocker, str) for blocker in blockers):
        raise _contract_error("ASK Seoul API product 응답의 blockers 계약이 올바르지 않습니다.")
    publication_id = payload.get("publication_id")
    if publication_id is not None and not isinstance(publication_id, str):
        raise _contract_error("ASK Seoul API product 응답의 publication_id 계약이 올바르지 않습니다.")
    metadata = _require(payload, "metadata", dict)
    columns = metadata.get("columns", [])
    if not isinstance(columns, list) or any(not isinstance(column, dict) or not isinstance(column.get("name"), str) for column in columns):
        raise _contract_error("ASK Seoul API product metadata.columns 계약이 올바르지 않습니다.")
    return payload


def _validate_data(payload: dict[str, Any], product_id: str, requested_limit: int) -> dict[str, Any]:
    if payload.get("bundle_id") != SKILL_BUNDLE_ID or payload.get("product_id") != product_id:
        raise _contract_error("ASK Seoul API data 응답의 bundle_id 또는 product_id가 일치하지 않습니다.")
    publication_id = _require(payload, "publication_id", str)
    if not publication_id:
        raise _contract_error("ASK Seoul API data 응답의 publication_id가 비어 있습니다.")
    row_count = _require(payload, "row_count", int)
    limit = _require(payload, "limit", int)
    has_more = _require(payload, "has_more", bool)
    rows = _require(payload, "rows", list)
    next_cursor = payload.get("next_cursor")
    if row_count < 0 or row_count != len(rows) or limit != requested_limit or not 1 <= limit <= 500:
        raise _contract_error("ASK Seoul API data page의 row_count 또는 limit 계약이 올바르지 않습니다.")
    if next_cursor is not None and not isinstance(next_cursor, str):
        raise _contract_error("ASK Seoul API data page의 next_cursor 계약이 올바르지 않습니다.")
    if has_more != (next_cursor is not None):
        raise _contract_error("ASK Seoul API data page의 has_more와 next_cursor가 일치하지 않습니다.")
    if not all(isinstance(row, dict) for row in rows):
        raise _contract_error("ASK Seoul API data page의 rows 계약이 올바르지 않습니다.")
    return payload


def _filters(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise SkillError("invalid_filter", "필터는 column=value 형식이어야 합니다.")
        name, expected = value.split("=", 1)
        name = name.strip()
        if not name or name in parsed:
            raise SkillError("invalid_filter", "필터 이름은 비어 있거나 중복될 수 없습니다.")
        parsed[name] = expected
    return parsed


def _validate_product_id(product_id: str) -> None:
    if product_id not in EXACT_PRODUCT_IDS:
        raise SkillError("unknown_product", f"지원하지 않는 product_id입니다: {product_id}")


def _bundle(config: ApiConfig) -> dict[str, Any]:
    return _validate_bundle(_request_json(config, f"/skill/v1/bundles/{SKILL_BUNDLE_ID}"))


def _detail(config: ApiConfig, product_id: str) -> dict[str, Any]:
    _validate_product_id(product_id)
    return _validate_product(_request_json(config, f"/skill/v1/products/{product_id}"), product_id)


def _data(config: ApiConfig, product_id: str, query: dict[str, str], limit: int) -> dict[str, Any]:
    _validate_product_id(product_id)
    return _validate_data(_request_json(config, f"/skill/v1/products/{product_id}/data", query), product_id, limit)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="seoul-weather-risk ASK Seoul HTTPS client")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preflight", help="live API 환경 설정 확인(네트워크 호출 없음)")
    commands.add_parser("catalog", help="weather_place_risk_window bundle 조회")

    describe = commands.add_parser("describe", help="제품 metadata 조회")
    describe.add_argument("--product-id", required=True)

    query = commands.add_parser("query", help="제품 data page 조회")
    query.add_argument("--product-id", required=True)
    query.add_argument("--filter", action="append", default=[], metavar="COLUMN=VALUE")
    query.add_argument("--from", dest="from_value")
    query.add_argument("--to", dest="to_value")
    query.add_argument("--limit", type=int, default=100)
    query.add_argument("--cursor")
    return parser


def run(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    try:
        config = _api_config()
        if args.command == "preflight":
            result = {
                "status": "ok",
                "mode": "live_https",
                "live_network": False,
                "credential_configured": True,
                "base_url_configured": True,
            }
        elif args.command == "catalog":
            result = _bundle(config)
        elif args.command == "describe":
            _bundle(config)
            result = _detail(config, args.product_id)
        else:
            if not 1 <= args.limit <= 500:
                raise SkillError("invalid_limit", "limit은 1부터 500 사이여야 합니다.")
            _bundle(config)
            detail = _detail(config, args.product_id)
            filters = _filters(args.filter)
            allowed_columns = {column["name"] for column in detail["metadata"].get("columns", [])}
            unknown = sorted(set(filters) - allowed_columns)
            if unknown:
                raise SkillError("unknown_filter", f"공개 projection에 없는 필터입니다: {', '.join(unknown)}")
            request_query = {**filters, "limit": str(args.limit)}
            if args.from_value is not None:
                request_query["from"] = args.from_value
            if args.to_value is not None:
                request_query["to"] = args.to_value
            if args.cursor is not None:
                request_query["cursor"] = args.cursor
            result = _data(config, args.product_id, request_query, args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except SkillError as exc:
        error = {"code": exc.code, "message": exc.message}
        if exc.details:
            error["details"] = exc.details
        print(json.dumps({"error": error}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
