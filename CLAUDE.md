# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A minimal Flask chatbot web app (v0.1) that answers chat messages via the OpenAI API and accepts Excel/PDF file uploads for processing. The entire application lives in `app.py` — there is no package structure, build system, linter, or test framework.

## Running the app

```bash
pip install -r requirements.txt
pip install openai            # used by app.py but missing from requirements.txt
python app.py                 # serves on http://127.0.0.1:8080 with debug=True
```

One-off scripts:

```bash
python init_db.py             # (re)creates chatbot.db with the conversations table
python test_upload.py         # manual smoke test of the OpenAI API (not a pytest test)
```

There is no automated test suite — `test_upload.py` is a standalone script that requires a real API key to run.

## Architecture

- `app.py` — the whole application:
  - `GET /` renders `templates/index.html`. **Note:** no `templates/` directory is committed, so this route will fail until the template is added.
  - `POST /chat` — JSON `{"message": ...}` in, `{"response": ...}` out. Calls `generate_response()`, which uses the OpenAI ChatCompletion API (`gpt-3.5-turbo`) with streaming, accumulating chunks into a single string before returning (i.e., the HTTP response itself is not streamed).
  - `POST /upload` — multipart file upload saved to `uploads/` (auto-created at cwd). `.xlsx`/`.xls` files go through `process_excel()` + `validate_engineering_rules()` (checks that the 4th column, "overhang", is within 0.5–3.0); `.pdf` files go through `process_pdf()` (PyPDF2 text extraction).
- `init_db.py` / `chatbot.db` — SQLite database with a `conversations` table (`user_message`, `bot_response`, `timestamp`). **`app.py` does not currently read or write this database**; conversation persistence is set up but not wired in.
- `chatbot_v01/` — empty directory, currently unused.

## Key caveats and conventions

- The code uses the **legacy OpenAI Python SDK (< 1.0)** interface: `openai.api_key`, `openai.ChatCompletion.create`, and `openai.error.*` exception classes. Installing a modern `openai` (>= 1.0) package will break `app.py` and `test_upload.py` unless the code is migrated. Keep API-call style consistent with whichever SDK version is actually installed.
- The OpenAI API key is read from the **`OPENAI_API_KEY` environment variable** in both `app.py` and `test_upload.py`. Set it before running; never hardcode or commit a key.
- Uploaded filenames are used as-is when saving to `uploads/` (no sanitization such as `secure_filename`); be aware of this if modifying the upload path handling.
- `chatbot.db` is committed to the repository, so schema changes via `init_db.py` produce a binary diff.
