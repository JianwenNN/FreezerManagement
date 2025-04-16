from sqlalchemy import Column, Integer, String, ForeignKey, Date, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class StudySample(Base):
    __tablename__ = "study_samples"
    
    id = Column(Integer, primary_key=True, index=True)
    container_id = Column(Integer, ForeignKey("container.id"), nullable=False)
    study_name = Column(String(200), nullable=False)
    project_id = Column(String(100), nullable=False)
    storage_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    container = relationship("Container", back_populates="study_samples")
    
    def __repr__(self):
        return f"<StudySample(id={self.id}, study_name={self.study_name}, project_id={self.project_id})>"


class NonGLPSample(Base):
    __tablename__ = "nonglp_preparation_samples"
    
    id = Column(Integer, primary_key=True, index=True)
    container_id = Column(Integer, ForeignKey("container.id"), nullable=False)
    study_name = Column(String(200), nullable=False)
    project_id = Column(String(100), nullable=False)
    preparation_date = Column(Date, nullable=False)
    storage_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    container = relationship("Container", back_populates="nonglp_samples")
    
    def __repr__(self):
        return f"<NonGLPSample(id={self.id}, study_name={self.study_name}, project_id={self.project_id})>"


class GLPSample(Base):
    __tablename__ = "glp_preparation_sample"
    
    id = Column(Integer, primary_key=True, index=True)
    container_id = Column(Integer, ForeignKey("container.id"), nullable=False)
    preparation_id = Column(String(100), unique=True, nullable=False)
    preparation_date = Column(Date, nullable=False)
    type = Column(String(100), nullable=False)
    study_name = Column(String(200), nullable=False)
    project_id = Column(String(100), nullable=False)
    expiration_date = Column(Date, nullable=False)
    storage_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    container = relationship("Container", back_populates="glp_samples")
    
    def __repr__(self):
        return f"<GLPSample(id={self.id}, preparation_id={self.preparation_id}, study_name={self.study_name})>"