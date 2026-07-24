# Sample Questions and Expected Results

This file tracks test questions to evaluate the Research Agent's performance across different reasoning modes.

## 1. Directly Answerable Questions
- **Q:** "What is the attention mechanism in transformers?"
  - **Expected:** Answer explaining self-attention, queries/keys/values, cited to `ai_transformers_overview.md`.
- **Q:** "What temperature increase does the climate report project by 2100?"
  - **Expected:** Answer stating 1.5°C to 4.5°C, citing `climate_change_report.txt`.
- **Q:** "What does PEP 8 recommend for line length?"
  - **Expected:** Answer stating 79 characters for code, 72 for docstrings, citing `python_best_practices.md`.

## 2. Synthesis Required
- **Q:** "How do both AI advancements and climate change relate to future energy demands?"
  - **Expected:** Answer synthesizing the energy demands of large AI models (from the climate report) and the shift to renewable energy, citing `climate_change_report.txt` and potentially `ai_transformers_overview.md`.
- **Q:** "Compare the testing practices recommended for Python with the evaluation approaches used for ML models."
  - **Expected:** Answer outlining pytest, unit/integration tests (from Python docs), and noting lack of specific ML evaluation details if not in corpus.

## 3. Conflicting Sources
- **Q:** "Is coffee beneficial or harmful for cardiovascular health?"
  - **Expected:** Answer presenting both Study A (beneficial, reduces heart disease) and Study B (harmful, increases PVCs), citing `conflicting_nutrition_studies.md` for both claims.

## 4. Unanswerable (Abstention)
- **Q:** "What is the GDP of Mars?"
  - **Expected:** Explicit ABSTAIN response.
- **Q:** "Who won the 2030 World Cup?"
  - **Expected:** Explicit ABSTAIN response.

## 5. Web Search Required (If Enabled)
- **Q:** "What is the current price of Bitcoin?"
  - **Expected:** Answer retrieved from web search, cited as `[Source: Web Result]`.
- **Q:** "What was the latest news about SpaceX Starship?"
  - **Expected:** Answer retrieved from web search, cited as `[Source: Web Result]`.
