# Message Evaluation Set

This is a small golden test set for OJA's message extractor. It is **not training data** and adding more examples does not teach an AI model Pidgin. The AI model/prompt performs the interpretation; these cases check whether it understood each phrase and expose exact failures.

The 12 cases cover Pidgin and English, naira shorthand, fractional quantities, market units, sales, credit, expenses, payments, stock-in, customer aliases, ambiguous names, missing information, and corrections with prior-entry context. Expected values check only the important fields, so the extractor can phrase clarification questions naturally while still being required to ask a non-empty question.

## Validate the test set

```sh
python eval/run_eval.py --validate-only
```

## Run against the configured model

Configure `OPENAI_API_KEY`, then run:

```sh
python eval/run_eval.py --adapter ai_extractor:extract_message
```

The runner prints an overall score, per-category scores, and each failed case with field-level expected/actual differences. It exits non-zero if any case fails. This makes one provider call per test case and may incur API cost. Without a configured key, validate the data with `python eval/run_eval.py --validate-only`; do not report that as a model accuracy score.

## Improving the cases

Start with phrases real merchants use. Ask traders how they describe quantity, units, credit, partial payments, and corrections; add those phrases as cases and agree on the expected interpretation before evaluating. Prefer a few distinct, realistic cases over many synthetic rewrites of the same sentence. Record ambiguous examples as clarification expectations rather than guessing the “right” answer.
