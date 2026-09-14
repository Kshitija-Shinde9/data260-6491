from typing import List

from pydantic import BaseModel, Field, field_validator


# we need exactly three string tags each 3 to 30 characters
# and a summary of at most 25 words.
class PlannerOutput(BaseModel):
    # min_length and max_length both 3 means the list must hold exactly 3 tags.
    tags: List[str] = Field(min_length=3, max_length=3)
    summary: str

    # Pydantic can check the number of tags on its own but not the length of
    # each one inside the list so I check that myself
    @field_validator("tags")
    @classmethod
    def each_tag_is_the_right_length(cls, tags: List[str]) -> List[str]:
        for tag in tags:
            if len(tag) < 3:
                raise ValueError(f"tag '{tag}' is too short, it must be at least 3 characters")
            if len(tag) > 30:
                raise ValueError(f"tag '{tag}' is too long, it must be at most 30 characters")
        return tags

    # Pydantic counts characters, not words, so I count the words myself.
    @field_validator("summary")
    @classmethod
    def summary_is_short_enough(cls, summary: str) -> str:
        word_count = len(summary.split())
        if word_count > 25:
            raise ValueError(f"summary has {word_count} words, it must be at most 25")
        if word_count == 0:
            raise ValueError("summary is empty")
        return summary


# Checks one Planner answer against the rules
def validate_planner_output(data: dict) -> tuple:
    try:
        PlannerOutput(
            tags=data.get("tags", []),
            summary=data.get("summary", ""),
        )
        return True, ""
    except Exception as error:
        messages = []
        for problem in getattr(error, "errors", lambda: [])():
            where = ".".join(str(p) for p in problem.get("loc", ()))
            what = problem.get("msg", "")
            messages.append(f"{where}: {what}")
        return False, "; ".join(messages) if messages else str(error)
