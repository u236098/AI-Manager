"""Import sample data so the manager loop can run without OAuth.

Creates fake-but-realistic posts with metrics for Kobby's accounts,
simulating ~3 weeks of posting history across Instagram and TikTok.
"""
import asyncio
import random
from datetime import datetime, timedelta, timezone, date
from sqlalchemy import select
from app.database import async_session
from app.models.core import (
    Creator, PlatformAccount, Platform, Post, PostType, PostObjective,
    PostMetric, AccountMetricSnapshot,
)
from app.models.content import Hook, ContentIdea, IdeaStatus


POSTS_DATA = [
    {"caption": "30 pull-ups no rest 💪", "type": PostType.REEL, "obj": PostObjective.REACH, "dur": 15, "base_views": 81000, "base_likes": 6200, "base_saves": 890, "base_follows": 142, "hook": "Watch me do 30 pull-ups without stopping"},
    {"caption": "POV: engineering student at the gym", "type": PostType.REEL, "obj": PostObjective.PERSONALITY, "dur": 18, "base_views": 34000, "base_likes": 2800, "base_saves": 310, "base_follows": 87, "hook": "POV: you study computer engineering but the gym is your real degree"},
    {"caption": "If you're stuck at 10 pull-ups, try this", "type": PostType.REEL, "obj": PostObjective.AUTHORITY, "dur": 22, "base_views": 52000, "base_likes": 4100, "base_saves": 1200, "base_follows": 198, "hook": "If you can do 10 pull-ups but can't get past 15, try this"},
    {"caption": "Barcelona gym tour 🇪🇸", "type": PostType.REEL, "obj": PostObjective.PERSONALITY, "dur": 24, "base_views": 28000, "base_likes": 2100, "base_saves": 420, "base_follows": 65, "hook": "Rating Barcelona's best gyms"},
    {"caption": "From 0 to muscle up in 6 months", "type": PostType.REEL, "obj": PostObjective.REACH, "dur": 20, "base_views": 120000, "base_likes": 9800, "base_saves": 2100, "base_follows": 310, "hook": "6 months ago I couldn't do a single muscle up"},
    {"caption": "Full day of eating as a student athlete", "type": PostType.REEL, "obj": PostObjective.COMMUNITY, "dur": 30, "base_views": 22000, "base_likes": 1800, "base_saves": 580, "base_follows": 43, "hook": "What I eat in a day as a broke engineering student"},
    {"caption": "This exercise changed my back", "type": PostType.REEL, "obj": PostObjective.AUTHORITY, "dur": 16, "base_views": 45000, "base_likes": 3600, "base_saves": 950, "base_follows": 156, "hook": "Nobody tells you about this exercise for back width"},
    {"caption": "Beach workout Barcelona", "type": PostType.REEL, "obj": PostObjective.REACH, "dur": 12, "base_views": 67000, "base_likes": 5100, "base_saves": 380, "base_follows": 95, "hook": "Beach calisthenics hits different"},
    {"caption": "My calisthenics progression 2024-2026", "type": PostType.REEL, "obj": PostObjective.TRUST, "dur": 25, "base_views": 38000, "base_likes": 3200, "base_saves": 720, "base_follows": 110, "hook": "2 years of calisthenics — was it worth it?"},
    {"caption": "Gym vs calisthenics — honest comparison", "type": PostType.REEL, "obj": PostObjective.AUTHORITY, "dur": 28, "base_views": 41000, "base_likes": 3400, "base_saves": 880, "base_follows": 130, "hook": "I've done both for 2 years. Here's the truth"},
    {"caption": "Quick arm workout at home 🏠", "type": PostType.REEL, "obj": PostObjective.REACH, "dur": 14, "base_views": 19000, "base_likes": 1400, "base_saves": 620, "base_follows": 38, "hook": "3 exercises, no equipment, bigger arms"},
    {"caption": "Study + gym routine that actually works", "type": PostType.REEL, "obj": PostObjective.PERSONALITY, "dur": 21, "base_views": 31000, "base_likes": 2500, "base_saves": 710, "base_follows": 89, "hook": "How I balance engineering and the gym"},
    {"caption": "Pull-up challenge with my friend", "type": PostType.REEL, "obj": PostObjective.COMMUNITY, "dur": 19, "base_views": 55000, "base_likes": 4300, "base_saves": 290, "base_follows": 72, "hook": "Can my friend beat me at pull-ups?"},
    {"caption": "What nobody tells you about getting lean", "type": PostType.REEL, "obj": PostObjective.AUTHORITY, "dur": 26, "base_views": 36000, "base_likes": 2900, "base_saves": 1050, "base_follows": 168, "hook": "I've been trying to get below 12% body fat and here's what I learned"},
    {"caption": "Exploring Gothic Quarter + sunset training", "type": PostType.REEL, "obj": PostObjective.PERSONALITY, "dur": 23, "base_views": 15000, "base_likes": 1200, "base_saves": 180, "base_follows": 29, "hook": "Barcelona has the best outdoor training spots"},
]


