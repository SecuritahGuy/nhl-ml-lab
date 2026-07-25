from dataclasses import dataclass


@dataclass
class Team:
    id: int
    name: str
    abbreviation: str
    venue: str
    conference: str
    division: str
    active: bool = True