import json
from collections import defaultdict
from pathlib import Path

from loguru import logger
from prefect import task
from pydantic import BaseModel

from flows.shrag.schemas.dynamic import create_categorical_schema
from flows.shrag.schemas.questions import QUESTION_FORMATS, QuestionType


class QuestionItem(BaseModel):
    key: str  # Represents the attribute name to extract
    question: str
    question_type: str
    answer_schema: type[BaseModel]


def read_playbook_json(playbook_json: Path | str) -> dict[str, dict[str, str]]:
    """Reads the playbook JSON file and returns the contents as a dictionary.

    Args:
        playbook_json (str): Path to the playbook JSON file
    Returns:
        dict[str, dict[str, str]]: Playbook JSON contents
    """
    return json.load(Path(playbook_json).open())


@task
def build_question_library(
    playbook: dict[str, dict[str, str | list[str]]],
) -> dict[str, list[QuestionItem]]:
    """Builds the Question Library from the playbook JSON file.

    The playbook should have the following structure:
    {
        "<Attribute>": {
            "Group": "<Group>",
            "Question": "<Question>",
            "QuestionType": "<Question-Type>",
            "ValidAnswers": ["answer1", "answer2", ...]
        }
    }

    Args:
        playbook_json (Path | str): _path_ to the proto questions JSON
    Returns:
        dict[str, list[QuestionItem]]: Question Library
        - The keys are the group names
        - The values are lists of QuestionItems
        - The QuestionItems are generated from the CSV and proto questions
        - The QuestionItems are generated based on the QuestionType
    """
    # Add the Answer Schema based on the extracted values
    q_collection = defaultdict(list)
    for attr, qitem in playbook.items():
        group = qitem["Group"]
        q_type = qitem["QuestionType"].strip().lower()

        if group:
            group = group.strip()
        if attr:
            attr = attr.strip()

        if q_type == QuestionType.CATEGORICAL:
            # For Categorical questions we use a dynamic schema based on the valid answers
            answer_schema = create_categorical_schema(
                qitem["ValidAnswers"],
                attr,  # use attribute name as description
            )
        else:
            # For everything else we use a fixed Schema
            answer_schema = QUESTION_FORMATS[q_type]["schema"]

        logger.debug(f"group: {group} | attr: {attr}")

        # NOTE: Non-hierarchical Qs live in their own 'group' which equals their 'attr'
        q_collection[group or attr].append(
            QuestionItem(
                key=attr or f"{group} - Yes/No",
                question=qitem["Question"],
                question_type=q_type,
                answer_schema=answer_schema,
            )
        )

    return q_collection


def get_question_prompt(q: QuestionItem) -> str:
    """Get the query prompt from a Question item"""
    return "{question}. {tip_message}".format(
        question=q.question,
        tip_message=QUESTION_FORMATS[q.question_type]["message"],
    )
