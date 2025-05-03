from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, Text, DateTime, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy import Boolean

from .base import Base


class Freezer(Base):
    __tablename__ = "freezer"
    
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(String(50), unique=True, nullable=False)
    temperature = Column(Numeric(5, 2), nullable=False)
    num_of_layers = Column(Integer, nullable=False)
    num_of_rack_per_layer = Column(Integer, nullable=False)
    num_of_drawer_per_rack = Column(Integer, nullable=False)
    description = Column(Text)
    location = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    layers = relationship("Layer", back_populates="freezer", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("num_of_layers > 0", name="check_positive_layers"),
        CheckConstraint("num_of_rack_per_layer > 0", name="check_positive_racks"),
        CheckConstraint("num_of_drawer_per_rack > 0", name="check_positive_drawers"),
    )
    
    def __repr__(self):
        return f"<Freezer(id={self.id}, asset_id={self.asset_id})>"


class Layer(Base):
    __tablename__ = "layer"
    
    id = Column(Integer, primary_key=True, index=True)
    freezer_id = Column(Integer, ForeignKey("freezer.id", ondelete="CASCADE"), nullable=False)
    layer_number = Column(Integer, nullable=False)
    description = Column(Text)
    
    # Relationships
    freezer = relationship("Freezer", back_populates="layers")
    racks = relationship("Rack", back_populates="layer", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("freezer_id", "layer_number", name="uq_layer_freezer_number"),
        CheckConstraint("layer_number > 0", name="check_positive_layer_number"),
    )
    
    def __repr__(self):
        return f"<Layer(id={self.id}, freezer_id={self.freezer_id}, layer_number={self.layer_number})>"


class Rack(Base):
    __tablename__ = "rack"
    
    id = Column(Integer, primary_key=True, index=True)
    layer_id = Column(Integer, ForeignKey("layer.id", ondelete="CASCADE"), nullable=False)
    rack_number = Column(Integer, nullable=False)
    description = Column(Text)
    
    # Relationships
    layer = relationship("Layer", back_populates="racks")
    drawers = relationship("Drawer", back_populates="rack", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("layer_id", "rack_number", name="uq_rack_layer_number"),
        CheckConstraint("rack_number > 0", name="check_positive_rack_number"),
    )
    
    def __repr__(self):
        return f"<Rack(id={self.id}, layer_id={self.layer_id}, rack_number={self.rack_number})>"


class Drawer(Base):
    __tablename__ = "drawer"
    
    id = Column(Integer, primary_key=True, index=True)
    rack_id = Column(Integer, ForeignKey("rack.id", ondelete="CASCADE"), nullable=False)
    drawer_number = Column(Integer, nullable=False)
    drawer_type_id = Column(Integer, ForeignKey("drawer_type.id"), nullable=False)
    description = Column(Text)
    # Add these new fields
    reserved = Column(Boolean, default=False, nullable=False)
    reserved_reason = Column(String(200), nullable=True)
    
    # Relationships
    rack = relationship("Rack", back_populates="drawers")
    drawer_type = relationship("DrawerType", back_populates="drawers")
    study_sample_containers = relationship("StudySampleContainer", back_populates="drawer")
    stdqc_containers = relationship("STDQCContainer", back_populates="drawer")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("rack_id", "drawer_number", name="uq_drawer_rack_number"),
        CheckConstraint("drawer_number > 0", name="check_positive_drawer_number"),
    )
    
    def __repr__(self):
        return f"<Drawer(id={self.id}, rack_id={self.rack_id}, drawer_number={self.drawer_number}, reserved={self.reserved})>"