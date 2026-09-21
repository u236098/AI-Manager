"""Seed Kobby Cooper as the first managed creator with initial brand strategy."""
import asyncio
from sqlalchemy import select
from app.database import async_session
from app.models.core import Creator
from app.models.brand import BrandStrategy
from app.models.manager import ManagerConfig, AutonomyLevel


async def seed():
    async with async_session() as db:
        existing = await db.execute(select(Creator).where(Creator.name == "Kobby Cooper"))
        if existing.scalar_one_or_none():
            print("Kobby Cooper already exists. Skipping seed.")
            return

        creator = Creator(name="Kobby Cooper")
        db.add(creator)
        await db.flush()

        strategy = BrandStrategy(
            creator_id=creator.id,
            primary_identity="Fitness/lifestyle creator",
            supporting_identities=[
                "Computer Engineering student",
                "Barcelona lifestyle",
                "Calisthenics",
                "Travel/social life",
            ],
            personality_traits=["confident", "friendly", "playful", "ambitious"],
            brand_goal="People follow Kobby rather than merely following fitness content.",
            audience_primary_age="18-30",
            audience_primary_interests=["fitness", "physique", "lifestyle", "self-improvement"],
            audience_primary_geography=["Spain", "US", "UK"],
            private_topics=[],
            style_boundaries=[],
            sponsorship_exclusions=[],
            current_phase="growth",
            strategic_priorities=[
                "Build recognisable personal brand across platforms",
                "Grow qualified audience (followers who follow Kobby, not just fitness)",
                "Test content formats to build creator playbook",
                "Establish content consistency",
            ],
        )
        db.add(strategy)

        config = ManagerConfig(
            creator_id=creator.id,
            autonomy_level=AutonomyLevel.ADVISER,
        )
        db.add(config)

        await db.commit()
        print(f"Seeded creator: Kobby Cooper (id={creator.id})")
        print("Brand strategy and manager config created.")


if __name__ == "__main__":
    asyncio.run(seed())
