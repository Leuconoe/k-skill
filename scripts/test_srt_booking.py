import importlib.util
import json
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_PATH = Path(__file__).with_name("srt_booking.py")
seats_stub = types.ModuleType("srt_seats")
seats_stub.parse_cars = lambda _html: []
seats_stub.parse_seats = lambda _html: []
seats_stub.sort_cars_for_booking = lambda cars: cars
seats_stub.sort_seats_for_booking = lambda seats: seats
sys.modules["srt_seats"] = seats_stub
SPEC = importlib.util.spec_from_file_location("srt_booking", SCRIPT_PATH)
assert SPEC and SPEC.loader
srt_booking = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = srt_booking
SPEC.loader.exec_module(srt_booking)


ARCHIVE_HTML = """
<h3>열차 시간표</h3>
<a onclick="   JBCMS.downloadAttach('TK0402050000', '27'); return false;">
  <span>2026. 05. 15. 기준</span>
</a>
<a onclick="   JBCMS.downloadAttach('TK0402050000', '24'); return false;">
  <span>2026. 02. 25. 기준</span>
</a>
"""


class SrtReadOnlyTests(unittest.TestCase):
    def test_parser_exposes_only_search_and_source(self) -> None:
        parser = srt_booking.build_parser()
        subcommands = parser._subparsers._group_actions[0].choices

        self.assertEqual(set(subcommands), {"search", "source"})
        for removed in ("reserve", "cancel", "reservations", "seats", "payment"):
            self.assertNotIn(removed, subcommands)

    def test_search_never_requires_credentials_or_srtrain(self) -> None:
        source = SCRIPT_PATH.read_text()
        self.assertNotIn("KSKILL_SRT_ID", source)
        self.assertNotIn("KSKILL_SRT_PASSWORD", source)
        self.assertNotIn("SRTrain", source)
        self.assertFalse(hasattr(srt_booking, "build_client"))

    def test_choose_latest_timetable_uses_current_official_attachment(self) -> None:
        selected = srt_booking.choose_latest_timetable(ARCHIVE_HTML)

        self.assertEqual(selected.title, "SRT 운행시각표(2026. 05. 15. 기준)")
        self.assertEqual(selected.attachment_no, "27")

    def test_parse_markdown_filters_route_and_time(self) -> None:
        markdown = """
<table>
<tr><th>열차<br>번호</th><th>수서</th><th>동탄</th><th>부산</th></tr>
<tr><td>301</td><td>06:30</td><td>06:47</td><td>09:01</td></tr>
<tr><td>303</td><td>09:00</td><td>09:17</td><td>11:31</td></tr>
</table>
"""

        results = srt_booking.parse_timetable_markdown(
            markdown,
            dep="수서",
            arr="부산",
            earliest="06:00",
            latest="08:00",
        )

        self.assertEqual(
            results,
            [
                {
                    "train_no": "301",
                    "dep": "수서",
                    "arr": "부산",
                    "dep_time": "06:30",
                    "arr_time": "09:01",
                }
            ],
        )

    def test_parse_markdown_returns_empty_for_unknown_station(self) -> None:
        markdown = "<table><tr><th>열차번호</th><th>수서</th><th>부산</th></tr></table>"

        self.assertEqual(
            srt_booking.parse_timetable_markdown(
                markdown,
                dep="서울",
                arr="부산",
                earliest="00:00",
                latest="23:59",
            ),
            [],
        )

    def test_cli_bad_date_fails_without_network(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "search",
                "--dep",
                "수서",
                "--arr",
                "부산",
                "--date",
                "2026-08-20",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("YYYYMMDD", result.stderr)

    def test_search_fetches_each_official_resource_once(self) -> None:
        markdown = """
<table><tr><th>열차번호</th><th>수서</th><th>부산</th></tr>
<tr><td>301</td><td>06:30</td><td>09:01</td></tr></table>
"""
        with (
            mock.patch.object(srt_booking, "fetch_archive", return_value=(ARCHIVE_HTML, "cookie")) as archive,
            mock.patch.object(srt_booking, "download_attachment", return_value=b"hwp") as download,
            mock.patch.object(srt_booking, "convert_hwp_to_markdown", return_value=markdown) as convert,
        ):
            output = srt_booking.search_public_timetable(
                dep="수서",
                arr="부산",
                date="20260820",
                earliest="0600",
                latest="0800",
                limit=5,
            )

        archive.assert_called_once()
        download.assert_called_once()
        convert.assert_called_once_with(b"hwp")
        self.assertEqual(output["count"], 1)
        self.assertEqual(output["source"]["operator"], "주식회사 에스알")
        self.assertEqual(
            output["booking_url"],
            "https://etk.srail.kr/hpg/hra/01/selectScheduleList.do?pageId=TK0101010000",
        )
        self.assertEqual(json.dumps(output, ensure_ascii=False).count("301"), 1)


if __name__ == "__main__":
    unittest.main()
