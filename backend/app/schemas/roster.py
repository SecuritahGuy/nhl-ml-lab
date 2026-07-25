from pydantic import BaseModel


class RosterPlayer(BaseModel):
    id: int
    first_name: str
    last_name: str
    position_code: str
    sweater_number: int | None = None
    birth_date: str | None = None
    birth_city: str | None = None
    birth_state_province: str | None = None
    birth_country: str | None = None
    height_inches: int | None = None
    weight_pounds: int | None = None
    headshot: str | None = None
    shoots_catches: str | None = None


class RosterResponse(BaseModel):
    team_abbrev: str
    season: str
    forwards: list[RosterPlayer]
    defensemen: list[RosterPlayer]
    goalies: list[RosterPlayer]