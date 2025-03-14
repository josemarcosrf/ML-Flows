from enum import Enum

from dateutil import parser
from pydantic import BaseModel, Field, field_validator


class YesNoEnum(Enum):
    pos = "Yes"
    neg = "No"
    NON = None


class BaseAnswer(BaseModel):
    response: str | Enum = Field(
        ..., description="Field to be overriden by the sub-class"
    )
    confidence: float = Field(
        ...,
        description="Confidence value between 0-1 of the correctness of the result.",
    )
    confidence_explanation: str = Field(
        ..., description="Explanation for the confidence score"
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


class SummaryAnswer(BaseAnswer):
    # NOTE: Renamed from 'summary' to have a uniform output schema
    response: str = Field(..., description="A concise yet complete summary")


class DateAnswer(BaseAnswer):
    # NOTE: Renamed from 'date' to have a uniform output schema
    response: str = Field(..., description="An extracted, well formatted date")

    @field_validator("response")
    @classmethod
    def check_date_format(cls, value) -> str | None:
        try:
            # Use dateutil to parse the date in multiple possible formats.
            # We don't care about the parsed date, just checking if it's parseable
            parser.parse(value)
            return value
        except (ValueError, TypeError):
            print(
                f"Error validating Date. '{value}' is not in a recognized date format"
            )
            return None
