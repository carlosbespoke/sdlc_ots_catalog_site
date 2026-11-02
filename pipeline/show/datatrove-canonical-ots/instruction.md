The repository at `/workdir` is DataTrove, a library to process, filter and deduplicate text data at
large scale: Documents and pipelines of blocks, readers and writers for JSONL, CSV, Parquet and Arrow
files on DataFolders, quality and URL filters, text formatters, exact, MinHash, sentence and Bloom
filter deduplication, summary statistics and their merging, and the local pipeline executor with its
logging folder, task completion tracking and statistics.

Fix all implementation drift from the documentation in this repository.
Everything in scope is the document-processing core of the datatrove package under src/datatrove/: data.py, io.py, pipeline/base.py, executor/base.py, executor/local.py and tools/merge_stats.py; every module under pipeline/formatters/; the modules under pipeline/filters/ except fasttext_filter.py, language_filter.py and unigram_log_probs.py; the modules under pipeline/readers/ except huggingface.py and warc.py; the modules under pipeline/writers/ except huggingface.py; the modules under pipeline/dedup/ except exact_substrings.py; the modules under pipeline/stats/ except __init__.py, lang_stats.py, perplexity_stats.py and token_stats.py; and utils/_import_utils.py, utils/batching.py, utils/binaryio.py, utils/hashing.py, utils/hashes/sha1.py, utils/hashes/xxhash.py, utils/logging.py, utils/stats.py, utils/text.py and utils/word_tokenizers.py; together with README.md and the module, class and function docstrings of the in-scope modules.

Where the code and the documentation disagree about runtime behavior, the documentation is the
authority: change the implementation so that it does what the documentation says, and do not edit
or delete documentation to make a disagreement go away. The documentation is README.md and the
in-package docstrings, including their examples; in-package code comments are only supporting
evidence, and when a comment conflicts with the documentation, follow the documentation.

The environment runs Python 3.12 with numpy, fsspec, huggingface_hub, pyarrow, orjson, regex, ftfy,
spaCy (blank language pipelines only, no trained models), tldextract, xxhash, tokenizers and pytest,
and has no network access, so no model, tokenizer, word list or other asset can be downloaded and no
S3, Hugging Face Hub, Slurm or Ray service is reachable; datatrove is imported from
`/workdir/src`. Keep the public API stable and keep every behavior that already matches its
documentation working exactly as it does now.
