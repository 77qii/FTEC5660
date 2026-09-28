# Submission handoff

The current implementation passes 52 offline tests, three consecutive real
seven-receipt public runs (both queries), and the real review recovery test with
both primary readers deliberately failed. OCR errors and provider failure remain
possible; these results do not guarantee private-set accuracy or full marks.
See `TEST_RESULTS.md` for the current source hash and historical failures.

1. Publish the contents of this directory to the public `77qii/FTEC5660` repository.
   Required root files are `hw1.py`, `requirements.txt`, and `README.md`.
   Include `HW1_Task2_Reflection.md`, which README links to, and the supporting
   tests/report. Do not upload the ZIP as a substitute for these extracted files.
2. Never publish `.env`, API keys, `.venv`, or Python cache directories.
   The supplied ZIP excludes them. Keep the existing `.gitignore`.
3. After publishing, verify the GitHub `main` branch shows the completed functions
   and the filled-in `Homework 1 solution` section. Keep the repository public
   during grading. A final clone of the published commit should be tested with:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   # Set DEEPSEEK_API_KEY privately in the environment or an ignored .env file.
   python hw1.py --image-folder public_test
   cat results.csv
   ```

4. Submit the GitHub username `77qii` on Blackboard. Follow the Task 2 submission
   field there for the reflection; the PDF does not specify a separate location.
   Confirm both requirements before the stated deadline, 29 September at midnight,
   using Blackboard's displayed timezone and deadline if available.

GitHub publishing and Blackboard submission have not been completed by the
assistant. No GitHub write credentials or Blackboard connection were available.
The fresh-clone tests applied local final files to a public clone; they do not
verify a published final commit. Passing the public set does not guarantee full
marks on the unseen private evaluation or on the instructor-assessed reflection.
