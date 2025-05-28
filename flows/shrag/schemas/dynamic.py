from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

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
        cats: dict[str, Any] = {cat: cat for cat in categories}
    else:
        cats: dict[str, Any] = {cat: val for cat, val in categories.items()}

    # Add a None to the passed categories
    cats["None"] = None

    # Create a dynamic Enum
    cat_enum = Enum("CategoryEnum", cats)

    # Custom model to ensure answer_category is JSON serializable
    class CategoricalAnswer(BaseAnswer):
        answer_category: cat_enum = Field(..., description=description)

        def model_dump(self, *args, **kwargs):
            data = super().model_dump(*args, **kwargs)
            if isinstance(data.get("answer_category"), Enum):
                data["answer_category"] = data["answer_category"].value
            return data

    return CategoricalAnswer
