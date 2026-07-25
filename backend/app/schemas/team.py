from pydantic import BaseModel


class Team(BaseModel):
    id: int
    tri_code: str
    full_name: str
    franchise_id: int | None = None
    league_id: int | None = None


class TeamDetail(BaseModel):
    id: int
    abbrev: str | None = None
    common_name: str | None = None
    place_name: str | None = None
    full_name: str | None = None
    logo: str | None = None