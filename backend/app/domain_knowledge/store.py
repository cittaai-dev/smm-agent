from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

_FACTS_DIR = Path(__file__).parent / "facts"


class DomainFact(BaseModel):
    id: str
    scope: str  # "global" or "section:<section_id>"
    text: str


@lru_cache
def _load_all() -> list[DomainFact]:
    facts: list[DomainFact] = []
    for path in sorted(_FACTS_DIR.glob("*.yaml")):
        for raw in yaml.safe_load(path.read_text()) or []:
            facts.append(DomainFact(**raw))
    return facts


def facts_for(section_id: str) -> list[DomainFact]:
    scope = f"section:{section_id}"
    return [f for f in _load_all() if f.scope in ("global", scope)]
