The repository at `/workdir` is AgentScope, a Python framework for building LLM-powered agents and
multi-agent applications. Its retrieval stack turns documents into searchable knowledge: readers parse files
into sections, chunkers split the sections into chunks, embedding models turn the chunks and the queries into
vectors, vector stores keep and search the vectors, and a `KnowledgeBase` ties an embedding model and one
vector-store collection together for inserting, searching, listing and deleting documents.

Fix all implementation drift from the documentation in this part of the repository.
Everything in scope is AgentScope's retrieval and embedding stack: the rag package (src/agentscope/rag/: documents, readers/parsers, chunkers, vector stores and the KnowledgeBase), the embedding package (src/agentscope/embedding/: the embedding model base class, the DashScope, OpenAI, Gemini and Ollama embedding models, embedding responses and the embedding caches), the credential package those models are configured with (src/agentscope/credential/) and the message package whose content blocks they consume (src/agentscope/message/), together with the RAG example page examples/rag/README.md and its example script examples/rag/index_and_search.py, and the module, class and function docstrings of the in-scope modules.

Where the code and the documentation disagree about runtime behavior, the documentation is the
authority: change the implementation so that it does what the documentation says, and do not edit
or delete documentation to make a disagreement go away. The documentation is those pages and the
in-package docstrings, including their examples; in-package code comments are only supporting
evidence, and when a comment conflicts with the documentation, follow the documentation. The rest of
the repository is context, not part of the task.

The environment runs Python 3.11 with AgentScope's development dependencies installed and has no network
access; `agentscope` is imported from `/workdir/src`. No model provider, embedding service or external
database is reachable, and none of the work needs one: embedding models can be replaced by local
subclasses, and the Qdrant vector store runs in memory (`location=":memory:"`). The upstream test suite
is not supplied; write your own checks as needed. Keep the public API stable and keep every behavior
that already matches its documentation working exactly as it does now.
