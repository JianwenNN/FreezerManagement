from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class StudySampleContainer(Base):
    __tablename__ = "study_sample_container"

    id                 = Column(Integer, primary_key=True, index=True)
    drawer_id          = Column(Integer, ForeignKey("drawer.id"), nullable=False)
    container_barcode  = Column(String(100), nullable=False, unique=True)
    study_name         = Column(String(100), nullable=False)
    position_in_drawer = Column(String(50))
    date_added         = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    drawer = relationship("Drawer", back_populates="study_sample_containers")

    def __repr__(self):
        return f"<StudySampleContainer(id={self.id}, barcode={self.container_barcode})>"


class STDQCContainer(Base):
    __tablename__ = "stdqc_container"

    id                 = Column(Integer, primary_key=True, index=True)
    drawer_id          = Column(Integer, ForeignKey("drawer.id"), nullable=False)
    compound_name      = Column(String(100), nullable=False)
    matrix             = Column(String(50),  nullable=False)
    anticoagulant      = Column(String(50),  nullable=False)
    prep_date          = Column(DateTime(timezone=True), nullable=False)
    source_id          = Column(String(100))
    description        = Column(Text)
    position_in_drawer = Column(String(50))
    date_added         = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    drawer = relationship("Drawer", back_populates="stdqc_containers")

    def __repr__(self):
        return f"<STDQCContainer(id={self.id}, source_id={self.source_id})>"


class DrawerReservation(Base):
    """
    Soft hold created during the suggest step.
    Expires after 5 minutes. The confirm step validates the token,
    or re-checks live capacity if the reservation has expired.
    Expired rows are purged by a background APScheduler job.
    """
    __tablename__ = "drawer_reservation"

    id             = Column(Integer, primary_key=True, index=True)
    drawer_id      = Column(Integer, ForeignKey("drawer.id", ondelete="CASCADE"), nullable=False)
    sample_type    = Column(String(50), nullable=False)
    reserved_count = Column(Integer, nullable=False)
    token          = Column(String(36), nullable=False, unique=True)
    expires_at     = Column(DateTime(timezone=True), nullable=False)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    drawer = relationship("Drawer")

    def __repr__(self):
        return (
            f"<DrawerReservation(id={self.id}, drawer_id={self.drawer_id}, "
            f"token={self.token}, expires_at={self.expires_at})>"
        )
