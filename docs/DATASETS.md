# Datasets & Knowledge Base

This repository contains tools and processed extracts used for clinical knowledge, medication metadata, and vector embeddings for retrieval-augmented generation (RAG).

- `knowledge_base/` contains:
  - `drugbank_loader.py` — parse and normalize DrugBank XML into internal tables
  - `rxnorm_client.py` — helpers to resolve RxNorm identifiers and mappings
  - `sider_loader.py` — parse SIDER adverse event information
  - `vector_store.py` — thin wrapper around Chroma/SQLite vector indexes used by the RAG pipeline

`data/drugs/` contains processed extracts and cached files derived from DrugBank, RxNorm, and SIDER (large raw files are kept out of git).
`data/guidelines/` contains curated clinical guideline snippets used to augment LLM responses.
`data/embeddings/` contains local vector store files used for development retrieval (Chroma/SQLite).
`data/synthetic/` contains synthetic patient and adherence datasets safe for testing.

How to regenerate data

1. Place raw source files in a secure local folder (outside git) and obey licensing terms.
2. Run parsing scripts to normalize sources into the internal format:

```bash
python scripts/parse_drugbank.py --input /path/to/drugbank.xml --output data/drugs/drugbank
python scripts/parse_sider.py --input /path/to/sider.tsv --output data/drugs/sider
```

3. Rebuild embeddings for retrieval:

```bash
python scripts/index_embeddings.py --source data/guidelines --index data/embeddings
```

Licensing and compliance

- Verify licensing for DrugBank and other curated datasets before downloading or redistributing.
- The repository includes small processed extracts for development only when permitted. Keep large or restricted raw files in external storage (S3, secure drives).
- Do not commit PHI. Use `data/synthetic/` for testing and demos.

Notes and recommendations

- `data/embeddings/` is convenient for local development but should be rebuilt for production with the canonical dataset and embedding model used in deployment.
- For production, consider a managed vector database, versioned blob storage for raw datasets, and strict access controls.
- If you reuse or redistribute any clinical dataset, include proper citation and licensing information in project documentation.
