from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
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

    files = relationship("File", back_populates="account")

class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True)

    # Local info
    l_path = Column(String, nullable=True)
    l_folder_name = Column(String, nullable=True)
    l_folder_size = Column(String, nullable=True)

    # Cloud (MEGA) info
    m_path = Column(String, nullable=True)
    m_folder_name = Column(String, nullable=True)
    m_folder_size = Column(String, nullable=True)

    m_account_id = Column(Integer, ForeignKey("mega_accounts.id"), nullable=True)
    m_sharing_link = Column(String, nullable=True)
    m_sharing_link_expiry = Column(DateTime, nullable=True)

    # Relationships
    account = relationship("MegaAccount", back_populates="files")

    __table_args__ = (
        UniqueConstraint('l_path', 'l_folder_name', name='unique_local_folder'),
    )


class Setting(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String)
