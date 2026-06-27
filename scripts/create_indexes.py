"""
Create database indexes for optimal query performance.
Run this after table creation.
"""
import asyncio
from sqlalchemy import text
from core.database import engine


async def create_indexes():
    """Create all required database indexes."""
    indexes = [
        # Student table
        "CREATE INDEX IF NOT EXISTS idx_students_email ON students(email)",
        "CREATE INDEX IF NOT EXISTS idx_students_created_at ON students(created_at)",

        # Student progress
        "CREATE INDEX IF NOT EXISTS idx_progress_student ON student_progress(student_id)",

        # Topic mastery
        "CREATE INDEX IF NOT EXISTS idx_topic_mastery_student ON student_topic_mastery_orm(student_id)",
        "CREATE INDEX IF NOT EXISTS idx_topic_mastery_state ON student_topic_mastery_orm(state)",

        # Study plans
        "CREATE INDEX IF NOT EXISTS idx_study_plans_student ON study_plans(student_id)",
        "CREATE INDEX IF NOT EXISTS idx_study_plans_date ON study_plans(date)",

        # Notes
        "CREATE INDEX IF NOT EXISTS idx_notes_student ON notes(student_id)",
        "CREATE INDEX IF NOT EXISTS idx_notes_topic ON notes(topic_id)",

        # Mock tests
        "CREATE INDEX IF NOT EXISTS idx_mock_tests_student ON mock_test_attempts(student_id)",

        # Revision records
        "CREATE INDEX IF NOT EXISTS idx_revision_student ON revision_records(student_id)",
        "CREATE INDEX IF NOT EXISTS idx_revision_due ON revision_records(next_revision_at)",
    ]

    async with engine.begin() as conn:
        for idx_sql in indexes:
            try:
                await conn.execute(text(idx_sql))
                print(f"✅ Created: {idx_sql[:60]}...")
            except Exception as exc:
                print(f"⚠️  Skipped: {exc}")

    print("\n✅ All indexes created!")


if __name__ == "__main__":
    asyncio.run(create_indexes())
