import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_PATH = Path(__file__).with_name("ktx_booking.py")
SPEC = importlib.util.spec_from_file_location("ktx_booking", SCRIPT_PATH)
assert SPEC and SPEC.loader
ktx_booking = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ktx_booking
SPEC.loader.exec_module(ktx_booking)


BOARD_PAYLOAD = {
    "boardList": [
        {
            "bdIdx": 1,
            "bdCode": "_ticketTable02",
            "bdTitle": "KTX 시간표(2026. 9. 1. 기준)",
            "fileId": ["jfile/202608/01/current.xlsx"],
            "regdt": "2026-08-01",
        },
        {
            "bdIdx": 2,
            "bdCode": "_ticketTable02",
            "bdTitle": "KTX 시간표(2026. 8. 1. 기준)",
            "fileId": ["jfile/202607/01/old.xlsx"],
            "regdt": "2026-07-01",
        },
    ]
}


class KtxReadOnlyTests(unittest.TestCase):
    def test_parser_exposes_only_search_and_source(self) -> None:
        parser = ktx_booking.build_parser()
        subcommands = parser._subparsers._group_actions[0].choices

        self.assertEqual(set(subcommands), {"search", "source"})
        for removed in ("reserve", "cancel", "reservations", "seats", "ncard-list"):
            self.assertNotIn(removed, subcommands)

    def test_search_never_requires_credentials(self) -> None:
        self.assertNotIn("KSKILL_KTX_ID", SCRIPT_PATH.read_text())
        self.assertNotIn("KSKILL_KTX_PASSWORD", SCRIPT_PATH.read_text())
        self.assertFalse(hasattr(ktx_booking, "build_client"))

    def test_choose_latest_timetable_uses_current_official_attachment(self) -> None:
        selected = ktx_booking.choose_latest_timetable(BOARD_PAYLOAD)

        self.assertEqual(selected.title, "KTX 시간표(2026. 9. 1. 기준)")
        self.assertEqual(
            selected.download_url,
            "https://www.korail.com/file/cubedata/COMMON/jfile/202608/01/current.xlsx",
        )

    def test_choose_timetable_for_date_does_not_use_future_schedule(self) -> None:
        selected = ktx_booking.choose_timetable_for_date(BOARD_PAYLOAD, "20260820")

        self.assertEqual(selected.title, "KTX 시간표(2026. 8. 1. 기준)")
        self.assertTrue(selected.download_url.endswith("/old.xlsx"))

    def test_parse_rows_filters_route_time_and_ktx_only(self) -> None:
        rows = [
            ["", "열차번호", "편성", "서울", "대전", "부산"],
            ["", "101", "KTX", "07:00", "08:00", "09:40"],
            ["", "1201", "무궁화", "07:10", "08:30", "12:00"],
            ["", "103", "KTX", "09:00", "10:00", "11:40"],
        ]

        results = ktx_booking.parse_timetable_rows(
            rows,
            dep="서울",
            arr="부산",
            earliest="06:00",
            latest="08:00",
        )

        self.assertEqual(
            results,
            [
                {
                    "train_no": "101",
                    "dep": "서울",
                    "arr": "부산",
                    "dep_time": "07:00",
                    "arr_time": "09:40",
                }
            ],
        )

    def test_parse_rows_returns_empty_for_unknown_station(self) -> None:
        rows = [["", "열차번호", "편성", "서울", "부산"], ["", "101", "KTX", "07:00", "09:40"]]

        self.assertEqual(
            ktx_booking.parse_timetable_rows(rows, dep="수서", arr="부산", earliest="00:00", latest="23:59"),
            [],
        )

    def test_cli_bad_time_fails_without_network(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "search",
                "--dep",
                "서울",
                "--arr",
                "부산",
                "--date",
                "20260820",
                "--time",
                "2500",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HHMM", result.stderr)

    def test_search_fetches_each_official_resource_once(self) -> None:
        workbook = mock.Mock()
        workbook.sheetnames = ["경부선"]
        worksheet = mock.Mock()
        worksheet.iter_rows.return_value = iter(
            [["", "열차번호", "편성", "서울", "부산"], ["", "101", "KTX", "07:00", "09:40"]]
        )
        workbook.__getitem__ = mock.Mock(return_value=worksheet)

        with (
            mock.patch.object(ktx_booking, "fetch_json", return_value=BOARD_PAYLOAD) as fetch_json,
            mock.patch.object(ktx_booking, "download_bytes", return_value=b"xlsx") as download,
            mock.patch.object(ktx_booking, "load_workbook_bytes", return_value=workbook),
        ):
            output = ktx_booking.search_public_timetable(
                dep="서울",
                arr="부산",
                date="20260820",
                earliest="0600",
                latest="0800",
                limit=5,
            )

        fetch_json.assert_called_once()
        download.assert_called_once()
        self.assertEqual(output["count"], 1)
        self.assertEqual(output["source"]["operator"], "한국철도공사")
        self.assertEqual(output["booking_url"], "https://www.korail.com/ticket/train/schedule")
        self.assertEqual(json.dumps(output, ensure_ascii=False).count("101"), 1)


if __name__ == "__main__":
    unittest.main()
