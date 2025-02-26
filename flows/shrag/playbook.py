import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
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


@task
def build_question_library(
    question_library_csv: Path | str,
    proto_questions_json: Path | str,
) -> dict[str, list[QuestionItem]]:
    """Builds the Question Library from the CSV and proto questions JSON

    Args:
        question_library_csv (Path | str): _path_ to the Question Library CSV
        proto_questions_json (Path | str): _path_ to the proto questions JSON
    Returns:
        dict[str, list[QuestionItem]]: Question Library
        - The keys are the group names
        - The values are lists of QuestionItems
        - The QuestionItems are generated from the CSV and proto questions
        - The QuestionItems are generated based on the QuestionType
    """
    # NOTE: For now we continue building the playbook from the CSV and proto questions
    # but we should consider a better approach to build the playbook from the proto questions

    # Read Question Library CSV (aka: The Playbook)
    q_library_df = pd.read_csv(question_library_csv)
    q_library_df.replace(np.nan, None, inplace=True)

    # Read the parsed attributes and proto generated questions
    proto_library = json.load(Path(proto_questions_json).open())

    # Add the Answer Schema based on the extracted values
    q_collection = defaultdict(list)
    for _, row in q_library_df.iterrows():
        group = row["Group"]
        attr = row["Attribute"]
        q_type = row["Question-Type"].strip().lower()

        if group:
            group = group.strip()
        if attr:
            attr = attr.strip()

        if q_type == QuestionType.CATEGORICAL:
            # For Categorical questions we use a dynamic schema based on the valid answers
            answer_schema = create_categorical_schema(
                proto_library[attr]["valid_answers"],
                attr,  # use attribute name as description
            )
        else:
            # For everything else we use a fixed Schema
            answer_schema = QUESTION_FORMATS[q_type]["schema"]

        logger.debug(f"group: {group} | attr: {attr}")

        # NOTE: Non-hierarchical Qs live in their own 'group' which equals their 'attr'
        # NOTE: To better understand `group`, `attr` and `key` see:
        # 'data/banneker_B1_export_openai_2025-02-14.csv
        q_collection[group or attr].append(
            QuestionItem(
                key=attr or f"{group} - yes/no",
                question=row["Question"],
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
