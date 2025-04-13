# ML-Flows

This repo implements a series of Machine Learning [Prefect](https://www.prefect.io/opensource) dataflows.

For example `SHRAG: Structured Heriarchical Retrieval Augmented Generation` using [LlamaIndex](https://www.llamaindex.ai/) as .

> 💡 Once installed, check all the flows with:

```shell
$ python -m flows ls # Or: pdm flows ls
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

   > [!INFO] You'll need python 3.12 or greater

   ```shell
   # Install pdm
   curl -sSL https://pdm-project.org/install-pdm.py | python3 -

   # Optionally install uv and set it as dependency resolver
   curl -LsSf https://astral.sh/uv/install.sh | sh
   pdm config use_uv true
   pdm config python.install_root $(uv python dir)
   ```

2. **Install dependencies:**

   ```shell
   pdm sync -G:all
   ```

3. **Auxiliary Services:**
   - Ensure you have a **ChromaDB** instance running: `inv local-chroma`
   - Ensure you have the **Prefect server** running: `inv local-prefect`
   - Ensure you have a running **Prefect pool**: `inv start-worker-pool -p process -n test --overwrite`

### Run

   First update the `.env` file as necessary. (See `.example.env` for guidance)

#### Auxiliary Services

   Local auxiliary services:

   ```shell
   inv local-chroma &               # start chroma
   inv local-prefect &              # start prefect
   inv local-worker-pool process &  # start a prefect process worker pool
   ```

   We also make use of Ray Serve deployments for OCR and Document Parsing available
   via a REST API. Check out [DoPARSE](https://github.com/josemarcosrf/DoPARSE)

   Additionally, you might want to configure Prefect to store results when running
   locally:

   ```bash
   prefect config set PREFECT_LOCAL_STORAGE_PATH="~/.prefect/storage"
   prefect config view # check modified settings
   ```

   Then there are two ways to run flows;

#### Flows - As python modules

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

#### Flows - As Prefect [deployments](https://docs.prefect.io/latest/concepts/deployments/)

1. Create a deployment:

```shell
pdm flows deploy playbook-qa DEUS process local-process-pool -t qa -t playbook
pdm flows deploy index-files DEUS process local-process-pool -t preproc -t markdown
```

2. Run either from the dashboard or programatically:

```shell
prefect deployment run 'playbook-qa/DEUS'
```



