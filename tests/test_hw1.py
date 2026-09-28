"""Offline boundary tests. Run: python -m unittest discover -s tests -v."""
import contextlib
import csv
import io
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import hw1


class Reader:
    def __init__(self, *values):
        self.values = values
        self.calls = 0
        self.lock = threading.Lock()

    def invoke(self, value):
        with self.lock:
            result = self.values[min(self.calls, len(self.values) - 1)]
            self.calls += 1
        if isinstance(result, Exception):
            raise result
        return result


def ledger(subtotal="102.31", paid="102.30", discounts=None, **extra):
    return dict(subtotal=subtotal, final_paid=paid,
                discounts=["-5.39"] if discounts is None else discounts, **extra)


class ReceiptTests(unittest.TestCase):
    def solve(self, a, b, count=1):
        self.a = a if isinstance(a, Reader) else Reader(a)
        self.b = b if isinstance(b, Reader) else Reader(b)
        with patch.object(hw1, "image_data_url", return_value="data:image/jpeg;base64,AA=="):
            with contextlib.redirect_stdout(io.StringIO()):
                result = hw1.answer_queries(
                    {"ledger": self.a, "items": self.b}, [Path(f"{i}.jpg") for i in range(count)])
        self.assertEqual(set(result), set(hw1.QUERIES))
        for value in result.values():
            self.assertRegex(value, r"^HK\$\d+\.\d{2}$")
        return tuple(result[q] for q in hw1.QUERIES)

    def test_pdf_example(self):
        self.assertEqual(self.solve(ledger(), {"item_amounts": [10, "36.90", "60.80"]}),
                         ("HK$102.30", "HK$107.70"))
        self.assertEqual(self.a.calls, 1)

    def test_no_discount(self):
        self.assertEqual(self.solve(ledger("12.30", "12.30", []), {"item_amounts": ["12.30"]}),
                         ("HK$12.30", "HK$12.30"))

    def test_multiple_signed_discounts(self):
        self.assertEqual(self.solve(ledger("10.05", "10.00", [-2, 3, {"amount": "-0.25"}]),
                                    {"item_amounts": ["15.30"]}), ("HK$10.00", "HK$15.30"))

    def test_positive_rounding(self):
        self.assertEqual(self.solve(ledger("10.06", "10.10", [], rounding="0.04"),
                                    {"item_amounts": ["10.06"]}), ("HK$10.10", "HK$10.06"))

    def test_cash_change(self):
        self.assertEqual(self.solve(ledger(paid=None, cash_tendered=200, change="97.70"),
                                    {"item_amounts": ["107.70"]}), ("HK$102.30", "HK$107.70"))

    def test_missing_subtotal_with_rounding(self):
        self.assertEqual(self.solve(ledger(subtotal=None, rounding="-0.01"),
                                    {"item_amounts": ["107.70"]}), ("HK$102.30", "HK$107.70"))

    def test_missing_paid_with_rounding(self):
        self.assertEqual(self.solve(ledger(paid=None, rounding="-0.01"),
                                    {"item_amounts": ["107.70"]}), ("HK$102.30", "HK$107.70"))

    def test_missing_subtotal_not_replaced_with_paid(self):
        a = Reader(ledger(subtotal=None), ledger())
        self.assertEqual(self.solve(a, {"item_amounts": ["107.70"]}), ("HK$102.30", "HK$107.70"))
        self.assertEqual(a.calls, 2)

    def test_invalid_numbers_retry(self):
        for bad in ("NaN", "Infinity", True, "12,34", "1e999", "5%", "1.234", {}, []):
            with self.subTest(bad=bad):
                a = Reader(ledger(discounts=[bad]), ledger())
                self.assertEqual(self.solve(a, {"item_amounts": ["107.70"]}),
                                 ("HK$102.30", "HK$107.70"))
                self.assertEqual(a.calls, 2)

    def test_missing_discount_list_retry(self):
        bad = ledger()
        del bad["discounts"]
        a = Reader(bad, ledger())
        self.assertEqual(self.solve(a, {"item_amounts": ["107.70"]}), ("HK$102.30", "HK$107.70"))
        self.assertEqual(a.calls, 2)

    def test_zero_receipt(self):
        self.assertEqual(self.solve(ledger(0, 0, []), {"item_amounts": [0]}),
                         ("HK$0.00", "HK$0.00"))
        self.assertEqual(self.a.calls, 1)

    def test_currency_and_thousands(self):
        self.assertEqual(self.solve(ledger("HK$1,000.00", "HKD 1,000.00", ["$10.00"]),
                                    {"item_amounts": ["1,010.00"]}), ("HK$1000.00", "HK$1010.00"))

    def test_malformed_and_transport_retry(self):
        a = Reader(ValueError("invalid JSON"), RuntimeError("network failure"), [], ledger())
        self.assertEqual(self.solve(a, {"item_amounts": ["107.70"]}), ("HK$102.30", "HK$107.70"))
        self.assertEqual(a.calls, 4)

    def test_inconsistent_cash_and_rounding_retry(self):
        for bad in (ledger(paid=200, cash_tendered=200, change="97.70"),
                    ledger(rounding="0.01"), ledger(cash_tendered=1, change=2)):
            a = Reader(bad, ledger())
            self.assertEqual(self.solve(a, {"item_amounts": ["107.70"]}), ("HK$102.30", "HK$107.70"))
            self.assertEqual(a.calls, 2)

    def test_partial_failure_does_not_discard_other_query(self):
        self.assertEqual(self.solve(RuntimeError("unavailable"), {"item_amounts": ["107.70"]}),
                         ("HK$0.00", "HK$107.70"))

    def test_total_failure_is_bounded(self):
        self.assertEqual(self.solve(RuntimeError("unavailable"), ValueError("bad JSON")),
                         ("HK$0.00", "HK$0.00"))
        self.assertEqual(self.a.calls, 4)

    def test_empty_input(self):
        self.assertEqual(self.solve(None, None, count=0), ("HK$0.00", "HK$0.00"))
        self.assertEqual(self.a.calls, 0)

    def test_deadline_stops_waiting_for_stuck_provider(self):
        # A separate process proves shutdown is not held open by stuck workers.
        script = '''
import hw1, time, threading
from unittest.mock import patch
real_clock = time.monotonic
first = True
def clock():
    global first
    if first:
        first = False
        return real_clock() - 179.9
    return real_clock()
class Stuck:
    def invoke(self, value):
        threading.Event().wait()
with patch.object(hw1, 'image_data_url', return_value='data:image/jpeg;base64,AA=='):
    with patch('time.monotonic', side_effect=clock):
        result = hw1.answer_queries({'ledger': Stuck(), 'items': Stuck()}, [hw1.Path('one.jpg')])
assert result[hw1.QUERY_1] == 'HK$0.00'
'''
        done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                              timeout=5, cwd=Path(hw1.__file__).parent)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_main_rejects_empty_folder_as_template_requires(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("sys.argv", ["hw1.py", "--image-folder", directory]):
                with self.assertRaisesRegex(SystemExit, "no supported images"):
                    hw1.main()

    def test_duplicate_receipts_are_counted(self):
        self.assertEqual(self.solve(ledger(), {"item_amounts": ["107.70"]}, count=2),
                         ("HK$204.60", "HK$215.40"))

    def test_missing_image(self):
        with contextlib.redirect_stdout(io.StringIO()):
            result = hw1.answer_queries({"ledger": Reader(None), "items": Reader(None)},
                                        [Path("/nonexistent/hw1-test.jpg")])
        self.assertEqual(result[hw1.QUERY_1], "HK$0.00")

    def test_unstable_items_use_steady_ledger(self):
        self.assertEqual(self.solve(ledger(), Reader(*[{"item_amounts": [n]} for n in (101, 102, 103, 104)])),
                         ("HK$102.30", "HK$107.70"))

    def test_bad_item_is_not_silently_omitted(self):
        b = Reader({"item_amounts": ["107.70", "unreadable"]}, {"item_amounts": ["107.70"]})
        self.assertEqual(self.solve(ledger(), b), ("HK$102.30", "HK$107.70"))
        self.assertEqual(b.calls, 2)

    def test_public_totals_and_every_single_receipt_offline(self):
        data = json.loads((Path(hw1.__file__).parent / "public_test/ground_truth.json").read_text())
        for row in data["receipts"].values():
            self.assertEqual(self.solve(ledger(row["subtotal_after_discounts_before_rounding"],
                                              row["amount_paid_after_rounding"], [row["discount_total"]]),
                                        {"item_amounts": [row["amount_without_discounts"]]}),
                             (f"HK${row['amount_paid_after_rounding']:.2f}",
                              f"HK${row['amount_without_discounts']:.2f}"))

    def test_all_public_subsets_offline(self):
        receipts = json.loads((Path(hw1.__file__).parent / "public_test/ground_truth.json").read_text())["receipts"]
        class PublicReader:
            def __init__(self, kind): self.kind = kind
            def invoke(self, value):
                row = receipts[value["image_url"]]
                if self.kind == "items":
                    return {"item_amounts": [row["amount_without_discounts"]]}
                return ledger(row["subtotal_after_discounts_before_rounding"],
                              row["amount_paid_after_rounding"], [row["discount_total"]])
        chain = {key: PublicReader(key) for key in ("ledger", "items")}
        for size in range(1, 8):
            for names in itertools.combinations(receipts, size):
                with self.subTest(names=names):
                    with patch.object(hw1, "image_data_url", side_effect=lambda path: path.name):
                        result = hw1.answer_queries(chain, [Path(name) for name in reversed(names)])
                    for query, field in ((hw1.QUERY_1, "amount_paid_after_rounding"),
                                         (hw1.QUERY_2, "amount_without_discounts")):
                        expected = sum(hw1.Decimal(str(receipts[name][field])) for name in names)
                        self.assertEqual(result[query], f"HK${expected:.2f}")

    def test_main_writes_csv_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = Path.cwd()
            try:
                os.chdir(directory)
                Path("receipt.jpg").touch()
                with patch.object(hw1, "build_chain", return_value={"ledger": Reader(ledger()),
                                                                  "items": Reader({"item_amounts": ["107.70"]})}):
                    with patch("sys.argv", ["hw1.py", "--image-folder", directory]):
                        with contextlib.redirect_stdout(io.StringIO()):
                            self.assertEqual(hw1.main(), 0)
                with Path("results.csv").open() as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[0]["model_response"], "HK$102.30")
                self.assertEqual(rows[1]["model_response"], "HK$107.70")
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
