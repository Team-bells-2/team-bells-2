from pydantic import BaseModel


class SeedSummary(BaseModel):
    locations_added: int
    suppliers_added: int
    offers_added: int
    reviews_added: int
