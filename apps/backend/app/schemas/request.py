from pydantic import BaseModel, ConfigDict


class StrictRequestModel(BaseModel):
    """Public JSON request bodies reject unknown fields and type coercion."""

    model_config = ConfigDict(extra="forbid", strict=True)
