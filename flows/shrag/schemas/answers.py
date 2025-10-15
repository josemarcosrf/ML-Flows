from enum import Enum

from dateutil import parser
from loguru import logger
from pydantic import BaseModel, Field, field_validator


class YesNoEnum(Enum):
    pos = "Yes"
    neg = "No"
    NON = None


class BaseAnswer(BaseModel):
    response: str = Field(
        ...,
        description=(
            "A concise, yet complete response to the user query. "
            "This is the response that a human would want."
        ),
    )
    confidence: float = Field(
        ...,
        description="Confidence value between 0-1 of the correctness of the result.",
    )

    @field_validator("response")
    def convert_enum_to_str(cls, v):
        if isinstance(v, Enum):
            return v.value
        return v


class CustomerInformation(BaseAnswer):
    name: str = Field(..., description="Customer's name")
    address: str = Field(..., description="Customer's postal address")
    city: str = Field(..., description="Customer's city")
    zip_code: str = Field(..., description="Customer's zip code")
    country: str = Field(..., description="Customer's country")
    state: str = Field(..., description="Customer's state")
    contact_name: str = Field(..., description="Customer's contact name")
    contact_email: str = Field(..., description="Customer's contact email")
    contact_phone: str = Field(..., description="Customer's contact phone number")

    # Remove `response` field from the schema
    __annotations__.pop("response", None)


class ExtractiveAnswer(BaseAnswer):
    response: str = Field(
        ...,
        description=(
            "An extracted value. e.g.: A Quantity, Distance, Percentage, Value, Name or Location"
        ),
    )


class YesNoAnswer(BaseAnswer):
    response: YesNoEnum | None = Field(
        ..., description="An Affirmative or Negative answer"
    )

    @field_validator("response", mode="before")
    @classmethod
    def normalize_yesno(cls, v):
        """Accept string values case-insensitively and coerce them to YesNoEnum.

        Examples accepted: "yes", "No", "yEs", (will be mapped
        to the corresponding enum). If value is already a YesNoEnum or None,
        it's returned unchanged.
        """
        if v is None:
            return None
        # If already an enum, return as-is
        if isinstance(v, Enum):
            return v
        # Normalize strings
        if isinstance(v, str):
            return YesNoEnum(v.strip().capitalize())

        return v

    def model_dump(self, *args, **kwargs):
        data = super().model_dump(*args, **kwargs)
        if isinstance(data.get("response"), Enum):
            data["response"] = data["response"].value
        return data


class SummaryAnswer(
    BaseAnswer
): ...  # No additional fields, inherits from BaseAnswer. Mostly as a placeholder for old playbooks.


class DateAnswer(BaseAnswer):
    date: str = Field(..., description="An extracted, well formatted date")

    @field_validator("date")
    @classmethod
    def check_date_format(cls, value) -> str | None:
        try:
            # Use dateutil to parse the date in multiple possible formats.
            # We don't care about the parsed date, just checking if it's parseable
            parser.parse(value)
            return value
        except (ValueError, TypeError):
            logger.warning(
                f"Error validating Date. '{value}' is not in a recognized date format"
            )
            return None


class RiskAssesmentAnswer(BaseAnswer):
    answer_category: str = Field(
        ...,
        description=(
            "Category based on the given answer categories. "
            "This category is to be matched based on the response and the provided categories"
        ),
    )
    assigned_risk: int = Field(
        ..., description="Risk assignation based on the answer category. From 0 to 100"
    )
