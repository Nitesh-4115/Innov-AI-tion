# RxNorm Data

This folder is **optional**. The application uses the RxNorm REST API (`knowledge_base/rxnorm_client.py`).

## API Endpoint (used by default):
https://rxnav.nlm.nih.gov/REST

## If you want local RxNorm data:

1. Go to https://www.nlm.nih.gov/research/umls/rxnorm/docs/rxnormfiles.html
2. Download "Current Prescribable Content" (no license required)
3. Extract RRF files here

## Expected files (optional):
- `RXNCONSO.RRF` - Drug concepts and names
- `RXNREL.RRF` - Drug relationships
- `RXNSAT.RRF` - Drug attributes

## Note:
The app works without these files using the REST API.
