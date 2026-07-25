from dataclasses import dataclass


@dataclass
class Player:
    id: int
    full_name: str
    first_name: str
    last_name: str
    position: str
    jersey_number: int | None = None
    birth_date: str | None = None
    nationality: str | None = None
    height: str | None = None
    weight: int | None = None