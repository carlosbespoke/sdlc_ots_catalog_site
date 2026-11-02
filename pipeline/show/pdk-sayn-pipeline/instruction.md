We moved the store orders feed to the POS vendor's change log, where order numbers are only unique within a store. A copy of their database is at /data/pos_changes.sqlite and our sayn project is in /data/orders_project.

Since then `sayn run` leaves orders with some orders more than once and without the columns the vendor added later, and order_history picks up extra rows when it runs again.

orders is a copy task with incremental_key and delete_key. It should hold every order (every delete_key value) once, with the values from its row with the latest incremental_key. delete_key should take a list of columns in copy tasks and in incremental autosql tasks (task YAML or the SQL file's config()), and a single column name must keep working. If a delete_key column isn't in the source table, the copy must fail without creating or changing the destination.

order_history, an append copy of the same log, should hold the vendor's log row for row, each with its load time, with or without max_merge_rows.

When the source gains columns and a copy doesn't list its columns, the next run should add them, with NULL for rows it doesn't reload. Running again with nothing new must change nothing, and incremental runs after each new batch must end with the same tables as one full load (-f).

Could you find and fix this? The existing tests in /app/tests have to keep passing. There's no network, and SQLite is the only database here.
