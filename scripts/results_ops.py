import json
import os
from pathlib import Path

import click
import pandas as pd
from pymongo import MongoClient


def get_mongo_db():
    """Get a MongoDB DB using environment variables."""
    mongo_uri = os.getenv("MONGO_URI")
    mongo_db = os.getenv("MONGO_DB")

    if not mongo_uri or not mongo_db:
        raise OSError("MONGO_URI and MONGO_DB environment variables must be set.")

    print(f"🔌 Connecting to MongoDB at {mongo_uri} and database {mongo_db}...")
    client = MongoClient(mongo_uri)
    return client[mongo_db]


@click.group()
def cli():
    """A CLI tool for uploading QA results to MongoDB."""
    pass


@cli.command()
@click.argument("data-dir")
@click.argument("results-csv")
@click.option("--client-id", required=True, help="Client ID to use for uploads.")
@click.option("--playbook-id", required=True, help="Playbook ID to use for uploads.")
def csv_results_to_mongo(data_dir, results_csv, client_id, playbook_id):
    # Get MongoDB client and collection
    db = get_mongo_db()
    collection = db["results"]

    # Read the CSV file
    df = pd.read_csv(results_csv)
    print(f"Read {len(df)} rows from {results_csv}.")
    if df.empty:
        print("No data found in the CSV file.")
        return

    # Iterate over each row in the DataFrame
    for index, row in df.iterrows():
        # Extract the document name from the 'name' column
        dname = row["Document"].strip()

        # Find the corresponding subdirectory based on the document name
        doc_file = next(Path(data_dir).rglob(f"**/{dname}/"), None)
        if doc_file is None:
            print(
                f"Skipping row {index} as no subdirectory found for document {dname}."
            )
            continue
        else:
            subdir = doc_file.relative_to(Path(data_dir))
            print(f"Found subdirectory for {dname} ➡️  {subdir}")

        # Prepare the document to be inserted
        meta_filters = {"subdir": str(subdir)}
        doc = {
            "meta_filters": meta_filters,
            "client_id": client_id,
            "playbook_id": playbook_id,
            "answers": {},
        }
        # Iterate over the columns to extract answers
        for col in df.columns:
            if col != "name":
                answer = row[col]
                if pd.notna(answer):
                    doc["answers"][col] = {
                        "answer": answer,
                        "confidence": 1.0,  # Assuming confidence is always 1.0 for CSV results
                    }

        # Compose the query to find existing documents
        query = {
            **{f"meta_filters.{k}": v for k, v in meta_filters.items()},
            "client_id": client_id,
            "playbook_id": "7499d6d7-026f-4152-b5e2-9703a18b77b9",  # search with old playbook_id
        }
        # Upsert the document into the MongoDB collection
        res = collection.update_one(query, {"$set": doc}, upsert=True)
        if res.matched_count == 0:
            print(f"Inserted new document for {dname}.")
        else:
            print(f"Updated {res.matched_count} existing document for {dname}.")


@cli.command()
@click.argument("data-dir")
@click.option("--client-id", required=True, help="Client ID to use for uploads.")
@click.option("--playbook-id", required=True, help="Playbook ID to use for uploads.")
def json_results_to_mongo(data_dir, client_id, playbook_id):
    """Upload QA results from JSON files to MongoDB.
    This script reads JSON files containing QA results from a specified directory
    and uploads them to a MongoDB collection.

    Each JSON file should be named in the format `name=<document_name>_qa_results.json`,
    where `<document_name>` is the name of the document for which the QA results are being stored.
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
    # Get MongoDB client and collection
    db = get_mongo_db()
    collection = db["results"]

    # Path to JSON files
    data_path = Path(data_dir)
    json_files = list(data_path.glob("name=*_qa_results.json"))
    print(f"Found {len(json_files)} JSON files in {data_path}.")

    for json_file in json_files:
        with open(json_file, encoding="utf-8") as f:
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
            "meta_filters": {
                "subdir": str(json_file.parent.parent / json_file.parent.name),
                "name": dname,
            },
            "client_id": client_id,
            "playbook_id": playbook_id,
            "answers": parsed_answers,
        }

        collection.insert_one(doc)
        print(f"✅ Uploaded results for {dname} to MongoDB.")


if __name__ == "__main__":
    cli()
