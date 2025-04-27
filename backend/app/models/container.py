from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base

class ContainerType(Base):
    __tablename__ = "container_type"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    description = Column(Text)
    
    # Relationships
    study_sample_containers = relationship("StudySampleContainer", back_populates="container_type")
    stdqc_containers = relationship("STDQCContainer", back_populates="container_type")
    drawer_capacities = relationship("DrawerCapacity", back_populates="container_type")
    
    def __repr__(self):
        return f"<ContainerType(id={self.id}, name={self.name})>"

class DrawerType(Base):
    __tablename__ = "drawer_type"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    description = Column(Text)
    
    # Relationships
    drawers = relationship("Drawer", back_populates="drawer_type")
    drawer_capacities = relationship("DrawerCapacity", back_populates="drawer_type")
    
    def __repr__(self):
        return f"<DrawerType(id={self.id}, name={self.name})>"

class DrawerCapacity(Base):
    __tablename__ = "drawer_capacity"
    
    drawer_type_id = Column(Integer, ForeignKey("drawer_type.id"), primary_key=True)
    container_type_id = Column(Integer, ForeignKey("container_type.id"), primary_key=True)
    max_capacity = Column(Integer, nullable=False)
    
    # Relationships
    drawer_type = relationship("DrawerType", back_populates="drawer_capacities")
    container_type = relationship("ContainerType", back_populates="drawer_capacities")
    
    __table_args__ = (
        CheckConstraint("max_capacity > 0", name="check_positive_capacity"),
    )
    
    def __repr__(self):
        return f"<DrawerCapacity(drawer_type_id={self.drawer_type_id}, container_type_id={self.container_type_id}, max_capacity={self.max_capacity})>"

class StudySampleContainer(Base):
    __tablename__ = "study_sample_container"

    id = Column(Integer, primary_key=True, index=True)
    drawer_id = Column(Integer, ForeignKey("drawer.id"), nullable=False)
    container_type_id = Column(Integer, ForeignKey("container_type.id"), nullable=False)

    container_barcode = Column(String(100), unique=True, nullable=False)
    study_name = Column(String(100), nullable=False)
    position_in_drawer = Column(String(50))
    date_added = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    drawer = relationship("Drawer", back_populates="study_sample_containers")
    container_type = relationship("ContainerType", back_populates="study_sample_containers")

    def __repr__(self):
        return f"<StudySampleContainer(id={self.id}, barcode={self.container_barcode}, study_name={self.study_name})>"

class STDQCContainer(Base):
    __tablename__ = "stdqc_container"

    id = Column(Integer, primary_key=True, index=True)
    drawer_id = Column(Integer, ForeignKey("drawer.id"), nullable=False)
    container_type_id = Column(Integer, ForeignKey("container_type.id"), nullable=False)

    compound_name = Column(String(100), nullable=False)
    matrix = Column(String(50), nullable=False)
    anticoagulant = Column(String(50), nullable=False)
    prep_date = Column(DateTime(timezone=True), nullable=False)
    source_id = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)  # Scanned from frontend
    position_in_drawer = Column(String(50))
    date_added = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    drawer = relationship("Drawer", back_populates="stdqc_containers")
    container_type = relationship("ContainerType", back_populates="stdqc_containers")

    def __repr__(self):
        return f"<STDQCContainer(id={self.id}, compound_name={self.compound_name})>"
