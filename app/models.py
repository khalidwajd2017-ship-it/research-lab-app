from sqlalchemy import Column, Integer, String, Date, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base

class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True)
    name_ar = Column(String)
    name_la = Column(String)
    short_name = Column(String)
    head_name = Column(String)
    teams = relationship("Team", back_populates="department")
    users = relationship("User", back_populates="department")

# استكمال بقية النماذج (Team, User, Work) كما هو

