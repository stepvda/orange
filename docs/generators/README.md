# Documentation generators

These scripts regenerate reference documents, diagrams, presentations,
screenshots, and videos. Run them from the project root, for example:

```bash
python3 docs/generators/build_diagrams.py
python3 docs/generators/build_reference.py
python3 docs/generators/build_docs.py
```

Generated documentation remains in `docs/`. Hand-written document content and
shared rendering helpers remain in `docs/_build/`.

See [`../DOCUMENTATION.md`](../DOCUMENTATION.md) for the complete build order and
prerequisites.

`build_next_steps.py` is self-contained — it carries the house Word style rather
than importing it, and reads its figures from `data/radar.db` when one is
present, falling back to a recorded snapshot and saying so on the cover.
