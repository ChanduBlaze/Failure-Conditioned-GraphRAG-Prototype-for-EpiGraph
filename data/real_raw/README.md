# Raw Real-Data Inputs

This folder is for raw public surveillance data obtained through downloads or manual placement.

Raw source files should be preserved unchanged so the data lineage remains auditable. Transformations and normalized outputs belong in `data/real_processed/`, not here.

Large raw data files should usually not be committed to the repository unless they are intentionally small, stable fixtures used for development or testing.

Metadata recorded for each raw dataset should eventually include:

- Source URL or API request.
- Retrieval date.
- Dataset version, when available.
- Notes about format, coverage, revisions, and manual acquisition steps.
