import json
import os
from pathlib import Path

import click
from pymongo import MongoClient


@click.group()
def cli():
    """A CLI tool for uploading QA results to MongoDB."""
    pass


@cli.command()
@click.argument("data-dir")
@click.option("--client-id", required=True, help="Client ID to use for uploads.")
@click.option("--playbook-id", required=True, help="Playbook ID to use for uploads.")
def results_to_mongo(data_dir, client_id, playbook_id):
    """Upload QA results from JSON files to MongoDB.
    This script reads JSON files containing QA results from a specified directory
    and uploads them to a MongoDB collection. Each JSON file should be named in the
    format `name=<document_name>_qa_results.json`, where `<document_name>` is the
    name of the document for which the QA results are being stored.
    The JSON files should contain a dictionary where each key is a question and the
    value is a dictionary with the answer and additional metadata.
    The MongoDB collection will store the results with the following structure:
    ```json
    {
        "meta_filters": {"name": "<document_name>"},
        "client_id": "<client_id>",
        "playbook_id": "<playbook_id>",
        "answers": {
            "<question_1>": {
                "answer": "<answer_text>",
                "confidence": <confidence_score>,
                ...additional_metadata
            },
            ...
        }
    }
    ```
    The `client_id` and `playbook_id` are used to associate the results with a specific
    client and playbook, respectively.

    Args:
        data_dir (str): Path to the directory containing the JSON files with QA results.
        client_id (str): Client ID to use for uploads.
        playbook_id (str): Playbook ID to use for uploads.

    Raises:
        EnvironmentError: If the MONGO_URI or MONGO_DB environment variables are not set.
    """
    # Read MongoDB URI and database from environment variables
    mongo_uri = os.environ.get("MONGO_URI")
    mongo_db = os.environ.get("MONGO_DB")
    if not mongo_uri or not mongo_db:
        raise EnvironmentError(
            "💥 MONGO_URI and MONGO_DB environment variables must be set."
        )

    # Connect to MongoDB
    client = MongoClient(mongo_uri)
    db = client[mongo_db]
    collection = db["results"]

    # Path to JSON files
    data_path = Path(data_dir)
    json_files = list(data_path.glob("name=*_qa_results.json"))

    for json_file in json_files:
        with open(json_file, "r", encoding="utf-8") as f:
            answers = json.load(f)

        parsed_answers = {}
        for k, v in answers.items():
            ans = v.pop("answer")
            parsed_answers[k] = {
                "answer": ans["response"],
                "confidence": ans["confidence"],
                **v,
            }

        dname = json_file.stem.replace("name=", "").replace("_qa_results", "")
        dname = dname.split(".")[0].strip()
        doc = {
            "meta_filters": {"name": dname},
            "client_id": client_id,
            "playbook_id": playbook_id,
            "answers": parsed_answers,
        }

        collection.insert_one(doc)

        print(f"✅ Uploaded results for {dname} to MongoDB.")


if __name__ == "__main__":
    cli()
