"""Create all database tables."""
import asyncio
from core.database import engine, Base

# Import ALL models so SQLAlchemy registers them
from domain.students.models import (
    Student, StudentPreference, StudentProgress, Topic,
    StudyPlan, Note, MockTestAttempt, RevisionRecord,
    StudentTopicMastery, student_topic_mastery
)

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("All tables created!")

    # Verify
    from sqlalchemy import text
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
        )
        tables = [row[0] for row in result]
        print(f"Tables ({len(tables)}): {tables}")

asyncio.run(create_tables())
