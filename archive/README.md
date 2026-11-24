# Archived Deep Learning (ANN) Sentiment Component

This directory preserves the original custom Deep Learning sentiment analysis pipeline from **Sage v1.0** for portfolio and reference purposes.

## What Was Archived

- `models_dl/` — Trained Keras models (`best_sentiment_ann.keras`, `baseline_ann.keras`, `regularized_ann_class_weighted.keras`, `selected_experiment_ann.keras`).
- `data_processed/` — `CountVectorizer` (`count_vectorizer.joblib`), train/validation/test splits, and `dataset_summary.json`.
- `notebooks/` — Exploration, preprocessing, baseline ANN, and regularized ANN training notebooks.
- `results/` & `results_dl/` — Training histories, learning curves, confusion matrices, and evaluation reports.

## Model Summary

- **Architecture:** `Dense(8000 → 128, ReLU) → Dropout(0.30) → Dense(128 → 64, ReLU) → Dropout(0.30) → Dense(64 → 3, Softmax)`
- **Features:** Bag-of-Words (`CountVectorizer(max_features=8000, binary=True, lowercase=False)`)
- **Dataset:** HARD Arabic Hotel Reviews (3 classes: Negative, Neutral, Positive)
- **Test Performance:** `86.9%` accuracy, `0.797` validation macro-F1

## Why Sage v2.0 Moved to Generative AI

The ANN classifier only outputs a 3-class sentiment label for short review text. Transforming Sage into a **Customer Support Intelligence Platform** requires multi-turn conversation understanding, speaker identification, problem categorization, priority assignment, agent evaluation against a rubric, resolution tracking, and evidence-based structured JSON output—capabilities provided by Generative AI models.
