"""
创建数据库表
"""
from sqlmodel import SQLModel
from write_agent.models import (
    WritingStyle,
    Material,
    RewriteRecord,
    ReviewRecord,
    ManualEditRecord,
    GitHubTrendingSnapshot,
    GitHubTrendingItem,
    GitHubRepoEnrichmentCache,
    ObservabilityEvent,
)
from write_agent.core import get_settings
from write_agent.core.database import create_app_engine
from write_agent.services.rag_service import ensure_pgvector_schema

settings = get_settings()

if __name__ == "__main__":
    # 创建引擎
    engine = create_app_engine(settings.database_url, echo=True)

    # 创建所有表
    SQLModel.metadata.create_all(engine)
    ensure_pgvector_schema(settings.database_url)

    print("✅ 数据库表创建完成")
