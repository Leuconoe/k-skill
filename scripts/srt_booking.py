#!/usr/bin/env python3
"""Read the official published SRT operating timetable without account access.

Usage:
  python3 scripts/srt_booking.py search --dep 수서 --arr 부산 --date 20260820 --time 0600
  python3 scripts/srt_booking.py source

The helper invokes `npx -y kordoc` only to convert the official HWP attachment
inside a temporary directory. It never logs in, checks seat inventory, reserves,
pays, cancels, polls, or stores the downloaded document.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener


ARCHIVE_URL = "https://etk.srail.kr/cms/archive.do?pageId=TK0402050000"
DOWNLOAD_URL = "https://www.srail.or.kr/cms/attach/download.do"
BOOKING_URL = "https://etk.srail.kr/hpg/hra/01/selectScheduleList.do?pageId=TK0101010000"
USER_AGENT = "k-skill/srt-readonly (+https://github.com/NomaDamas/k-skill)"
ATTACHMENT = re.compile(
    r"downloadAttach\('TK0402050000',\s*'(?P<number>\d+)'\).*?</a>",
    re.DOTALL,
)
EFFECTIVE_DATE = re.compile(r"(20\d{2})[.\s년]+(\d{1,2})[.\s월]+(\d{1,2})")
TIME_VALUE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


@dataclass(frozen=True)
class TimetableSource:
    title: str
    attachment_no: str
    effective_date: str
    source_url: str = ARCHIVE_URL

    @property
    def download_url(self) -> str:
        return f"{DOWNLOAD_URL}?pageId=TK0402050000&atchNo={self.attachment_no}"


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._row is not None and self._cell is not None:
            self._row.append(re.sub(r"\s+", "", unescape("".join(self._cell))))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None


def fetch_archive(timeout: float = 20.0) -> tuple[str, Any]:
    opener = build_opener(HTTPCookieProcessor())
    request = Request(ARCHIVE_URL, headers={"User-Agent": USER_AGENT})
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.read().decode("utf-8", "replace"), opener
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"SRT official timetable archive unavailable: {exc}") from exc


def choose_latest_timetable(html: str) -> TimetableSource:
    sources: list[TimetableSource] = []
    for match in ATTACHMENT.finditer(html):
        date_match = EFFECTIVE_DATE.search(match.group(0))
        if date_match is None:
            continue
        year, month, day = date_match.groups()
        title = f"SRT 운행시각표({year}. {int(month):02d}. {int(day):02d}. 기준)"
        sources.append(
            TimetableSource(
                title=title,
                attachment_no=match.group("number"),
                effective_date=f"{year}{int(month):02d}{int(day):02d}",
            )
        )
    if not sources:
        raise RuntimeError("SRT published no readable operating timetable attachment")
    return max(sources, key=lambda source: (source.effective_date, int(source.attachment_no)))


def choose_timetable_for_date(html: str, date: str) -> TimetableSource:
    matches: list[TimetableSource] = []
    for match in ATTACHMENT.finditer(html):
        date_match = EFFECTIVE_DATE.search(match.group(0))
        if date_match is None:
            continue
        year, month, day = date_match.groups()
        title = f"SRT 운행시각표({year}. {int(month):02d}. {int(day):02d}. 기준)"
        source = TimetableSource(
            title=title,
            attachment_no=match.group("number"),
            effective_date=f"{year}{int(month):02d}{int(day):02d}",
        )
        if source.effective_date <= date:
            matches.append(source)
    if not matches:
        raise RuntimeError(f"SRT published no operating timetable applicable to {date}")
    return max(matches, key=lambda source: (source.effective_date, int(source.attachment_no)))


def download_attachment(opener: Any, source: TimetableSource, timeout: float = 30.0) -> bytes:
    request = Request(
        source.download_url,
        headers={"User-Agent": USER_AGENT, "Referer": ARCHIVE_URL},
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"SRT official timetable attachment unavailable: {exc}") from exc


def convert_hwp_to_markdown(content: bytes) -> str:
    with tempfile.TemporaryDirectory(prefix="k-skill-srt-readonly-") as directory:
        source = Path(directory) / "timetable.hwp"
        output = Path(directory) / "timetable.md"
        source.write_bytes(content)
        result = subprocess.run(
            ["npx", "-y", "kordoc", str(source), "-o", str(output)],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0 or not output.exists():
            message = result.stderr.strip() or result.stdout.strip() or "unknown conversion error"
            raise RuntimeError(f"SRT official HWP timetable could not be parsed: {message}")
        return output.read_text(encoding="utf-8")


def parse_timetable_markdown(
    markdown: str,
    *,
    dep: str,
    arr: str,
    earliest: str,
    latest: str,
) -> list[dict[str, str]]:
    parser = TableParser()
    parser.feed(markdown)
    dep_name = dep.replace("역", "")
    arr_name = arr.replace("역", "")
    results: list[dict[str, str]] = []

    for header_index, header in enumerate(parser.rows):
        normalized = [value.replace("역", "") for value in header]
        if dep_name not in normalized or arr_name not in normalized:
            continue
        if not any("열차번호" in value for value in normalized):
            continue
        train_index = next(index for index, value in enumerate(normalized) if "열차번호" in value)
        dep_index = normalized.index(dep_name)
        arr_index = normalized.index(arr_name)
        for row in parser.rows[header_index + 1 :]:
            if max(train_index, dep_index, arr_index) >= len(row):
                break
            train_no = row[train_index]
            if not re.fullmatch(r"\d{3,4}", train_no):
                break
            dep_time = row[dep_index]
            arr_time = row[arr_index]
            if not TIME_VALUE.fullmatch(dep_time) or not TIME_VALUE.fullmatch(arr_time):
                continue
            if earliest <= dep_time <= latest:
                results.append(
                    {
                        "train_no": train_no,
                        "dep": dep,
                        "arr": arr,
                        "dep_time": dep_time,
                        "arr_time": arr_time,
                    }
                )
    return results


def validate_date(value: str) -> str:
    if not re.fullmatch(r"\d{8}", value):
        raise ValueError("date must use YYYYMMDD")
    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError as exc:
        raise ValueError("date must use a valid YYYYMMDD value") from exc
    return value


def validate_time(value: str) -> str:
    if not re.fullmatch(r"\d{4}", value):
        raise ValueError("time must use HHMM")
    try:
        datetime.strptime(value, "%H%M")
    except ValueError as exc:
        raise ValueError("time must use a valid HHMM value") from exc
    return f"{value[:2]}:{value[2:]}"


def search_public_timetable(
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
    html, opener = fetch_archive()
    source = choose_timetable_for_date(html, date)
    markdown = convert_hwp_to_markdown(download_attachment(opener, source))
    trains = parse_timetable_markdown(markdown, dep=dep, arr=arr, earliest=start, latest=end)
    unique = {(train["train_no"], train["dep_time"], train["arr_time"]): train for train in trains}
    ordered = sorted(unique.values(), key=lambda train: (train["dep_time"], train["train_no"]))[:limit]
    return {
        "count": len(ordered),
        "trains": ordered,
        "date": date,
        "schedule_note": "공개 운행계획 기준이며 실시간 잔여석·운휴·지연 정보가 아닙니다.",
        "source": {"operator": "주식회사 에스알", **asdict(source), "download_url": source.download_url},
        "booking_url": BOOKING_URL,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SRT official timetable lookup (read-only)")
    commands = parser.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search", help="search a published SRT operating timetable")
    search.add_argument("--dep", required=True)
    search.add_argument("--arr", required=True)
    search.add_argument("--date", required=True, help="YYYYMMDD")
    search.add_argument("--time", default="0000", help="earliest departure, HHMM")
    search.add_argument("--time-limit", default="2359", help="latest departure, HHMM")
    search.add_argument("--limit", type=int, default=10)
    commands.add_parser("source", help="show the current official timetable source")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        html, _opener = fetch_archive()
        if args.command == "source":
            source = choose_latest_timetable(html)
            print(json.dumps({**asdict(source), "download_url": source.download_url}, ensure_ascii=False, indent=2))
            return 0
        if args.limit < 1 or args.limit > 50:
            raise ValueError("--limit must be between 1 and 50")
        result = search_public_timetable(
            dep=args.dep,
            arr=args.arr,
            date=args.date,
            earliest=args.time,
            latest=args.time_limit,
            limit=args.limit,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
