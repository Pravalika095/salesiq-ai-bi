# Development notes

> Sections marked **[STUDENT TO COMPLETE]** need your own words after you have reviewed, run and understood the code. Everything else records what actually happened while the application was generated.

## 1. AI tools used

- **Claude Code** (Anthropic, model Claude Opus 5.5) running in the Claude desktop app with terminal, file-editing and in-app browser access. It read the assignment document and CSV, wrote the backend, frontend, tests and documentation, ran the test suite and the dev servers, and checked the UI in a browser.
- **[STUDENT TO COMPLETE]** Any other tools you used (ChatGPT, Copilot, Cursor, …) and for what.

## 2. How AI-assisted development was done

1. A detailed specification prompt (stack, endpoints, revenue rules, security and testing requirements) was given to Claude Code together with the assignment `.docx`, the CSV and the job description.
2. The assistant inspected the real CSV first: 51 data rows, `DD-MM-YYYY` dates, one `Returned` row (TXN0033), one zero-quantity row (TXN0034), one blank unit price (TXN0051), no duplicate IDs. The cleaning policy was decided from these findings.
3. It built in layers — schema/loader → analytics → interpreter/API → tests → frontend → docs — and ran each layer before moving on (smoke script of ~30 questions against the real data, then `pytest`, then `npm run build`, then both servers with browser checks).
4. Key numbers were cross-checked independently: a test recomputes total revenue from the raw CSV with Python's `csv` module and `Decimal`, and the Monitor total (₹4,73,000 over 9 rows) was checked by hand.

**[STUDENT TO COMPLETE]** Describe the prompts you wrote, what you accepted, what you changed by hand, and which parts you can explain line by line.

## 3. Problems encountered and how they were debugged

These are the problems that actually occurred during generation:

| Problem | How it showed up | Diagnosis | Fix |
|---|---|---|---|
| **pandas 3.1 blocked by Windows** | `ImportError: DLL load failed while importing writers: An Application Control policy has blocked this file.` on the first run of the loader | Windows Application Control / Smart App Control refused a native extension from the newest pandas wheel; nothing was wrong with the code | Installed `pandas==2.3.3`, which loaded fine, and pinned `pandas>=2.2,<3.0` in `requirements.txt` |
| **Inline Python mangled by PowerShell** | `SyntaxError: '[' was never closed` — the list of strings arrived without quotes | Windows PowerShell 5.1 strips embedded double quotes when passing a here-string to a native program | Wrote the smoke test to a `.py` file and ran it instead of `python -c` |
| **"How did revenue change between two months?" answered with total revenue** | Seen in the smoke-test output | The parser only treated a question as a comparison when it found month names; with none, it fell through to the generic "revenue" rule | Comparison wording + "month(s)" now triggers a clarification asking for two months |
| **The first fix broke "Online vs retail sales"** | Spotted while reviewing the fix: "vs" is a comparison word, so channel questions would have asked for two months | The comparison rule was too broad | The comparison/clarification path now also requires a month name or the word "month(s)"; both cases are covered by tests |
| **Line chart overshoot** | In the browser, the monthly line curved above the May data point | Recharts `type="monotone"` interpolation implies values that do not exist | Switched to `type="linear"` so the line passes exactly through the monthly values |

Other observations: `npm install` warns that Recharts 2.x is no longer actively developed (kept for its stable API), and `vite build` warns that the JS bundle is just over 500 kB (Recharts); neither affects functionality. FastAPI's `TestClient` emits a deprecation warning about `httpx` from Starlette; tests still pass.

**[STUDENT TO COMPLETE]** Add any problems you hit when setting the project up on your own machine and how you solved them.

## 4. What was learned

- Validating an LLM's output against a strict schema, and making the database layer itself read-only, is a sturdier safety boundary than trying to filter generated SQL.
- Reading CSV columns as text and parsing explicitly avoids silent `NaN → 0` conversions that would corrupt revenue.
- Storing money as integer paise makes sums exact and test assertions simple.
- A deterministic fallback parser is worthwhile even with an LLM: it keeps the app usable offline, makes tests deterministic, and gives a safe path when the model fails.

**[STUDENT TO COMPLETE]** Your own takeaways.

## 5. With another day of work

- Exercise the LLM path against a real provider key and record example prompts/responses; add an evaluation set of ~50 questions comparing LLM vs fallback intent accuracy.
- Support combined filters (e.g. product × region × month) and date ranges through the intent schema.
- Add an optional, strictly validated text-to-SQL mode (SQL parser + table/column allowlist + read-only connection) for questions outside the fixed intents.
- Persist question history, add CSV upload with a validation preview, and add CI (GitHub Actions running pytest and the frontend build) plus Playwright UI tests.

## 6. Verification performed

- `python -m pytest` in `backend/`: **76 passed** (one Starlette deprecation warning).
- `python -m app.data_loader` run twice: first run imported 51 rows; second run skipped (idempotent).
- `npm run build` in `frontend/`: succeeded.
- Backend (`uvicorn`, port 8000) and frontend (`vite`, port 5173) started together; Dashboard, Ask AI (example click, Enter-to-submit, unsupported question), Data Quality and Transactions were checked in a browser, plus a 375 px phone-width check with no horizontal overflow. No browser console errors.
- **Not verified:** a live OpenAI or Gemini call (no API key was available; the LLM path is tested with a mocked client).
