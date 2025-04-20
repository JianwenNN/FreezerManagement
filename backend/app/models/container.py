from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base

class ContainerType(Base):
    __tablename__ = "container_type"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    dimensions = Column(String(50), nullable=False)
    description = Column(Text)
    
    # Relationships
    containers = relationship("Container", back_populates="container_type")
    drawer_capacities = relationship("DrawerCapacity", back_populates="container_type")
    
    def __repr__(self):
        return f"<ContainerType(id={self.id}, name={self.name}, dimensions={self.dimensions})>"

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
    
    # Constraints
    __table_args__ = (
        CheckConstraint("max_capacity > 0", name="check_positive_capacity"),
    )
    
    def __repr__(self):
        return f"<DrawerCapacity(drawer_type_id={self.drawer_type_id}, container_type_id={self.container_type_id}, max_capacity={self.max_capacity})>"

class Container(Base):
    __tablename__ = "container"
    
    id = Column(Integer, primary_key=True, index=True)
    container_id = Column(String(100), unique=True, nullable=False)
    drawer_id = Column(Integer, ForeignKey("drawer.id"), nullable=False)
    container_type_id = Column(Integer, ForeignKey("container_type.id"), nullable=False)
    position_in_drawer = Column(String(50))
    date_added = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    drawer = relationship("Drawer", back_populates="containers")
    container_type = relationship("ContainerType", back_populates="containers")
    study_samples = relationship("StudySample", back_populates="container", cascade="all, delete-orphan")
    nonglp_samples = relationship("NonGLPSample", back_populates="container", cascade="all, delete-orphan")
    glp_samples = relationship("GLPSample", back_populates="container", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Container(id={self.id}, container_id={self.container_id}, drawer_id={self.drawer_id})>"