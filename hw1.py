#!/usr/bin/env python3
"""FTEC5660 HW1 student starter: build a chain for supermarket receipts."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import mimetypes
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


QUERY_1 = "How much money did I spend in total for these bills?"
QUERY_2 = "How much would I have had to pay without the discount?"
QUERIES = (QUERY_1, QUERY_2)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
DUMMY_RESPONSE = "please design your chain to answer these two queries."


def load_env_file(path: Path = Path(".env")) -> None:
    """Load the simple KEY=VALUE entries used by this homework."""
    if not path.is_file():
        return
    import os

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def image_files(folder: Path) -> list[Path]:
    """Return supported images directly inside *folder*, sorted by filename."""
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def image_data_url(path: Path) -> str:
    """Encode a local image in the format accepted by a multimodal prompt."""
    mime_type, _ = mimetypes.guess_type(path.name)
    mime_type = mime_type or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def build_chain() -> Any:
    """Create two primary readers and a final evidence-review chain once.

        ChatPromptTemplate -> ChatDeepSeek (vision) -> JsonOutputParser

    Reader A transcribes SUBTOTAL, the payment line and the discount lines.
    Reader B transcribes only the product lines at full price. They never see
    each other's output, so the two routes to "what it would have cost without
    the discount" can be reconciled afterwards. Review re-extracts the printed
    evidence for unresolved receipts without seeing prior candidate answers.
    """
    ### YOUR CODE HERE
    MODEL_NAME = "deepseek-v4-flash-vision-exp"

    # --- Reader A: the totals line and every discount line -----------------------
    LEDGER_PROMPT = """\
    You read Hong Kong supermarket receipts. Return ONLY a raw JSON object with
    exactly these keys -- no markdown fences, no commentary:

