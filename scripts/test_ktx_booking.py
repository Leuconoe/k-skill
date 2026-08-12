import importlib.util
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


class FakeTrain:
    train_no = "75"
    train_type_name = "KTX-산천"
    dep_date = "20260819"
    dep_time = "060300"
    arr_time = "084900"
    dep_name = "서울"
    arr_name = "부산"
    def has_general_seat(self):
        return True

    def has_special_seat(self):
        return False


class AdjacentTrain(FakeTrain):
    train_no = "703"
    dep_name = "청량리"
    arr_name = "부전"


class FakeKorail:
    def __init__(self, korail_id, korail_pw, auto_login):
        self.init = (korail_id, korail_pw, auto_login)
        self.calls = []

    def search_train(self, **kwargs):
        self.calls.append(("search_train", kwargs))
        return [FakeTrain(), AdjacentTrain()]

    def reserve(self, *_args, **_kwargs):
        raise AssertionError("reserve must never be called")

    def cancel(self, *_args, **_kwargs):
        raise AssertionError("cancel must never be called")


class KtxLiveReadOnlyTests(unittest.TestCase):
    def test_parser_exposes_only_search_and_source(self) -> None:
        parser = ktx_booking.build_parser()
        subcommands = parser._subparsers._group_actions[0].choices

        self.assertEqual(set(subcommands), {"search", "source"})

    def test_helper_uses_live_korail2_not_file_transport(self) -> None:
        source = SCRIPT_PATH.read_text()
        self.assertIn("korail2", source)
        self.assertNotIn("openpyxl", source)
        self.assertNotIn("userBoard.do", source)
        self.assertNotIn("cubedata", source)

    def test_search_uses_anonymous_client_and_only_search_train(self) -> None:
        client = FakeKorail("", "", False)
        with mock.patch.object(ktx_booking, "build_client", return_value=client):
            result = ktx_booking.search_live_timetable(
                dep="서울",
                arr="부산",
                date="20260819",
                earliest="0600",
                latest="1200",
                limit=5,
            )

        self.assertEqual(client.init, ("", "", False))
        self.assertEqual([name for name, _kwargs in client.calls], ["search_train"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["trains"][0]["train_no"], "75")
        self.assertEqual(result["trains"][0]["dep_time"], "06:03")
        self.assertEqual(result["source"]["transport"], "korail2")

    def test_source_reports_live_schedule_endpoint_only(self) -> None:
        source = ktx_booking.source_info()

        self.assertEqual(source["mode"], "live")
        self.assertIn("ScheduleView", source["endpoint"])
        self.assertNotIn("Reservation", source["endpoint"])

    def test_module_has_no_state_changing_command_functions(self) -> None:
        for name in ("command_reserve", "command_cancel", "command_reservations", "command_payment"):
            self.assertFalse(hasattr(ktx_booking, name))

    def test_cli_bad_time_fails_before_client_creation(self) -> None:
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
                "20260819",
                "--time",
                "2500",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("HHMM", result.stderr)


if __name__ == "__main__":
    unittest.main()
