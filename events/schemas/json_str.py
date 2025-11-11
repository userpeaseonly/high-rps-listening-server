from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema
from typing import Any
import json

class JsonStr(dict):
    @classmethod
    def __get_pydantic_core_schema__(cls, _source, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(cls._validate, core_schema.str_schema())

    @classmethod
    def _validate(cls, v: str) -> dict:
        try:
            return json.loads(v)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON string: {e}")