def _vary(base: int, pct: float = 0.3) -> int:
    return max(0, int(base * random.uniform(1 - pct, 1 + pct)))


async def import_data():
    async with async_session() as db:
        creator = (await db.execute(select(Creator).where(Creator.id == 1))).scalar_one()

        ig = PlatformAccount(
            creator_id=1, platform=Platform.INSTAGRAM,
            platform_user_id="ig_mock_001", username="kobbycooper",
            display_name="Kobby Cooper",
        )
        tt = PlatformAccount(
            creator_id=1, platform=Platform.TIKTOK,
            platform_user_id="tt_mock_001", username="fittokboy",
            display_name="Kobby Cooper",
        )
        db.add_all([ig, tt])
        await db.flush()

        now = datetime.now(timezone.utc)
        base_date = now - timedelta(days=21)
        all_posts = []

        for i, pd in enumerate(POSTS_DATA):
            pub = base_date + timedelta(days=i * 1.4, hours=random.randint(8, 20))
            is_tiktok = i % 3 == 0
            account = tt if is_tiktok else ig

            post = Post(
                account_id=account.id,
                platform_post_id=f"mock_{account.platform.value}_{i+1:03d}",
                post_type=PostType.TIKTOK_VIDEO if is_tiktok else pd["type"],
                objective=pd["obj"],
                caption=pd["caption"],
                duration_seconds=pd["dur"],
                published_at=pub,
                is_pinned=(i in [0, 4, 6]),
            )
            db.add(post)
            await db.flush()
            all_posts.append((post, pd))

            tt_mult = 1.8 if is_tiktok else 1.0
            for hours in [0.5, 2, 8, 24, 72, 168]:
                age_mult = min(hours / 24, 1.0) * 0.6 + 0.4
                metric = PostMetric(
                    post_id=post.id,
                    captured_at=pub + timedelta(hours=hours),
                    hours_after_publish=hours,
                    views=int(_vary(pd["base_views"]) * age_mult * tt_mult),
                    likes=int(_vary(pd["base_likes"]) * age_mult * tt_mult),
                    comments_count=_vary(int(pd["base_likes"] * 0.08)),
                    shares=_vary(int(pd["base_views"] * 0.02)),
                    saves=int(_vary(pd["base_saves"]) * age_mult),
                    reach=int(_vary(pd["base_views"]) * 0.85 * age_mult * tt_mult),
                    followers_from_post=int(_vary(pd["base_follows"]) * age_mult),
                    retention_rate=random.uniform(0.3, 0.7),
                    completion_rate=random.uniform(0.15, 0.55),
                )
                db.add(metric)

            hook = Hook(
                creator_id=1, post_id=post.id, text=pd["hook"],
                hook_type="question" if "?" in pd["hook"] else "statement",
                retention_1s=random.uniform(0.6, 0.9),
                retention_3s=random.uniform(0.4, 0.8),
                performance_vs_median=pd["base_views"] / 40000,
            )
            db.add(hook)

        base_followers = 8200
        for day_offset in range(22):
            d = (base_date + timedelta(days=day_offset)).date()
            delta = random.randint(20, 120)
            base_followers += delta
            for account in [ig, tt]:
                mult = 0.6 if account.platform == Platform.TIKTOK else 1.0
                snapshot = AccountMetricSnapshot(
                    account_id=account.id, date=d,
                    followers=int(base_followers * mult),
                    followers_delta=int(delta * mult),
                    total_reach=_vary(50000),
                    profile_visits=_vary(800),
                    profile_to_follow_rate=random.uniform(0.03, 0.08),
                )
                db.add(snapshot)

        ideas = [
            ContentIdea(
                creator_id=1, status=IdeaStatus.BACKLOG,
                title="How I went from 10 pull-ups to 30",
                concept="Progressive overload tutorial using Kobby's actual journey",
                why="Previous 3 pull-up videos generated 2.4x median saves",
                objective=PostObjective.FOLLOWER_CONVERSION,
                ai_score=8.5,
                source="growth_agent",
            ),
            ContentIdea(
                creator_id=1, status=IdeaStatus.BACKLOG,
                title="Day in the life: engineering student in Barcelona",
                concept="Full day vlog — classes, gym, Barcelona evening",
                why="Personality content is underrepresented (15% vs 20% target)",
                objective=PostObjective.PERSONALITY,
                ai_score=7.2,
                source="content_agent",
            ),
            ContentIdea(
                creator_id=1, status=IdeaStatus.BACKLOG,
                title="3 calisthenics mistakes I made for a year",
                concept="Educational: common calisthenics mistakes with demonstrations",
                why="Educational authority content converts followers at 2.1x rate",
                objective=PostObjective.AUTHORITY,
                ai_score=7.8,
                source="content_agent",
            ),
        ]
        db.add_all(ideas)

        await db.commit()
        print(f"Imported {len(all_posts)} posts with metrics across Instagram and TikTok")
        print(f"Created {len(ideas)} content ideas")
        print("22 days of account metric snapshots for both platforms")
        print("Hook library populated from all posts")


if __name__ == "__main__":
    asyncio.run(import_data())
