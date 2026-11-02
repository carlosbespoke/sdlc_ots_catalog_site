Our order feed moved from flat CSV to nested parquet. Every order now has an optional `ship_to` address, a list of `lines` and a list of `vouchers`. A sample of the daily files and the patito models we use for them are in /data/orders/. For each file we run

```python
Order.DataFrame(pl.read_parquet(path)).fill_null(strategy="defaults").validate()
```

and then pass `iter_models()` on to invoicing. The sample files are all good data, but none of them get through this, and on bad files the problems patito reports are not the real ones.

Nested models should get the same treatment patito gives top-level columns. `fill_null(strategy="defaults")` should do for the fields of every address, line and voucher that is there what it does for top-level columns. `validate()` should check each of those like a row of its model and report problems at `<column>.<field>` (for example `lines.qty`) with the same error classes it uses for top-level columns. A null entry in a list counts as one missing value on that list column, unless the list's items are `Optional`. A line number used twice in one order is an error. `iter_models()` should give orders whose `ship_to`, `lines` and `vouchers` hold `Address`, `Line` and `Voucher` objects, or None where the file has none.

This should hold for any nested patito model, not only ours. Please fix it in patito at /app and keep the existing tests in /app/tests passing. There's no network; patito is installed in editable mode in /opt/venv, along with polars and pyarrow.
