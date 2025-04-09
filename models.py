from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

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

    mega_files = relationship("MegaFile", back_populates="account")


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True)
    path = Column(String, nullable=False)
    folder_name = Column(String, nullable=True)
    folder_size = Column(String, nullable=True)

    mega_files = relationship("MegaFile", back_populates="local_file")


class MegaFile(Base):
    __tablename__ = "mega_files"

    id = Column(Integer, primary_key=True)
    path = Column(String, nullable=True)
    folder_name = Column(String, nullable=True)
    folder_size = Column(String, nullable=True)

    mega_account_id = Column(Integer, ForeignKey("mega_accounts.id"), nullable=False)
    local_id = Column(Integer, ForeignKey("files.id"), nullable=True)

    mega_sharing_link = Column(String, nullable=True)
    mega_sharing_link_expiry = Column(DateTime, nullable=True)

    account = relationship("MegaAccount", back_populates="mega_files")
    local_file = relationship("File", back_populates="mega_files")


class Setting(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String)
