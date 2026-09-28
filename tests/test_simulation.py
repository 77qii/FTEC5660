"""Deterministic fault injection and synthetic receipts; no API calls."""
from collections import Counter
import contextlib
import csv
from decimal import Decimal
import io
import os
from pathlib import Path
import random
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import hw1


class ScriptedReader:
    def __init__(self, scripts, delays=None):
        self.scripts = scripts
        self.delays = delays or {}
        self.calls = Counter()
        self.lock = threading.Lock()
        self.active = self.peak = 0

    def invoke(self, value):
        name = value['image_url']
        with self.lock:
            attempt = self.calls[name]
            self.calls[name] += 1
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            time.sleep(self.delays.get(name, 0))
            script = self.scripts[name]
            result = script[min(attempt, len(script) - 1)]
            if isinstance(result, Exception):
                raise result
            return result
        finally:
            with self.lock:
                self.active -= 1


def row(paid, discounts=0):
    return {'subtotal': paid, 'final_paid': paid, 'rounding': 0,
            'discounts': [discounts]}


class SimulationTests(unittest.TestCase):
    def run_case(self, names, ledgers, items, delays=None):
        a, b = ScriptedReader(ledgers, delays), ScriptedReader(items, delays)
        output = io.StringIO()
        with patch.object(hw1, 'image_data_url', side_effect=lambda p: p.name):
            with contextlib.redirect_stdout(output):
                result = hw1.answer_queries({'ledger': a, 'items': b}, list(map(Path, names)))
        self.assertEqual(set(result), set(hw1.QUERIES))
        for value in result.values():
            self.assertRegex(value, r'^HK\$\d+\.\d{2}$')
        return result, a, b, output.getvalue()

    def test_retry_subset_preserves_identity_and_order(self):
        names = ['good', 'slow', 'fail_then_good', 'bad_json']
        a = {n: [row(i + 1)] for i, n in enumerate(names)}
        b = {n: [{'item_amounts': [i + 1]}] for i, n in enumerate(names)}
        a['fail_then_good'].insert(0, TimeoutError())
        a['bad_json'] = ['not JSON', [], None, row(4)]
        result, ra, rb, _ = self.run_case(names, a, b, {'slow': 0.01})
        self.assertEqual(list(result.values()), ['HK$10.00', 'HK$10.00'])
        self.assertEqual(ra.calls, Counter(good=1, slow=1, fail_then_good=2, bad_json=4))
        self.assertEqual(ra.calls, rb.calls)

    def test_concurrency_cap_with_65_receipts(self):
        names = [str(i) for i in range(65)]
        result, a, b, _ = self.run_case(names, {n: [row(1)] for n in names},
                                      {n: [{'item_amounts': [1]}] for n in names},
                                      {n: 0.004 for n in names})
        self.assertEqual(list(result.values()), ['HK$65.00', 'HK$65.00'])
        self.assertLessEqual(a.peak, 8)
        self.assertLessEqual(b.peak, 8)
        self.assertGreater(a.peak, 1)

    def test_random_synthetic_receipts_with_transient_faults(self):
        # Oracle uses integer cents, independent of the implementation's Decimal sums.
        rng = random.Random(5660)
        for scenario in range(100):
            names, a, b = [], {}, {}
            paid_total = without_total = 0
            for index in range(rng.randint(1, 20)):
                name = f'{scenario}-{index}.jpg'
                names.append(name)
                amounts = [rng.randint(0, 100000) for _ in range(rng.randint(1, 12))]
                original = sum(amounts)
                discount = rng.randint(0, original)
                subtotal = original - discount
                rounding = rng.randint(-min(9, subtotal), 9)
                paid = subtotal + rounding
                money = lambda cents: f'{cents // 100}.{cents % 100:02d}'
                record = {'subtotal': money(subtotal), 'final_paid': money(paid),
                          'rounding': str(Decimal(rounding) / 100),
                          'discounts': [str(-Decimal(discount) / 100)]}
                if index % 3 == 0:
                    record['final_paid'] = None
                    record['cash_tendered'] = money(paid + 5000)
                    record['change'] = '50.00'
                elif index % 3 == 1:
                    record['subtotal'] = None
                a[name] = [TimeoutError('simulated')] * rng.randrange(4) + [record]
                b[name] = [None] * rng.randrange(4) + [{'item_amounts': list(map(money, amounts))}]
                paid_total += paid
                without_total += original
            rng.shuffle(names)
            with self.subTest(scenario=scenario):
                result, ra, rb, _ = self.run_case(names, a, b)
                self.assertEqual(result[hw1.QUERY_1], f'HK${paid_total // 100}.{paid_total % 100:02d}')
                self.assertEqual(result[hw1.QUERY_2], f'HK${without_total // 100}.{without_total % 100:02d}')
                self.assertTrue(all(n <= 4 for n in ra.calls.values()))
                self.assertTrue(all(n <= 4 for n in rb.calls.values()))

    def test_payment_from_reconciled_reading_beats_earlier_unresolved_vote(self):
        first = {'subtotal': '102.31', 'final_paid': '102.40', 'discounts': None}
        fixed = {'subtotal': '102.31', 'final_paid': '102.30', 'rounding': '-0.01', 'discounts': ['5.39']}
        result, _, _, _ = self.run_case(['a'], {'a': [first, fixed]},
                                       {'a': [{'item_amounts': ['107.70']}]})
        self.assertEqual(result[hw1.QUERY_1], 'HK$102.30')

    def test_permanent_failure_does_not_remove_successful_receipts(self):
        result, a, _, log = self.run_case(['ok', 'bad'],
            {'ok': [row(10, 2)], 'bad': [RuntimeError()]},
            {'ok': [{'item_amounts': [12]}], 'bad': [None]})
        self.assertEqual(list(result.values()), ['HK$10.00', 'HK$12.00'])
        self.assertEqual(a.calls, Counter(ok=1, bad=4))
        self.assertIn('counted as 0.00', log)

    def test_stable_wrong_items_do_not_override_usable_ledger(self):
        # With no evidence review available, use the assignment's ledger definition.
        result, _, _, log = self.run_case(['a'], {'a': [row(10, 2)]},
                                         {'a': [{'item_amounts': [11]}]})
        self.assertEqual(result[hw1.QUERY_2], 'HK$12.00')
        self.assertIn('disagreed', log)

    def test_main_writes_incorrect_not_correct_on_total_failure(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                Path('a.jpg').touch()
                chain = {k: ScriptedReader({'a.jpg': [TimeoutError()]}) for k in ('ledger', 'items')}
                truth = {q: Decimal('10.00') for q in hw1.QUERIES}
                with patch.object(hw1, 'build_chain', return_value=chain), \
                     patch.object(hw1, 'image_data_url', side_effect=lambda p: p.name), \
                     patch.object(hw1, 'read_ground_truth', return_value=truth), \
                     patch('sys.argv', ['hw1.py', '--image-folder', directory]), \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(hw1.main(), 0)
                with Path('results.csv').open() as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual(len(rows), 2)
                self.assertTrue(all(r['correctness'].startswith('incorrect:') for r in rows))
            finally:
                os.chdir(previous)

    def test_langchain_prompt_and_parser_without_network(self):
        from langchain_core.runnables import RunnableLambda
        from langchain_core.messages import AIMessage
        seen = []
        def fake_model(prompt):
            seen.append(prompt.to_messages())
            return AIMessage(content='{"subtotal":10,"final_paid":10,"discounts":[]}')
        with patch('langchain_deepseek.ChatDeepSeek', return_value=RunnableLambda(fake_model)) as factory:
            chain = hw1.build_chain()
        self.assertEqual(factory.call_args.kwargs['model'], 'deepseek-v4-flash-vision-exp')
        result = chain['ledger'].invoke({'image_url': 'data:image/jpeg;base64,AA=='})
        self.assertEqual(result['final_paid'], 10)
        self.assertEqual(seen[0][1].content[0]['image_url']['url'], 'data:image/jpeg;base64,AA==')
        self.assertIn('CASH', seen[0][0].content)
        self.assertEqual(set(chain), {'ledger', 'items', 'review'})
        chain['review'].invoke({'image_url': 'data:image/jpeg;base64,AA=='})
        self.assertIn('Do not adjust any digit', seen[1][0].content)
        self.assertEqual(factory.call_count, 1)


if __name__ == '__main__':
    unittest.main()
