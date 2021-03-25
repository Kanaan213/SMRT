from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, sessionmaker

# DB metadata.schema config
engine = create_engine('sqlite:///db/smrt.db', echo=False)
Base = declarative_base()

class File(Base): # Table files for SMRT file header
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True)
    ref = Column(String(8), unique=True, nullable=False)
    type = Column(String(4), nullable=False)
    companyid = Column(String, nullable=False)
    createdts = Column(DateTime, nullable=False)
    insertedts = Column(DateTime, nullable=False, default=datetime.utcnow)
    data = relationship('Reading', back_populates='filename', cascade="all, delete, delete-orphan")

    def __repr__(self):
        return f"<File(ref={self.ref}, company={self.companyid}, created={self.createdts})>"

class Reading(Base): # Table readings for actural meter readings linked to filename
    __tablename__ = 'readings'
    id = Column(Integer, primary_key=True)
    meterid = Column(String(9), nullable=False)
    readingdate = Column(String(8), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    value = Column(Float, nullable=False)
    fileid = Column(Integer, ForeignKey('files.id'))
    filename = relationship('File', back_populates='data')
    UniqueConstraint(meterid, timestamp)

    def __repr__(self):
        return f"Reading<File={self.filename.ref}, meter={self.meterid}, reading={self.value}, date={self.readingdate}>"

# Create session operator
Session = sessionmaker(bind=engine)

if __name__ == '__main__':
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    
