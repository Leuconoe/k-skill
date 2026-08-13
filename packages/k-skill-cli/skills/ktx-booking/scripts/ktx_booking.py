#!/usr/bin/env -S uv run --locked --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "korail2 @ git+https://github.com/dhfhfk/korail2@4b134266fff097ea0fd54e9f760cb128b6c8f878",
#   "pycryptodome==3.23.0",
# ]
# ///
"""Live, anonymous, read-only KTX timetable lookup through korail2."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date as calendar_date
from datetime import time
from typing import Any

from korail2 import Korail, KorailError, NoResultsError, TrainType
from korail2.korail2 import KORAIL_SEARCH_SCHEDULE

BOOKING_URL = "https://www.korail.com/ticket/train/schedule"
TIME_VALUE = re.compile(r"^\d{6}$")


def build_client() -> Korail:
    return Korail("", "", auto_login=False)


def source_info() -> dict[str, str]:
    return {
        "mode": "live",
        "transport": "korail2",
        "operator": "한국철도공사",
        "endpoint": KORAIL_SEARCH_SCHEDULE,
        "authentication": "anonymous",
        "mutation": "none; ScheduleView search only",
        "booking_url": BOOKING_URL,
    }


def format_time(value: str) -> str:
    return f"{value[:2]}:{value[2:4]}"


def normalize_station(value: str) -> str:
    """Accept common "...역" input for a canonical Korail station name."""
    name = value.strip()
    if len(name) > 2 and name.endswith("역"):
        return name[:-1]
    return name


def normalize_train(train: Any) -> dict[str, Any]:
    return {
        "train_no": str(train.train_no),
        "train_type": str(train.train_type_name),
        "dep": str(train.dep_name),
        "arr": str(train.arr_name),
        "dep_date": str(train.dep_date),
        "dep_time": format_time(str(train.dep_time)),
        "arr_time": format_time(str(train.arr_time)),
        "general_seat_available": bool(train.has_general_seat()),
        "special_seat_available": bool(train.has_special_seat()),
    }


def search_live_timetable(
    *,
    dep: str,
    arr: str,
    date: str,
    earliest: str,
    latest: str,
    limit: int,
) -> dict[str, Any]:
    validate_date(date)
    start = validate_time(earliest)
    end = validate_time(latest)
    if start > end:
        raise ValueError("--time must not be later than --time-limit")
    dep = normalize_station(dep)
    arr = normalize_station(arr)
    client = build_client()
    try:
        trains = client.search_train(
            dep=dep,
            arr=arr,
            date=date,
            time=start,
            train_type=TrainType.KTX,
            include_no_seats=True,
            include_waiting_list=False,
        )
    except NoResultsError:
        trains = []
    in_window = [train for train in trains if start <= str(train.dep_time) <= end]
    matched = [
        train
        for train in in_window
        if str(train.dep_name) == dep and str(train.arr_name) == arr
    ]
    if in_window and not matched:
        returned = sorted({f"{train.dep_name}→{train.arr_name}" for train in in_window})
        raise ValueError(
            f"요청한 역({dep}→{arr})과 정확히 일치하는 열차가 없습니다. "
            f"코레일이 반환한 역: {', '.join(returned)}"
        )
    results = [normalize_train(train) for train in matched][:limit]
    return {
        "count": len(results),
        "trains": results,
        "date": date,
        "source": source_info(),
        "schedule_note": "실시간 시간표·좌석 가능 여부 조회이며 예약·좌석 선점은 실행하지 않습니다.",
        "booking_url": BOOKING_URL,
    }


def validate_date(value: str) -> str:
    if not re.fullmatch(r"\d{8}", value):
        raise ValueError("date must use YYYYMMDD")
    try:
        calendar_date(int(value[:4]), int(value[4:6]), int(value[6:]))
    except ValueError as exc:
        raise ValueError("date must use a valid YYYYMMDD value") from exc
    return value


def validate_time(value: str) -> str:
    if not re.fullmatch(r"\d{4}", value):
        raise ValueError("time must use HHMM")
    try:
        time.fromisoformat(f"{value[:2]}:{value[2:]}")
    except ValueError as exc:
        raise ValueError("time must use a valid HHMM value") from exc
    return value + "00"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KTX live timetable lookup through korail2 (read-only)")
    commands = parser.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search", help="query the current KTX timetable")
    search.add_argument("--dep", required=True)
    search.add_argument("--arr", required=True)
    search.add_argument("--date", required=True, help="YYYYMMDD")
    search.add_argument("--time", default="0000", help="earliest departure, HHMM")
    search.add_argument("--time-limit", default="2359", help="latest departure, HHMM")
    search.add_argument("--limit", type=int, default=10)
    commands.add_parser("source", help="show the read-only live query endpoint")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "source":
            print(json.dumps(source_info(), ensure_ascii=False, indent=2))
            return 0
        if args.limit < 1 or args.limit > 50:
            raise ValueError("--limit must be between 1 and 50")
        result = search_live_timetable(
            dep=args.dep,
            arr=args.arr,
            date=args.date,
            earliest=args.time,
            latest=args.time_limit,
            limit=args.limit,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (KorailError, NoResultsError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
