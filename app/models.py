from sqlalchemy import Column, Integer, String, Date, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base

# نموذج قسم (Department)
class Department(Base):
    __tablename__ = "departments"
    
    id = Column(Integer, primary_key=True)
    name_ar = Column(String)
    name_la = Column(String)
    short_name = Column(String)
    head_name = Column(String)
    
    # العلاقات مع النماذج الأخرى
    teams = relationship("Team", back_populates="department")
    users = relationship("User", back_populates="department")

# نموذج فريق (Team)
class Team(Base):
    __tablename__ = "teams"
    
    id = Column(Integer, primary_key=True)
    name = Column(String)
    name_en = Column(String)
    short_name = Column(String)
    head_name = Column(String)
    description = Column(Text)
    classification = Column(String)
    domains = Column(String)
    keywords = Column(String)
    program_desc = Column(Text)
    
    department_id = Column(Integer, ForeignKey("departments.id"))
    
    # العلاقات مع النماذج الأخرى
    department = relationship("Department", back_populates="teams")
    members = relationship("User", back_populates="team")

# نموذج مستخدم (User)
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    full_name = Column(String)
    password_hash = Column(String)
    role = Column(String)  # مثل 'admin', 'dept_head', 'leader', 'researcher'
    member_type = Column(String)  # مثل 'permanent', 'phd_student', 'affiliate', 'associate'
    
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    
    # العلاقات مع النماذج الأخرى
    team = relationship("Team", back_populates="members")
    department = relationship("Department", back_populates="users")
    works = relationship("Work", back_populates="researcher")

# نموذج عمل (Work)
class Work(Base):
    __tablename__ = "works"
    
    id = Column(Integer, primary_key=True)
    title = Column(Text)
    details = Column(Text) 
    activity_type = Column(String)  # مثل "مقال في مجلة علمية", "مداخلة في مؤتمر"
    classification = Column(String)  # مثل "A", "B", "Q1", "Q2", "Q3"
    publication_date = Column(Date)
    year = Column(Integer)
    points = Column(Integer)
    
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # العلاقات مع النماذج الأخرى
    researcher = relationship("User", back_populates="works")
