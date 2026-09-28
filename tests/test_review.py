"""Focused tests for the bounded final evidence/recovery reader."""
import contextlib
import io
from decimal import Decimal
from pathlib import Path
import random
import subprocess
import sys
import unittest
from unittest.mock import patch

import hw1
from test_simulation import ScriptedReader, row


class ReviewTests(unittest.TestCase):
    def solve(self, a, b, review):
        readers = {k: ScriptedReader({'a': [v]}) for k, v in
                   (('ledger', a), ('items', b), ('review', review))}
        with patch.object(hw1, 'image_data_url', return_value='a'), contextlib.redirect_stdout(io.StringIO()):
            result = hw1.answer_queries(readers, [Path('a')])
        for value in result.values():
            self.assertRegex(value, r'^HK\$\d+\.\d{2}$')
        return tuple(result.values()), readers

    def test_stable_wrong_items_corrected_by_fresh_ledger(self):
        result, readers = self.solve(row(10, 2), {'item_amounts': [11]}, row(10, 2))
        self.assertEqual(result, ('HK$10.00', 'HK$12.00'))
        self.assertEqual(readers['review'].calls['a'], 1)

    def test_stable_wrong_discounts_corrected_by_review(self):
        result, _ = self.solve(row(10, 1), {'item_amounts': [12]}, row(10, 2))
        self.assertEqual(result, ('HK$10.00', 'HK$12.00'))

    def test_recover_after_both_readers_fail_all_four_rounds(self):
        result, readers = self.solve(TimeoutError(), ValueError(), row(10, 2))
        self.assertEqual(result, ('HK$10.00', 'HK$12.00'))
        self.assertEqual(readers['ledger'].calls['a'], 4)
        self.assertEqual(readers['items'].calls['a'], 4)
        self.assertEqual(readers['review'].calls['a'], 1)

    def test_review_failure_preserves_existing_amounts(self):
        result, _ = self.solve(row(10, 2), {'item_amounts': [11]}, TimeoutError())
        self.assertEqual(result, ('HK$10.00', 'HK$12.00'))

    def test_new_uncorroborated_guess_is_not_accepted(self):
        result, _ = self.solve(row(10, 2), {'item_amounts': [11]}, row(20, 5))
        self.assertEqual(result, ('HK$10.00', 'HK$12.00'))

    def test_internally_consistent_review_can_correct_both_routes(self):
        review = dict(row(10, 3), item_amounts=[13])
        result, _ = self.solve(row(10, 2), {'item_amounts': [11]}, review)
        self.assertEqual(result, ('HK$10.00', 'HK$13.00'))

    def test_invalid_cash_relationship_rejects_review(self):
        review = dict(row(10, 3), cash_tendered=20, change=5)
        result, _ = self.solve(row(10, 2), {'item_amounts': [11]}, review)
        self.assertEqual(result, ('HK$10.00', 'HK$12.00'))

    def test_failed_audit_preserves_already_reconciled_receipt(self):
        result, readers = self.solve(row(10, 2), {'item_amounts': [12]}, AssertionError())
        self.assertEqual(result, ('HK$10.00', 'HK$12.00'))
        self.assertEqual(readers['review'].calls['a'], 2)

    def test_repeated_audit_corrects_false_primary_agreement(self):
        result, readers = self.solve(row(10, 1), {'item_amounts': [11]},
                                     dict(row(10, 2), item_amounts=[12]))
        self.assertEqual(result, ('HK$10.00', 'HK$12.00'))
        self.assertEqual(readers['review'].calls['a'], 2)

    def test_single_conflicting_audit_cannot_replace_agreement(self):
        chain = {'ledger': ScriptedReader({'a': [row(10, 2)]}),
                 'items': ScriptedReader({'a': [{'item_amounts': [12]}]}),
                 'review': ScriptedReader({'a': [dict(row(10, 3), item_amounts=[13]), None]})}
        with patch.object(hw1, 'image_data_url', return_value='a'), contextlib.redirect_stdout(io.StringIO()):
            result = hw1.answer_queries(chain, [Path('a')])
        self.assertEqual(list(result.values()), ['HK$10.00', 'HK$12.00'])

    def test_zero_review_is_valid_recovery(self):
        result, _ = self.solve(None, None, row(0))
        self.assertEqual(result, ('HK$0.00', 'HK$0.00'))

    def test_item_only_review_recovers_query_two(self):
        result, _ = self.solve(None, None, {'item_amounts': [12]})
        self.assertEqual(result, ('HK$0.00', 'HK$12.00'))

    def test_payment_only_recovery_preserves_existing_agreement(self):
        a = {'subtotal': 10, 'discounts': [2]}
        result, _ = self.solve(a, {'item_amounts': [12]}, {'final_paid': 10})
        self.assertEqual(result, ('HK$10.00', 'HK$12.00'))

    def test_review_failure_remains_bounded(self):
        result, readers = self.solve(None, None, TimeoutError())
        self.assertEqual(result, ('HK$0.00', 'HK$0.00'))
        self.assertEqual(readers['review'].calls['a'], 2)

    def test_transient_review_timeout_recovers_on_second_attempt(self):
        review = ScriptedReader({'a': [TimeoutError(), row(10, 2)]})
        chain = {'ledger': ScriptedReader({'a': [None]}),
                 'items': ScriptedReader({'a': [None]}), 'review': review}
        with patch.object(hw1, 'image_data_url', return_value='a'), contextlib.redirect_stdout(io.StringIO()):
            result = hw1.answer_queries(chain, [Path('a')])
        self.assertEqual(list(result.values()), ['HK$10.00', 'HK$12.00'])
        self.assertEqual(review.calls['a'], 2)

    def test_fifty_random_recovery_scenarios(self):
        rng = random.Random(5661)
        for scenario in range(50):
            paid_cents = rng.randint(0, 100000)
            discount_cents = rng.randint(100, 10000)
            paid = str(Decimal(paid_cents) / 100)
            discount = str(Decimal(discount_cents) / 100)
            full = str(Decimal(paid_cents + discount_cents) / 100)
            good = row(paid, discount)
            if scenario % 3 == 0:
                a, b = None, TimeoutError()
            elif scenario % 3 == 1:
                a, b = row(paid, '0'), {'item_amounts': [full]}
            else:
                a, b = good, {'item_amounts': [paid]}
            with self.subTest(scenario=scenario):
                result, readers = self.solve(a, b, good)
                self.assertEqual(result, (f'HK${Decimal(paid):.2f}', f'HK${Decimal(full):.2f}'))
                self.assertEqual(readers['review'].calls['a'], 1)

    def test_review_only_receives_unresolved_image(self):
        a = ScriptedReader({'ok': [row(10, 2)], 'bad': [row(20, 3)]})
        b = ScriptedReader({'ok': [{'item_amounts': [12]}], 'bad': [{'item_amounts': [22]}]})
        review = ScriptedReader({'bad': [row(20, 3)]})
        with patch.object(hw1, 'image_data_url', side_effect=lambda p: p.name), contextlib.redirect_stdout(io.StringIO()):
            result = hw1.answer_queries({'ledger': a, 'items': b, 'review': review}, [Path('bad'), Path('ok')])
        self.assertEqual(list(result.values()), ['HK$30.00', 'HK$35.00'])
        self.assertEqual(dict(review.calls), {'bad': 1, 'ok': 2})

    def test_reserve_allows_recovery_after_main_reader_stalls(self):
        script = '''
import hw1, threading, time
from unittest.mock import patch
clock = time.monotonic
first = True
def shifted():
    global first
    if first:
        first = False
        return clock() - 89.9
    return clock()
class Stuck:
    def invoke(self, value): threading.Event().wait()
class Recovery:
    def invoke(self, value):
        return {'subtotal':10,'final_paid':10,'rounding':0,'discounts':[2]}
with patch.object(hw1,'image_data_url',return_value='a'), patch('time.monotonic',side_effect=shifted):
    result=hw1.answer_queries({'ledger':Stuck(),'items':Stuck(),'review':Recovery()},[hw1.Path('a')])
assert list(result.values()) == ['HK$10.00','HK$12.00'], result
'''
        result = subprocess.run([sys.executable, '-c', script], cwd=Path(hw1.__file__).parent,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
