# ML-Flows

This repo implements a series of Machine Learning [Prefect](https://www.prefect.io/opensource) dataflows.

For example `SHRAG: Structured Heriarchical Retrieval Augmented Generation` using [LlamaIndex](https://www.llamaindex.ai/) as .

> 💡 Once installed, check all the flows with:

```shell
inv ls
```

## How to

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

5. **Run:**

   First update the `.env` file as necessary. (See `.example.env` for guidance)

   Then there are two ways to run flows;


   ### As a python module

   Simply, as you'd run the module's CLI present in each submodule's `__main__.py`:

   ```shell
   source .env; # For ease so we don't need to pass tons of params

   # Running a flow directly from its __main__ entrypoint
   # E.g.: Run a QA-Playbook filtering by document name
   python -m flows.shrag run-playbook-qa \
      data/Playbook_sample.csv \
      data/proto_questions_sample.json \
      <your-chromaDB-collection-name> \
      -m 'name:<document-name-to-filter-by>'
   ```

   ### As [deployment](https://docs.prefect.io/latest/concepts/deployments/)

   TBD



