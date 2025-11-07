import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Table, ForeignKey, Float, Text
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy.pool import QueuePool

# Load environment variables from .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL is None:
    raise EnvironmentError("DATABASE_URL not set in .env file")

engine = create_engine(DATABASE_URL, poolclass=QueuePool, pool_size=5, max_overflow=10)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Association Tables (for Many-to-Many relationships) ---

candidate_skills_association = Table('candidate_skills', Base.metadata,
    Column('candidate_id', Integer, ForeignKey('candidates.id'), primary_key=True),
    Column('skill_id', Integer, ForeignKey('skills.id'), primary_key=True)
)

candidate_certifications_association = Table('candidate_certifications', Base.metadata,
    Column('candidate_id', Integer, ForeignKey('candidates.id'), primary_key=True),
    Column('certification_id', Integer, ForeignKey('certifications.id'), primary_key=True)
)


# --- Entity Models ---

class Candidate(Base):
    __tablename__ = 'candidates'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    phone = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    total_experience_years = Column(Float, nullable=True)
    city = Column(String, nullable=True)
    
    skills = relationship("Skill", secondary=candidate_skills_association, back_populates="candidates")
    certifications = relationship("Certification", secondary=candidate_certifications_association, back_populates="candidates")
    
    degrees = relationship("Degree", back_populates="candidate", cascade="all, delete-orphan")
    experiences = relationship("Experience", back_populates="candidate", cascade="all, delete-orphan")

class Skill(Base):
    __tablename__ = 'skills'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    candidates = relationship("Candidate", secondary=candidate_skills_association, back_populates="skills")

class Certification(Base):
    __tablename__ = 'certifications'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    candidates = relationship("Candidate", secondary=candidate_certifications_association, back_populates="certifications")

class Company(Base):
    __tablename__ = 'companies'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    experiences = relationship("Experience", back_populates="company")

class College(Base):
    __tablename__ = 'colleges'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    degrees = relationship("Degree", back_populates="college")

# --- Relationship Models ---

class Degree(Base):
    __tablename__ = 'degrees'
    id = Column(Integer, primary_key=True, index=True)
    degree_name = Column(String, nullable=True) # <-- Your added field
    passed_out_year = Column(Integer, nullable=True)
    
    candidate_id = Column(Integer, ForeignKey('candidates.id'))
    college_id = Column(Integer, ForeignKey('colleges.id'))
    
    candidate = relationship("Candidate", back_populates="degrees")
    college = relationship("College", back_populates="degrees") # <-- This is the corrected relationship

class Experience(Base):
    __tablename__ = 'experiences'
    id = Column(Integer, primary_key=True, index=True)
    total_years = Column(Float, nullable=True)
    role = Column(String)
    description = Column(Text, nullable=True)
    
    candidate_id = Column(Integer, ForeignKey('candidates.id'))
    company_id = Column(Integer, ForeignKey('companies.id'))
    
    candidate = relationship("Candidate", back_populates="experiences")
    company = relationship("Company", back_populates="experiences")


# --- Utility Functions ---

def create_db_and_tables():
    """Creates all tables in the database (if they don't exist)."""
    Base.metadata.create_all(bind=engine)

def recreate_db_and_tables():
    """
    Drops all tables and recreates them.
    WARNING: This will delete all existing data.
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

def get_db():
    """Dependency to get a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()