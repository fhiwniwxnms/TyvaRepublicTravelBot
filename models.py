from sqlalchemy.orm import declarative_base
from sqlalchemy import Table, Column, Integer, String, Text, Float, ForeignKey

Base = declarative_base()

route_tags = Table(
    "route_tags",
    Base.metadata,
    Column("route_id", Integer, ForeignKey("routes.id"), primary_key=True),
    Column("tag", String, primary_key=True),
)

route_seasons = Table(
    "route_seasons",
    Base.metadata,
    Column("route_id", Integer, ForeignKey("routes.id"), primary_key=True),
    Column("season", String, primary_key=True),
)

route_transports = Table(
    "route_transports",
    Base.metadata,
    Column("route_id", Integer, ForeignKey("routes.id"), primary_key=True),
    Column("transport", String, primary_key=True),
)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(Integer, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    preferences = Column(Text, nullable=True)


class Route(Base):
    __tablename__ = "routes"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    length_km = Column(Float, nullable=True)
    difficulty = Column(String, nullable=True)
    price_estimate = Column(Float, nullable=True)
    link = Column(String, nullable=True)
    popularity = Column(Integer, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "length_km": self.length_km,
            "difficulty": self.difficulty,
            "price_estimate": self.price_estimate,
            "link": self.link,
            "popularity": self.popularity,
        }
