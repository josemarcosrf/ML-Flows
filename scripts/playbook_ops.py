import json
from pathlib import Path

import click
import pandas as pd


def clean_playbook(playbook_df: pd.DataFrame) -> pd.DataFrame:
    # Replace pandas NA with None for JSON serialization
    playbook_df = playbook_df.replace(pd.NA, None)
    # Fill NaN values with empty strings
    playbook_df = playbook_df.fillna("")
    # Remove any Unamed columns
    playbook_df = playbook_df.loc[:, ~playbook_df.columns.str.contains("^Unnamed")]
    # Remove any columns that are all empty
    playbook_df = playbook_df.dropna(axis=1, how="all")
    # Remove any rows that are all empty
    playbook_df = playbook_df.dropna(axis=0, how="all")

    return playbook_df


@click.group()
def cli():
    """Playbook Operations"""
    pass


@cli.command("merge")
@click.argument("playbook_csv", type=click.Path(exists=True, dir_okay=False))
@click.argument("proto_questions_json", type=click.Path(exists=True, dir_okay=False))
@click.argument("output_json")
def merge_playbook_and_proto_questions(
    playbook_csv: str, proto_questions_json: str, output_json: str
):
    """Merges a playbook CSV with a proto questions JSON file and outputs a JSON file.

    The playbook CSV should have the following columns:
    - Group
    - Attribute
    - Question
    - Question-Type

    The proto questions JSON should have the following structure:
    {
        "<Attribute>": {
            "valid_answer": ["answer1", "answer2", ...]
        }
    }
    The output JSON will have the following structure:
    {
        "<Attribute>": {
            "group": "<Group>",
            "Question": "<Question>",
            "QuestionType": "<Question-Type>",
            "ValidAnswers": ["answer1", "answer2", ...]
        }
    }

    Args:
        playbook_csv (str): _path to the playbook CSV file_
        proto_questions_json (str): _path to the proto questions JSON file_
        output_json (str): _path to the output JSON file_
    """
    # Read and clean the playbook CSV
    print(f"📚 Reading playbook CSV {playbook_csv}")
    playbook_df = clean_playbook(pd.read_csv(playbook_csv))

    # Read the proto questions JSON
    print(f"📚 Reading proto-questions JSON file {proto_questions_json}")
    with Path(proto_questions_json).open("r") as f:
        proto_questions = json.load(f)

    # Merge the playbook and proto questions by the Attribute column
    print("🔁 Merging playbook and proto questions")
    unified_playbook = {}
    for _, row in playbook_df.iterrows():
        attribute = row["Attribute"]
        # If the attribute is in the proto questions, add the question and answer to the row
        if proto := proto_questions.get(attribute):
            valid_answers = proto.get("valid_answers", [])
        else:
            valid_answers = []

        if not attribute:
            # This is the first question of a group (the Yes/No question)
            attribute = row["Group"] + " - Yes/No"

        unified_playbook[attribute] = {
            "group": row["Group"],
            "question": row["Question"],
            "question_type": row["Question-Type"],
            "valid_answers": valid_answers,
        }

    # Write the unified playbook to a JSON file
    with Path(output_json).open("w") as f:
        json.dump(unified_playbook, f, indent=2)

    print(f"✨ Converted {playbook_csv} to {output_json}!")


if __name__ == "__main__":
    cli()
