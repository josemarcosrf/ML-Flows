import json
import os
from pathlib import Path

import click
from pymongo import MongoClient


@click.command()
@click.argument("data-dir")
@click.option("--client-id", required=True, help="Client ID to use for uploads.")
@click.option("--playbook-id", required=True, help="Playbook ID to use for uploads.")
def main(data_dir, client_id, playbook_id):
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
    main()
