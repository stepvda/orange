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
