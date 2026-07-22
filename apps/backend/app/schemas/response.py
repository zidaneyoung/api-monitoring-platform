from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer

from app.utc import api_timestamp


class UTCResponseModel(BaseModel):
    """API response model with one RFC 3339 UTC timestamp representation."""

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("*", check_fields=False, when_used="json")
    def serialize_utc_datetimes(self, value: object) -> object:
        return api_timestamp(value) if isinstance(value, datetime) else value
