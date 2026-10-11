"""Pydantic shared models will be added in Block 2 and later."""
from pydantic import BaseModel


class SharedBaseModel(BaseModel):
    """Common base for future Pydantic contracts."""

    class Config:
        extra = "forbid"