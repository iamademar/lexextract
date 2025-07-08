from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Date, Numeric
from sqlalchemy.orm import relationship

from .db import Base


class Client(Base):
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    contact_name = Column(String)
    contact_email = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class Statement(Base):
    __tablename__ = "statements"
    
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    file_path = Column(String, nullable=False)
    
    client = relationship("Client", backref="statements")


class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True)
    statement_id = Column(Integer, ForeignKey("statements.id"), nullable=False)
    date = Column(Date, nullable=False)
    payee = Column(String, nullable=False)
    amount = Column(Numeric, nullable=False)
    type = Column(String, nullable=False)
    balance = Column(Numeric)
    currency = Column(String, default="GBP")
    
    statement = relationship("Statement", backref="transactions") 