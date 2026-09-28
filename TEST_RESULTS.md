# Homework 1 validation

Date: 28 September 2026.

## Audit and timeout fix — current status

Current `hw1.py` SHA-256:
`2dc3249565d9ce25d9f5546a82697a4a008717f3c7d994f506beb9250e02e283`.

- **52 offline tests passed** in 2.548 seconds. New regression cases verify
  correction of false primary agreement by two consistent, internally checked
  audit readings, and rejection of a single conflicting audit. Failed audits
  preserve existing usable evidence. Existing boundary/recovery tests still pass.
- Request timeout increased from 40 to 90 seconds. Audit reserve is now 180
  seconds per eight images, capped at half the overall budget. The overall
  deadline remains max(180 seconds, 90 seconds per image); a short deadline can
  still truncate requests. Every readable image is audited, including receipts
  whose primary readers agreed. This increases requests and latency.
- The REAL recovery test passed: forced failure of both primary readers for
  receipts 2 and 4, followed by real API review, returned HK$830.10 / HK$983.00.
- **Three consecutive real seven-receipt CLI runs all passed both queries**:
  each returned HK$1974.30 / HK$2348.20 and generated the required CSV.
- Run 1 caught a review ledger reading of 391.20 for receipt2 against its item
  total of 392.20. The existing corroborated 392.20 was retained. This is direct
  evidence of a one-dollar reading discrepancy, but does not identify the exact
  cause of the earlier unlogged failed run.
- Run 3 review gave receipt4 an inconsistent item total of 607.70; the ledger
  evidence supported 590.80, which was selected correctly. Thus raw OCR errors
  remain even when final answers pass. Three public passes do not guarantee
  private-set accuracy or full marks; mutually consistent errors and complete
  provider failure remain limitations.
- Text outside the two permitted functions was verified byte-identical to the
  repository template. No public answers were added to implementation logic.
  Per-receipt audit and selected amounts are now printed for diagnosis.

All following sections are historical and retain previous failures/results.

## Post-recharge rerun — before audit and timeout fix

The implementation was not changed for this rerun; its SHA-256 remains
`d289b68fc0a6a7779a80c69d352fbead8e743ef267c0f8c245854067629c823c`.
All 50 offline tests passed again (2.155 seconds).

Three consecutive real CLI runs used all seven public receipts:

| Run | Actual paid | Without discounts | Result |
| --- | --- | --- | --- |
| 1 | HK$1974.30 | HK$2348.20 | Both correct |
| 2 | HK$1974.30 | HK$2348.20 | Both correct |
| 3 | HK$1974.30 | HK$2347.20 | Query 2 incorrect: HK$1.00 too low |

All three runs generated CSV successfully. Timeouts remained frequent; run 2
reached the second evidence-review attempt and ultimately passed. No HTTP 402
was observed in these reruns. Run 3 demonstrates remaining recognition or
reconciliation instability, not merely the earlier account restriction. Its
per-receipt raw readings were not logged, so the precise misread is not known.
At that time, `results.csv` retained the third run, including its failed score.
These results do not justify an all-tests-pass or full-marks claim.

The separate forced-primary-failure recovery test also **failed** after recharge.
Both primary readers were deliberately replaced with timeout mocks for receipts
2 and 4; the review reader used the real API. Both review attempts timed out for
both receipts. Actual output was HK$0.00 / HK$0.00 instead of HK$830.10 / HK$983.00.
This confirms that recovery remains dependent on a timely provider response;
the current 40-second request timeout did not suffice in this test. Neither
implementation nor timeout settings were changed during this rerun.

## Targeted revision — before recharge

Current `hw1.py` SHA-256:
`d289b68fc0a6a7779a80c69d352fbead8e743ef267c0f8c245854067629c823c`.

- Offline suite: **50 tests passed**. The 16 new review tests cover stable
  incorrect item readings, incorrect discount readings, evidence corroboration,
  rejection of new unsupported guesses, cash inconsistencies, genuine zero,
  partial-field recovery, complete primary-reader failure, bounded review
  retries, a stuck primary reader, 50 seeded recovery scenarios, and receipt
  identity. Earlier subset/randomized tests remain included.
- Unresolved receipts now receive a separate image-based evidence review, with
  at most one recovery retry, within the original overall deadline. Review does
  not see prior answers. Usable ledger evidence takes priority over conflicting
  item-only fallback, fixing the simulated stable-item-error case (12, not 11).
- During live validation, the first two seven-receipt runs returned
  HK$1974.30 / HK$2348.20 correctly. These used the initial one-review version.
- The third seven-receipt run used the current two-attempt recovery version.
  Many provider timeouts/APIStatusError responses occurred. It still wrote CSV,
  but returned HK$0.00 / HK$221.20: **both incorrect**.
- A forced-primary-failure test with REAL review calls on receipts 2 and 4
  failed in both the initial and current recovery versions: review calls timed
  out or returned status errors. Actual HK$0.00 / HK$0.00 did not match expected
  HK$830.10 / HK$983.00. Mocked recovery tests pass; real recovery is not verified.
- No claim of all live tests passing or guaranteed full marks is justified.
  Complete provider failure can still leave zero/partial totals. Stable,
  mutually consistent OCR errors can also escape arithmetic checks.
- A subsequent single-request diagnostic returned HTTP **402**, with error
  code `invalid_request_error`. This suggests an account/billing restriction;
  the account balance was not inspected. Earlier errors cannot all be attributed
  to this status. Further live calls were stopped pending account verification.

