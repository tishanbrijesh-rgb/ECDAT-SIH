# Phase 4 Frozen Evaluation Corpora

Frozen set of source files for measuring detector accuracy.

## Structure

Each source file contains real (positive) or absence-of (negative) cryptographic operations.
Alias and wrapper subdirectories test import-shadowing and indirection handling.

## Usage

Run the evaluator:

```bash
ECC_GATEGUARD=off python scripts/evaluate_corpora.py
```

## Corpus Summary

- **53 total cases**: 41 positive, 12 negative
- **6 languages**: Python, Java, JavaScript, Go, C, C#
