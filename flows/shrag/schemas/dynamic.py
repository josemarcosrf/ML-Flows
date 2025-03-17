from enum import Enum
from typing import Any

from pydantic import BaseModel, create_model, Field

from flows.shrag.schemas.answers import BaseAnswer


def print_schema(model: BaseModel):
    for field_name, field_info in model.model_fields.items():
        print(f"Field: {field_name}")
        print(f"Description: {field_info.description}")
        try:
            print(f"Categories: {list(field_info.annotation.__members__.keys())}")
        except Exception:
            pass
        print("-" * 50)


def create_categorical_schema(categories: list[str] | dict[str, Any], description: str):
    """Function to create a dynamic Pydantic model based on an Enum"""
    if isinstance(categories, list):
        cats = {cat: cat for cat in categories}
    else:
        cats = {cat: val for cat, val in categories.items()}

    # Add a None to the passed categories
    cats["None"] = None

    # Create a dynamic Pydantic model with the generated Enum
    cat_enum = Enum("CategoryEnum", cats)
    schema = create_model(
        "CategoricalAnswer",
        __base__=BaseAnswer,  # Inherit from BaseAnswer
        response=(cat_enum, Field(..., description=description)),
    )
    # Adapt the model_dump method to handle Enum
    schema.model_dump = lambda self: {
        "response": self.response.value,
        "confidence": self.confidence,
        "confidence_explanation": self.confidence_explanation,
    }

    return schema
