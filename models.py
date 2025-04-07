from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class MegaAccount(Base):
    __tablename__ = "mega_accounts"

    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)
    is_pro_account = Column(Boolean, nullable=True)
    used_quota = Column(String, nullable=True)
    total_quota = Column(String, nullable=True)
    storage_quota_updated = Column(DateTime, nullable=True)
    last_login = Column(DateTime, nullable=True)

class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True)
    local_path = Column(String, nullable=False)
    file_indices = Column(Text, nullable=False)
    is_uploaded = Column(Boolean, nullable=True)

class MegaFile(Base):
    __tablename__ = "mega_files"

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("mega_accounts.id"), nullable=False)
    is_local = Column(Boolean, nullable=True)
    sharing_link = Column(String, nullable=True)
    sharing_link_expiry = Column(DateTime, nullable=True)
    file_indices = Column(Text, nullable=True)
