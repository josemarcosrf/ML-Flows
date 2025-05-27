import json
from collections import defaultdict
from hashlib import sha1

from loguru import logger
from prefect import task
from pydantic import BaseModel

from flows.shrag.schemas.answers import RiskAssesmentAnswer
from flows.shrag.schemas.dynamic import create_categorical_schema
from flows.shrag.schemas.questions import QUESTION_FORMATS, QuestionType


class QuestionItem(BaseModel):
    key: str  # Represents the attribute name to extract
    question: str
    question_type: str
    answer_schema: type[BaseModel]


def q_library_hash(q_library) -> str:
    """Hash the question library to determine if it has changed"""

    # First dump the question library to a JSON string
    d = {k: [q.model_dump() for q in q_list] for k, q_list in q_library.items()}
    for k, q_list in d.items():
        for i, q in enumerate(q_list):
            if "answer_schema" in q:
                d[k][i]["answer_schema"] = str(q["answer_schema"])

    return sha1(json.dumps(d).encode()).hexdigest()


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
    for i, (attr, p_item) in enumerate(playbook.items()):
        attr = attr.strip()
        group = p_item["Group"]
        question = p_item["Question"]
        q_type = p_item["QuestionType"].strip().lower()
        categories = p_item.get("ValidAnswers", [])
        risk_weights = p_item.get("RiskWeights", [])

        if q_type == QuestionType.CATEGORICAL:
            # For Categorical questions we use a dynamic schema based on the valid answers
            answer_schema = create_categorical_schema(
                categories,
                attr,  # use attribute name as description
            )
        elif q_type == QuestionType.RISK:
            # NOTE: This is a bit hacky. We are altering the original question to embed
            # the risk mapping directly as part of it
            cls_to_risk_msg = "\n".join(
                [
                    f"category:{a} -> risk:{r}"
                    for a, r in zip(categories, risk_weights, strict=True)
                ]
            )
            question = (
                f"{question}\n"
                f"These are the valid answer categories and their associated risk:\n"
                f"{cls_to_risk_msg}\n"
            )
            answer_schema = RiskAssesmentAnswer
        else:
            # For everything else we use a fixed Schema
            answer_schema = QUESTION_FORMATS[q_type]["schema"]

        summary = f"{i:03d}. G: {group} | A: {attr} | T: {q_type}"
        if q_type == QuestionType.RISK:
            summary += " | ✳️"

        logger.info(summary)

        # Non-hierarchical Qs live in their own group which equals their attr
        # NOTE: To understand `group`, `attr` and `key` see the 'Banneker_Playbook_v1.csv'
        q_collection[group or attr].append(
            QuestionItem(
                key=attr,
                question=question,
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
