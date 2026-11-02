We refresh the German bank data in /app from the Bundesbank's bank code file, but our build machine has no network. Running `python -m scripts.get_bank_registry_de FILE` from /app should rebuild the German registry from a local copy of that file. Our copies of the June and September files are in /data/bundesbank/. Don't commit a registry built from them; the shipped data stays as it is.

After an import, the banks in the file should resolve through `IBAN.bank_name`, `IBAN.bank_short_name`, `IBAN.bic` and `BIC.from_bank_code("DE", code)` exactly as the file lists them. A bank listed without a BIC keeps its names, its `bic` is None and `from_bank_code` raises `InvalidBankCode`.

Some banks merged and the files delete their codes, but IBANs with those codes are still around. They should resolve to the bank that took the code over, and `IBAN.generate("DE", code, account)` should use that bank's code. A deleted code that no current bank took over is unknown, like any code not in the registry. `BIC.exists` and `BIC.domestic_bank_codes` should only see records the latest file keeps, and `IBAN.random("DE")` must never produce a deleted code. Codes deleted by an earlier file have to keep resolving after the next import, and importing a file twice gives the same result as once.

If a line is cut short or its bank code isn't eight digits, the import should exit non-zero and leave the registry as it was.

`uv run poe check` and the existing tests have to pass, and add a changelog entry. Everything else is installed.
