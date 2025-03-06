# ML-Flows

This repo implements a series of Machine Learning [Prefect](https://www.prefect.io/opensource) dataflows.

For example `SHRAG: Structured Heriarchical Retrieval Augmented Generation` using [LlamaIndex](https://www.llamaindex.ai/) as .

> 💡 Once installed, check all the flows with:

```shell
$ python -m flows ls
```

Which should output something like:
```shell
╒════╤═════════════╤═════════════════════════╤══════════════════════════════════════════════════════════════════════════════════════════════╕
│    │ Flow Name   │ From                    │ Flow Parameters                                                                              │
╞════╪═════════════╪═════════════════════════╪══════════════════════════════════════════════════════════════════════════════════════════════╡
│  0 │ playbook-qa │ flows/shrag/__init__.py │ - playbook_json: Path to the playbook JSON file                                              │
│    │             │                         │ - chroma_collection_name: Name of the ChromaDB collection                                    │
│    │             │                         │ - chroma_host: ChromaDB host. Defaults to CHROMA_HOST_DEFAULT.                               │
│    │             │                         │ - chroma_port: ChromaDB port. Defaults to CHROMA_PORT_DEFAULT.                               │
│    │             │                         │ - llm_backend: LLM backend to use. Defaults to LLM_BACKEND_DEFAULT.                          │
│    │             │                         │ - llm_model: LLM model to use. Defaults to LLM_MODEL_DEFAULT.                                │
│    │             │                         │ - embedding_model: Embedding model to use. Defaults to EMBEDDING_MODEL_DEFAULT.              │
│    │             │                         │ - reranker_model: Reranker model to use. Defaults to None.                                   │
│    │             │                         │ - similarity_top_k: Number of top results to retrieve. Defaults to SIMILARITY_TOP_K_DEFAULT. │
│    │             │                         │ - similarity_cutoff: Similarity cutoff for retrieval. Defaults to SIMILARITY_CUTOFF_DEFAULT. │
│    │             │                         │ - meta_filters: Metadata filters for retrieval. Defaults to {}.                              │
╘════╧═════════════╧═════════════════════════╧══════════════════════════════════════════════════════════════════════════════════════════════╛
```

## How to

### Setup

1. **Create a virtual environment:**

   ```shell
   # You'll need python 3.12 or greater
   pdm init
   ```

2. **Install dependencies:**

   ```shell
   pdm sync -G:all
   ```

3. **Auxiliary Services:**
   - Ensure you have a ChromaDB instance running: `inv local-chroma`
   - Ensure you have the Prefect server running: `inv local-prefect`
   - Ensure you have a running Prefect pool: `inv start-worker-pool -p process -n test --overwrite`

### Run

   First update the `.env` file as necessary. (See `.example.env` for guidance)

   Then there are two ways to run flows;


   #### As a python module

   Simply, as you'd run the module's CLI present in each submodule's `__main__.py`:

   ```shell
   source .env; # For ease so we don't need to pass tons of params

   # Running a flow directly from its __main__ entrypoint
   # E.g.: Run a QA-Playbook filtering by document name
   python -m flows.shrag run-playbook-qa \
      data/playbook_sample.json \
      <your-chromaDB-collection-name> \
      -m 'name:<document-name-to-filter-by>'
   ```

   #### As a Prefect [deployment](https://docs.prefect.io/latest/concepts/deployments/)

   1. Create a deployment:

   ```shell
   python -m flows deploy playbook-qa DEV process test -t qa -t playbook
   ```

   2. Run either from the dashboard or programatically:

   ```shell
   prefect deployment run 'playbook-qa/DEV'
   ```