{{"subtotal": <number or null>, "final_paid": <number or null>,
 "rounding": <signed number or null>, "cash_tendered": <number or null>,
 "change": <number or null>, "discounts": [<number>, ...]}}

    * "subtotal"    The SUBTOTAL (or TOTAL) line: the items after every discount has
                    been deducted, but BEFORE the ROUNDING adjustment.
    * "final_paid"  The amount actually paid, AFTER the ROUNDING adjustment, on the
                    payment line: OCTOPUS, VISA, MASTER, UNIONPAY, ALIPAY,
                    WECHAT, AMOUNT DUE, TOTAL DUE.
    * "discounts"   Every discount line as a POSITIVE number: "Buy N Save $X",
                    "% OFF", DISCOUNT, PROMOTION, COUPON, VOUCHER, MEMBER / VIP
                    PRICE, APP UPGRADE, REBATE, SAVINGS, 折扣, 優惠, 會員價.
                    - NEVER include the ROUNDING line.
                    - Never merge two discount lines into one number.
                    - Return [] when the receipt has no discount line.

    Discount lines are printed small and indented: read each amount digit by digit,
    because 5/6, 3/8 and 0/8 are easily confused on faded thermal paper. Ignore the
    product prices entirely -- another reader handles those. Never compute a value
    that is not printed; transcribe exactly as shown, to 2 decimals.
    Transcribe ROUNDING with its printed sign; use 0 only when clearly absent,
    and null when unreadable. CASH may be tendered money, not the amount spent.
    If CASH and CHANGE are present, put them in cash_tendered and change; use
    final_paid only for an explicitly printed net total after rounding.
    Use null for unknown fields, including discounts if not fully readable.
    Use [] only when there are definitely no discounts. Do not duplicate a
    discount in both item-level lines and a total-savings summary. A percentage
    is not a monetary discount: transcribe the associated dollar amount.
    Output raw JSON and nothing else.\
    """

    # Reader B independently transcribes product lines at full price.
    ITEMS_PROMPT = """\
    You read Hong Kong supermarket receipts. Return ONLY a raw JSON object with
    exactly this key -- no markdown fences, no commentary:

    {{"item_amounts": [<number>, ...]}}

    List the printed FULL price of every product line, before any discount is
    applied. When a product spans two lines and the price sits on its "QTY: n"
    line, that amount is the line total: take it once and never also take a unit
    price. Include $0.00 lines and service charges such as "PLASTIC BAG CHARGIN".

    Ignore every discount line, and ignore SUBTOTAL, ROUNDING and the payment
    lines -- another reader handles those. Never compute a value that is not
    printed; transcribe exactly as shown, to 2 decimals.
    Output raw JSON and nothing else.\
    """



    from langchain_core.output_parsers import JsonOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_deepseek import ChatDeepSeek

    llm = ChatDeepSeek(
        model=MODEL_NAME,
        temperature=0,
        max_retries=0,
        timeout=90,
    )

    def reader(system_prompt: str) -> Any:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                (
                    "human",
                    [
                        {"type": "image_url", "image_url": {"url": "{image_url}"}},
                        {"type": "text", "text": "Read this receipt. Raw JSON only."},
                    ],
                ),
            ]
        )
        return prompt | llm | JsonOutputParser()

    REVIEW_PROMPT = """\
    Re-examine this supermarket receipt from the printed evidence only.
    Return ONLY JSON with these fields:
    {{"subtotal": null, "final_paid": null, "rounding": null,
      "cash_tendered": null, "change": null, "discounts": null,
      "item_amounts": null}}
    Replace null with a printed amount, or a list of printed amounts for the
    last two fields, only when readable. Never invent an amount or calculate a
    total. Focus first on SUBTOTAL before ROUNDING and the net total after it.
    ROUNDING is signed; use 0 only if clearly absent. CASH may be tendered cash:
    transcribe CASH and CHANGE separately, never treat tendered cash as net paid.
    Next inspect each promotion/coupon/discount line in order, including small
    indented lines. discounts lists monetary amounts, not percentages. Exclude
    ROUNDING, change, and duplicate total-savings summaries. Use [] only when
    there are definitely no discounts; otherwise leave an unreadable list null.
    Finally, if readable, item_amounts lists full-price product line totals once
    each, including bags, excluding discounts and payment totals. A quantity-line
    amount is already a line total, not a unit price. Do not adjust any digit to
    make arithmetic balance. Check faded 3/8 and 5/6 digits directly on the image.
    Independent software will check the arithmetic. Prefer null to guessing.
    """
    return {"ledger": reader(LEDGER_PROMPT), "items": reader(ITEMS_PROMPT),
            "review": reader(REVIEW_PROMPT)}


def answer_queries(chain: Any, images: list[Path]) -> dict[str, Any]:
    """Read every receipt with both readers, reconcile them, then aggregate.

    Query 1 = sum over receipts of the amount paid after ROUNDING.
    Query 2 = sum over receipts of SUBTOTAL plus its discount lines added back,
              cross-checked against the full-price item lines.

    A receipt is settled as soon as the two independent readers land on the same
    amount; only receipts with unresolved fields or disagreement are read again.
    Failed readings are retried within a finite request and overall time budget.
    Every receipt gets an evidence audit and at most one recovery retry.
    """
    ### YOUR CODE HERE
    MAX_CONCURRENCY = 8
    MAX_ROUNDS = 4
    SECONDS_PER_IMAGE = 90
    MIN_TIME_BUDGET = 180
    ROUNDING_TOLERANCE = Decimal("0.10")
    AGREEMENT_TOLERANCE = Decimal("0.005")

    def _to_decimal(value: Any) -> Decimal | None:
        """Best-effort conversion of an LLM-supplied number to Decimal."""
        if value is None or isinstance(value, bool):
            return None
        try:
            text = re.sub(r"^(?:HK\$|HKD|\$)\s*", "", str(value).strip(), flags=re.I)
            if not re.fullmatch(r"[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?", text):
                return None
            number = Decimal(text.replace(",", ""))
            return number if number.is_finite() and abs(number) < Decimal("1e12") else None
        except (InvalidOperation, ValueError):
            return None


    def _sum_amounts(raw: Any, absolute: bool = False) -> Decimal | None:
        """Sum a list that may hold bare numbers or {"amount": n} objects."""
        if not isinstance(raw, list):
            return None
        total = Decimal("0")
        for entry in raw:
            value = entry.get("amount") if isinstance(entry, dict) else entry
            number = _to_decimal(value)
            if number is None:
                return None
            total += abs(number) if absolute else number
        return total


    def _read_ledger(raw: Any) -> dict[str, Decimal | None] | None:
        """Reader A -> {paid, without_discount} using SUBTOTAL + discounts added back."""
        if isinstance(raw, BaseException) or not isinstance(raw, dict):
            return None
        subtotal = _to_decimal(raw.get("subtotal"))
        paid = _to_decimal(raw.get("final_paid"))
        rounding = _to_decimal(raw.get("rounding"))
        cash = _to_decimal(raw.get("cash_tendered"))
        change = _to_decimal(raw.get("change"))
        if cash is not None and change is not None:
            if not Decimal("0") <= change <= cash:
                return None
            net = cash - change
            if paid is not None and paid != net:
                return None
            paid = net
        if rounding is not None:
            if paid is None and subtotal is not None:
                paid = subtotal + rounding
            if subtotal is None and paid is not None:
                subtotal = paid - rounding
        if subtotal is not None and paid is not None:
            if rounding is not None and subtotal + rounding != paid:
                return None
            if rounding is None and abs(subtotal - paid) > ROUNDING_TOLERANCE:
                return None
        if any(x is not None and x < 0 for x in (subtotal, paid)):
            return None
        discounts = _sum_amounts(raw.get("discounts"), absolute=True)
        without = subtotal + discounts if subtotal is not None and discounts is not None else None
        return {"paid": paid, "without_discount": without}


    def _read_items(raw: Any) -> Decimal | None:
        """Reader B -> the same amount, reached by summing the full-price item lines."""
        if isinstance(raw, BaseException) or not isinstance(raw, dict):
            return None
        total = _sum_amounts(raw.get("item_amounts"))
        return total if total is not None and total >= 0 else None


    def _mode(values: list[Decimal]) -> Decimal:
        """Most frequent value; ties broken towards the median."""
        midpoint = sorted(values)[len(values) // 2]
        return min(values, key=lambda v: (-values.count(v), abs(v - midpoint)))


    def _settle(
        items: list[Decimal],
        ledger: list[Decimal],
        agreed: list[Decimal],
        name: str,
    ) -> Decimal | None:
        """Decide one receipt's amount without discounts.

        After the final evidence review, unresolved cases use ledger votes first:
        SUBTOTAL plus discounts is the assignment's definition. Repeated item OCR
        alone does not justify overruling a usable ledger. This remains a fallback,
        not proof of correct recognition.
        """
        if agreed:
            return _mode(agreed)

        if ledger:
            choice, why = _mode(ledger), "unresolved; using SUBTOTAL plus discounts"
        elif items:
            choice, why = _mode(items), "ledger unavailable; using item fallback"
        else:
            return None

        print(f"[warn] readers disagreed on {name}; took {choice} ({why})")
        return choice



    import time
    import queue
    import threading

    ledger_chain, items_chain = chain["ledger"], chain["items"]
    review_chain = chain.get("review")
    inputs = []
    for path in images:
        try:
            inputs.append({"image_url": image_data_url(path)})
        except OSError:
            print(f"[warn] cannot read image: {path.name}")
            inputs.append(None)
    deadline = time.monotonic() + max(MIN_TIME_BUDGET, SECONDS_PER_IMAGE * len(images))
    # Reserve time for final recovery and one retry per unresolved image, even if a
    # main reader stalls. Review shares the original overall budget.
    reserve = min(180 * max(1, (len(images) + 7) // 8),
                  max(MIN_TIME_BUDGET, SECONDS_PER_IMAGE * len(images)) / 2)
    reading_deadline = deadline - reserve if review_chain is not None else deadline

    paid_votes: list[list[Decimal]] = [[] for _ in images]
    reconciled_paid_votes: list[list[Decimal]] = [[] for _ in images]
    ledger_votes: list[list[Decimal]] = [[] for _ in images]
    item_votes: list[list[Decimal]] = [[] for _ in images]
    agreed: list[list[Decimal]] = [[] for _ in images]

    def run(sub_chain: Any, indexes: list[int], stop_at: float) -> list[Any]:
        # Own daemon workers avoid executor shutdown waiting on a stuck request.
        mailbox = queue.Queue()
        slots = threading.Semaphore(MAX_CONCURRENCY)
        def worker(slot, index):
            try:
                with slots:
                    result = sub_chain.invoke(inputs[index]) if time.monotonic() < stop_at else None
            except Exception as exc:
                print(f"[warn] receipt extraction failed ({type(exc).__name__}); will retry if budget permits")
                result = None
            mailbox.put((slot, result))
        results = [None] * len(indexes)
        launched = 0
        for slot, index in enumerate(indexes):
            if time.monotonic() >= stop_at:
                break
            threading.Thread(target=worker, args=(slot, index), daemon=True).start()
            launched += 1
        for _ in range(launched):
            try:
                # Preserve completed results even if the deadline was just reached.
                slot, value = mailbox.get_nowait()
            except queue.Empty:
                remaining = stop_at - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    slot, value = mailbox.get(timeout=remaining)
                except queue.Empty:
                    print("[warn] reading stage deadline reached")
                    break
            results[slot] = value
        return results

    pending = [i for i, value in enumerate(inputs) if value is not None]
    for round_number in range(MAX_ROUNDS):
        if not pending:
            break
        if time.monotonic() >= reading_deadline:
            # Better a majority-vote answer than a run that never finishes:
            # results.csv must always be written.
            print("[warn] time budget reached; settling with the readings so far")
            break
        ledger_out = run(ledger_chain, pending, reading_deadline)
        items_out = run(items_chain, pending, reading_deadline)

        for slot, index in enumerate(pending):
            ledger = _read_ledger(ledger_out[slot])
            items = _read_items(items_out[slot])
            if items is not None:
                item_votes[index].append(items)
            if ledger is not None:
                if ledger["paid"] is not None:
                    paid_votes[index].append(ledger["paid"])
                if ledger["without_discount"] is not None:
                    ledger_votes[index].append(ledger["without_discount"])
                if items is not None and ledger["without_discount"] is not None and abs(ledger["without_discount"] - items) <= AGREEMENT_TOLERANCE:
                    agreed[index].append(ledger["without_discount"])
                    if ledger["paid"] is not None:
                        reconciled_paid_votes[index].append(ledger["paid"])

        pending = [i for i in pending if not agreed[i] or not paid_votes[i]]
        if not pending:
            break
        if round_number + 1 < MAX_ROUNDS:
            print(f"[info] re-reading {len(pending)} unreconciled receipt(s)")

    reviewed_paid = {}
    reviewed_without = {}
    audit_candidates = {}
    review_pending = [i for i, value in enumerate(inputs) if value is not None] if review_chain is not None else []
    for review_round in range(2):
        if not review_pending or time.monotonic() >= deadline:
            break
        print(f"[info] evidence review {review_round + 1} for {len(review_pending)} receipt(s)")
        retry_review = []
        for index, raw in zip(review_pending, run(review_chain, review_pending, deadline)):
            ledger = _read_ledger(raw)
            if ledger is None:
                retry_review.append(index)
                continue
            items = _read_items(raw)
            without, paid = ledger["without_discount"], ledger["paid"]
            internally_agreed = without is not None and items is not None and without == items
            prior_amounts = ledger_votes[index] + item_votes[index]
            print(f"[info] audit {images[index].name}: paid={paid}, ledger={without}, items={items}")
            if agreed[index] and internally_agreed and without != _mode(agreed[index]):
                # One audit must not replace two agreeing primary readers.
                # Require the same internally checked correction a second time.
                if audit_candidates.get(index) == (paid, without):
                    reviewed_without[index] = without
                    if paid is not None:
                        reviewed_paid[index] = paid
                else:
                    audit_candidates[index] = (paid, without)
                    retry_review.append(index)
                continue
            if without is None and items is not None and not prior_amounts and not agreed[index]:
                reviewed_without[index] = items
                print(f"[warn] recovered {images[index].name} from item-only review")
            if not agreed[index] and without is not None:
                # A third conflicting guess cannot overrule existing evidence.
                if internally_agreed or without in prior_amounts or not prior_amounts:
                    reviewed_without[index] = without
                    if not internally_agreed and not prior_amounts:
                        print(f"[warn] recovered {images[index].name} from a single ledger review")
                else:
                    print(f"[warn] final review conflicts with prior amounts for {images[index].name}")
            if paid is not None and (internally_agreed or paid in paid_votes[index] or not paid_votes[index]):
                reviewed_paid[index] = paid
            if ((without is None and items is None and not agreed[index] and index not in reviewed_without)
                    or (paid is None and not paid_votes[index] and index not in reviewed_paid)):
                retry_review.append(index)
        review_pending = retry_review

    total_paid = Decimal("0")
    total_without = Decimal("0")
    for index, path in enumerate(images):
        if index in reviewed_paid:
            total_paid += reviewed_paid[index]
        elif not paid_votes[index]:
            print(f"[warn] no usable reading for {path.name}; counted as 0.00")
        else:
            # Prefer payment from a reading whose discount total was corroborated
            # in the same round, rather than an earlier unresolved extraction.
            total_paid += _mode(reconciled_paid_votes[index] or paid_votes[index])
        amount = reviewed_without.get(index)
        if amount is None:
            amount = _settle(item_votes[index], ledger_votes[index], agreed[index], path.name)
        if amount is None:
            print(f"[warn] no amount recovered for {path.name}; counted as 0.00")
            continue
        total_without += amount
        print(f"[info] selected {path.name}: without_discount={amount}")

    cents = Decimal("0.01")
    return {
        QUERY_1: f"HK${total_paid.quantize(cents)}",
        QUERY_2: f"HK${total_without.quantize(cents)}",
    }


# Everything below is provided runner/scoring code. No edits are needed.

_MONEY_RE = re.compile(
    r"(?<![\w.])(?:HK\$|\$)?\s*(-?\d[\d,]*(?:\.\d+)?)(?![\w.])",
    re.IGNORECASE,
)


def response_text(value: Any) -> str:
    """Convert common LangChain response shapes to text for results.csv."""
    content = getattr(value, "content", value)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts).strip()
    if isinstance(content, (dict, list)):
        return json.dumps(content, ensure_ascii=False)
    return str(content).strip()


def parse_single_amount(text: str) -> Decimal | None:
    """Accept a response only when it contains exactly one numeric amount."""
    matches = _MONEY_RE.findall(text)
    if len(matches) != 1:
        return None
    try:
        return Decimal(matches[0].replace(",", "")).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def read_ground_truth(folder: Path) -> dict[str, Decimal]:
    """Read aggregate answers from the test folder."""
    path = folder / "ground_truth.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    answers = data.get("answers", data)
    return {query: Decimal(str(answers[query])).quantize(Decimal("0.01")) for query in QUERIES}


def correctness_text(response: str, expected: Decimal | None) -> str:
    """Return `correct`, or an expected/predicted mismatch explanation."""
    if expected is None:
        return "not graded: ground_truth.json is missing"
    predicted = parse_single_amount(response)
    if predicted == expected:
        return "correct"
    shown = f"HK${predicted:.2f}" if predicted is not None else repr(response)
    return f"incorrect: expected HK${expected:.2f}, predicted {shown}"


def write_results(responses: dict[str, Any], truth: dict[str, Decimal]) -> Path:
    """Write the required three-column results.csv file."""
    output = Path("results.csv")
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["query", "model_response", "correctness"])
        for query in QUERIES:
            text = response_text(responses.get(query, "<missing response>"))
            writer.writerow([query, text, correctness_text(text, truth.get(query))])
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run FTEC5660 HW1 on receipt images")
    parser.add_argument(
        "--image-folder",
        required=True,
        type=Path,
        help="folder containing supermarket receipt images",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.image_folder.is_dir():
        raise SystemExit(f"not a folder: {args.image_folder}")

    images = image_files(args.image_folder)
    if not images:
        raise SystemExit(f"no supported images found in {args.image_folder}")

    load_env_file()
    chain = build_chain()
    responses = answer_queries(chain, images)
    if not isinstance(responses, dict):
        raise TypeError("answer_queries() must return a dictionary")

    output = write_results(responses, read_ground_truth(args.image_folder))
    print(f"Processed {len(images)} receipt(s). Wrote {output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