The sections below are historical records for earlier revisions. References to
“final”, older test counts, or successful API runs there apply to those revisions,
not certification of the current source hash above.

## Scope and environment

- Python 3.13.5.
- Dependencies installed from the unchanged `requirements.txt` into a new,
  independent virtual environment; `pip check` passed in the project environment.
- The project's stale `python3` virtual-environment link was repaired to use
  its Python 3.13 interpreter, and the dependencies were installed there too.
- Text outside `build_chain()` and `answer_queries()` was compared with the
  upstream teacher template and matches exactly, including the CSV/scoring code.
- Model construction verified `deepseek-v4-flash-vision-exp` and a single
  `image_url` prompt input. API keys were not printed or added to the tests.

## Offline tests

Command: `.venv/bin/python -m unittest discover -s tests -v`.

Result: **26 tests passed**, including subtests of all **127 nonempty subsets**
of the seven public receipts, with reversed input order. These tests supply
simulated extraction results; they verify the program's arithmetic and handling
of responses, not the accuracy of image recognition.

Coverage includes the PDF example, no discounts, multiple signed discounts,
positive/negative rounding, cash tendered and change, missing subtotal/payment,
missing discount lists, malformed items, NaN/infinity/booleans, malformed currency
and percentage strings, zero-value receipts, duplicate receipts, network/JSON
failures, independent recovery of the two queries, exhausted retries, missing
images, empty input, empty-folder rejection by the unchanged runner, and CSV
generation. A subprocess test uses a permanently blocked fake provider and
confirms that the deadline allows the process to exit.

## Real API tests

| Input | Actual paid | Without discounts | Result |
| --- | --- | --- | --- |
| All seven public receipts | HK$1974.30 | HK$2348.20 | Both CSV rows `correct` |
| receipt2.jpg + receipt4.jpg | HK$830.10 | HK$983.00 | Both assertions passed |
| All seven, final files in a clean directory | HK$1974.30 | HK$2348.20 | Both CSV rows `correct` |

The full public run required retries for three receipts, then one receipt.
Receipt7 remained inconsistent and was settled by voting at HK$396.00.
A separate direct ledger extraction of receipt5 returned subtotal 102.31,
payment 102.30, rounding -0.01 and discount 5.39, matching the PDF example.

The final clean-directory API run passed after recovering from one API timeout
and retrying one unresolved receipt. This used a local export of the final
submission files, not a GitHub clone: the machine's Git
command requires unavailable Apple developer tools. The API key is inherited
through the process environment rather than copied into the test directory.

## Expanded offline simulation (follow-up)

Command: `.venv/bin/python -m unittest discover -s tests -v`.

Result after the regression fix: **34 tests passed**. The expanded suite in
`tests/test_simulation.py` includes 100 reproducible randomly generated folders
(seed 5660; 1–20 receipts per folder), using integer-cent expected totals. It
injects independent transient failures into each reader, tests up to three
failures followed by recovery, shuffles receipt order, and varies discounts,
rounding, cash/change and missing fields. The existing 127 public-subset
simulations also pass. A 65-receipt test checks the eight-request concurrency
cap and aggregation; delayed responses and different retry subsets verify
receipt identity is preserved. Additional cases exercise complete and partial
failures, CSV scoring on failed extraction, and the actual LangChain prompt and
JSON parser with a fake model (no network calls).

The initial expanded run had one failure: an earlier unresolved payment of
102.40 tied with a later reconciled reading of 102.30, and the median tie rule
chose 102.40. Payment selection now prefers readings from a round with matching
ledger/item totals before falling back to all payment votes. The regression
test and full suite pass. This remains a consistency heuristic, not independent
verification of the payment. Changes remain inside the two permitted functions;
the rest of the source was compared against the upstream template again.

One test explicitly records a known accuracy limitation: consistently wrong
item OCR can win the disagreement fallback (11.00 instead of a correct ledger
amount of 12.00). That test passing means the limitation is reproduced, not that
the model result is correct. No live API calls were made in this follow-up;
the real API results above predate this small payment-selection change.

## Final submission verification

After the payment-selection fix, the final `hw1.py` completed **three independent
real API runs** on all seven public receipts. Every run produced:

| Run | Actual paid | Without discounts | CSV correctness |
| --- | --- | --- | --- |
| 1, project directory | HK$1974.30 | HK$2348.20 | Both correct |
| 2, freshly cloned worktree with final files applied | HK$1974.30 | HK$2348.20 | Both correct |
| 3, same worktree, new process and model calls | HK$1974.30 | HK$2348.20 | Both correct |

Run 1 recovered from API timeouts and used stable ledger readings for receipt4.
Run 2 retried one unresolved receipt. Run 3 needed no additional reading round.
All **34 offline tests** also passed in the freshly cloned worktree. The clone
was obtained using Dulwich because the system Git executable could not run.
Final local files were applied to that clone before testing; these results do
not mean the final files have been pushed to GitHub. The two-function template
restriction was checked again after the final API runs and passed.

The revised Task 2 reflection is included in the repository and linked from
README. It distinguishes the recent model launch from older background sources,
attributes the vendor's evaluation claims, removes an unsupported direct quote
and sector comparison, and explains concrete changes to career plans.

## Remaining submission and accuracy limits

Passing public tests does not establish private-set accuracy. Stable repeated
readings can still be wrong. If extraction fails on every attempt, the program
warns and uses a partial numeric total (zero contribution for an unresolved
amount) so the normal runner can still write CSV; that result is not a verified
answer. Empty folders retain the teacher runner's explicit error behavior.
No claim is made that the private grading data or its three independent runs
have been tested.
