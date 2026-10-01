# Conversational Sales Analytics Agent

Local terminal agent for multi-turn analytics over the [Olist Brazilian e-commerce](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) dataset. Answers come from allowlisted SQL only; the model picks the query, not the numbers.

## Walkthrough

[Five-minute project walkthrough](Avinash-submission.mp4)

## Setup

1. **Python 3.11** — create a virtual environment and install dependencies:

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Kaggle** — configure credentials outside this repo (for example `~/.kaggle/kaggle.json` with your Kaggle API key).

3. **Download the dataset** into `data/`:

   ```bash
   mkdir -p data && kaggle datasets download -d olistbr/brazilian-ecommerce -p data --unzip
   ```

4. **Ingest** CSVs into SQLite:

   ```bash
   python -m sales_agent.ingest
   ```

   This writes `data/olist.sqlite`.

5. **Chat** — start LM Studio (or another OpenAI-compatible server) with model `google/gemma-4-e4b`. Default API base URL is `http://127.0.0.1:1234/v1` (override with `LM_API_BASE` if needed). Set a bearer token and run the REPL:

   ```bash
   export LM_API_TOKEN=your_token_here
   python -m sales_agent.chat
   ```

   Optional: `LM_MODEL` defaults to `google/gemma-4-e4b`.

## Tests and evaluation

- **Deterministic tests** (fixture DB, no LM Studio):

  ```bash
  python -m pytest
  ```

- **Live eval** (~20 questions against `data/olist.sqlite` and your local model):

  ```bash
  python -m eval.run_eval
  ```

  Results are written to `eval/results.md`.

## Repository notes

`data/` and `.env` are gitignored. Do not commit the Olist CSVs, `data/olist.sqlite`, or API tokens.
