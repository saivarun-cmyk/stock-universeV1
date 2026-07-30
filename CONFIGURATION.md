# Universe Configuration

All stocks and indexes are configured in:

`config/universe.yaml`

## Add a stock

Add an entry under `stocks`:

```yaml
- sector: Banking
  stock: My New Bank
  ticker: EXAMPLE.NS
```

Save the file and restart Streamlit.

## Add an index

Add an entry under `indexes`:

```yaml
- sector: My Sector
  stock: My Index
  ticker: ^EXAMPLE
```

Save and restart.

### No code changes

You do **not** need to edit:
- `app.py`
- `services/market.py`
- `services/universe.py`
- UI files

The application automatically reads the configuration at startup.

### Important

The `ticker` must be a valid Yahoo Finance symbol. If Yahoo Finance does not
provide data for a symbol, the scanner will skip that symbol and report it as
unavailable rather than crashing the entire application.

The application does not use a price/amount filter.
