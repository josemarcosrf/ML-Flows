from enum import Enum
from typing import TypedDict

from pydantic import BaseModel

from flows.shrag.schemas.answers import (
    CustomerInformation,
    DateAnswer,
    ExtractiveAnswer,
    SummaryAnswer,
    YesNoAnswer,
)


class QuestionFormat(TypedDict):
    message: str
    schema: type[BaseModel]


class QuestionType(str, Enum):
    CATEGORICAL = "categorical"
    DATETIME = "datetime"
    EXTRACTIVE = "extractive"
    SUMMARISATION = "summarisation"
    YES_NO = "yes/no"


QUESTION_FORMATS: dict[str, QuestionFormat] = {
    # NOTE: We expect the question types to be in lowercase for easier parsing
    # and spaces are replaced with dashes.
    "yes/no": {
        "message": "Tips: Make sure to answer in the correct format: 'Yes' or 'No' ",
        "schema": YesNoAnswer,
    },
    "summarisation": {
        "message": (
            "Tips: Make concise summary, if you can't find the answer in "
            "the context return None "
        ),
        "schema": SummaryAnswer,
    },
    "extractive": {
        "message": (
            "Tips: Make sure to answer with an entity-like response when possible "
            "(e.g.: Distances, Amounts, Durations, Monetary values, Locations, Names, "
            "Percentages, Phone Numbers, Emails, etc) "
            "If you can't find the answer in the context return None "
        ),
        "schema": ExtractiveAnswer,
    },
    "datetime": {
        "message": (
            "Tips: Make sure to answer in the correct format, dates in the datetime "
            "format, if you can't find the answer in the context return None "
        ),
        "schema": DateAnswer,
    },
    "customer-information": {
        "message": (
            "Tips: Make sure to answer concisely. If you can't find the information "
            "in the context for any of the fields return None "
        ),
        "schema": CustomerInformation,
    },
    "categorical": {
        "message": (
            "Tips: Make sure to answer with one the provided categories. If the answer "
            "doesn't fall into one of the provided categories return None "
        ),
        "schema": None,  # This Answer model is defined @ question type
    },
}
