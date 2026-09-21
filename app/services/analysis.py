"""Performance analysis — the core intelligence loop.

Analyzes posts and metrics to produce observations, recommendations, and
scores past recommendations against actual outcomes.
This runs without any AI provider — pure data analysis.
"""
from __future__ import annotations
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median, mean, quantiles
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.core import Post, PostMetric, PostObjective, AccountMetricSnapshot, PlatformAccount
from app.models.manager import ManagerMemory, KnowledgeType, Recommendation
from app.models.content import Hook


OBJECTIVE_SCORING_WEIGHTS: dict[str, dict[str, float]] = {
    "reach": {
        "views": 0.30,
        "reach": 0.25,
        "shares": 0.20,
        "retention_rate": 0.15,
        "completion_rate": 0.10,
    },
    "follower_conversion": {
        "followers_from_post": 0.40,
        "follow_rate": 0.30,
        "saves": 0.15,
        "retention_rate": 0.15,
    },
    "authority": {
        "saves": 0.30,
        "followers_from_post": 0.25,
        "follow_rate": 0.20,
        "retention_rate": 0.15,
        "completion_rate": 0.10,
    },
    "personality": {
        "followers_from_post": 0.25,
        "likes": 0.20,
        "comments_count": 0.20,
        "retention_rate": 0.20,
        "shares": 0.15,
    },
    "community": {
        "comments_count": 0.35,
        "shares": 0.25,
        "likes": 0.20,
        "retention_rate": 0.20,
    },
    "trust": {
        "completion_rate": 0.30,
        "saves": 0.25,
        "followers_from_post": 0.25,
        "retention_rate": 0.20,
    },
    "commercial": {
        "views": 0.20,
        "saves": 0.20,
        "followers_from_post": 0.20,
        "retention_rate": 0.20,
        "completion_rate": 0.20,
    },
    "experimental": {
        "views": 0.25,
        "followers_from_post": 0.25,
        "saves": 0.25,
        "retention_rate": 0.25,
    },
}

AGE_NORMALIZED_HOURS = [2, 24, 72, 168]


async def _get_metric_at_age(post_id: int, target_hours: float, db: AsyncSession) -> PostMetric | None:
    """Get the metric snapshot closest to the target age for fair comparison."""
    result = await db.execute(
        select(PostMetric)
        .where(PostMetric.post_id == post_id)
        .order_by(func.abs(PostMetric.hours_after_publish - target_hours))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _compute_age_normalized_medians(
    post_ids: list[int], target_hours: float, db: AsyncSession
) -> dict[str, float]:
    """Compute median metrics across posts at a specific age."""
    metrics_at_age = []
    for pid in post_ids:
        m = await _get_metric_at_age(pid, target_hours, db)
        if m:
            metrics_at_age.append(m)

    if not metrics_at_age:
        return {}

    def safe_median(values):
        valid = [v for v in values if v is not None]
        return median(valid) if valid else 0

    return {
        "views": safe_median([m.views for m in metrics_at_age]),
        "likes": safe_median([m.likes for m in metrics_at_age]),
        "saves": safe_median([m.saves for m in metrics_at_age]),
        "shares": safe_median([m.shares for m in metrics_at_age]),
        "comments_count": safe_median([m.comments_count for m in metrics_at_age]),
        "followers_from_post": safe_median([m.followers_from_post for m in metrics_at_age]),
        "retention_rate": safe_median([m.retention_rate for m in metrics_at_age]),
        "completion_rate": safe_median([m.completion_rate for m in metrics_at_age]),
    }


async def compute_early_velocity(
    post_id: int, all_post_ids: list[int], db: AsyncSession
) -> dict | None:
    """Compare a post's early performance against age-normalized baselines."""
    velocities = {}
    for hours in AGE_NORMALIZED_HOURS:
        post_metric = await _get_metric_at_age(post_id, hours, db)
        if not post_metric:
            continue

        baseline = await _compute_age_normalized_medians(all_post_ids, hours, db)
        if not baseline:
            continue

        ratios = {}
        for field in ["views", "likes", "saves", "followers_from_post"]:
            post_val = getattr(post_metric, field) or 0
            base_val = baseline.get(field, 0)
            if base_val > 0:
                ratios[field] = round(post_val / base_val, 2)

        velocities[f"+{hours}h"] = {
            "post_values": {
                "views": post_metric.views,
                "likes": post_metric.likes,
                "saves": post_metric.saves,
                "followers_from_post": post_metric.followers_from_post,
            },
            "median_baseline": baseline,
            "vs_median": ratios,
        }

    return velocities if velocities else None


async def analyze_performance(creator_id: int, db: AsyncSession) -> dict:
    """Analyze recent performance with age-normalized comparisons."""
    accounts = (await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.creator_id == creator_id,
            PlatformAccount.is_active == True,
        )
    )).scalars().all()

    account_ids = [a.id for a in accounts]

    posts_result = await db.execute(
        select(Post).where(Post.account_id.in_(account_ids)).order_by(Post.published_at.desc())
    )
    posts = posts_result.scalars().all()
    if not posts:
        return {"error": "No posts to analyze"}

    all_post_ids = [p.id for p in posts]

    baselines_7d = await _compute_age_normalized_medians(all_post_ids, 168, db)

    post_performances = []
    for post in posts:
        metric_7d = await _get_metric_at_age(post.id, 168, db)
        if not metric_7d:
            metric_7d = (await db.execute(
                select(PostMetric)
                .where(PostMetric.post_id == post.id)
                .order_by(PostMetric.captured_at.desc())
                .limit(1)
            )).scalar_one_or_none()

        if not metric_7d:
            continue

        views = metric_7d.views or 0
        saves = metric_7d.saves or 0
        follows = metric_7d.followers_from_post or 0

        perf = {
            "post_id": post.id,
            "caption": (post.caption or "")[:80],
            "objective": post.objective.value if post.objective else None,
            "published_at": post.published_at.isoformat() if post.published_at else None,
            "views": views,
            "likes": metric_7d.likes or 0,
            "saves": saves,
            "shares": metric_7d.shares or 0,
            "comments_count": metric_7d.comments_count or 0,
            "followers_from_post": follows,
            "retention_rate": metric_7d.retention_rate,
            "completion_rate": metric_7d.completion_rate,
            "duration": post.duration_seconds,
            "is_pinned": post.is_pinned,
            "post_type": post.post_type.value if post.post_type else None,
            "comparison_age_hours": metric_7d.hours_after_publish,
        }

        base_views = baselines_7d.get("views", 0)
        base_saves = baselines_7d.get("saves", 0)
        base_follows = baselines_7d.get("followers_from_post", 0)

        perf["views_vs_median"] = round(views / base_views, 2) if base_views > 0 else 0
        perf["saves_vs_median"] = round(saves / base_saves, 2) if base_saves > 0 else 0
        perf["follows_vs_median"] = round(follows / base_follows, 2) if base_follows > 0 else 0
        perf["save_rate"] = round(saves / views, 4) if views > 0 else 0
        perf["follow_rate"] = round(follows / views, 4) if views > 0 else 0

        post_performances.append(perf)

    if not post_performances:
        return {"error": "No metrics available"}

    by_objective = {}
    for p in post_performances:
        obj = p["objective"] or "unclassified"
        by_objective.setdefault(obj, []).append(p)

    objective_analysis = {}
    for obj, obj_posts in by_objective.items():
        def safe_med(key):
            vals = [p[key] for p in obj_posts if p.get(key) is not None]
            return median(vals) if vals else 0

        objective_analysis[obj] = {
            "count": len(obj_posts),
            "median_views": safe_med("views"),
            "median_saves": safe_med("saves"),
            "median_follows": safe_med("followers_from_post"),
            "median_save_rate": safe_med("save_rate"),
            "median_follow_rate": safe_med("follow_rate"),
            "median_retention": safe_med("retention_rate"),
            "median_completion": safe_med("completion_rate"),
        }

    top_by_views = sorted(post_performances, key=lambda p: p["views"], reverse=True)[:3]
    top_by_follows = sorted(post_performances, key=lambda p: p["followers_from_post"], reverse=True)[:3]
    top_by_saves = sorted(post_performances, key=lambda p: p["save_rate"], reverse=True)[:3]

    high_views_low_follows = [
        p for p in post_performances
        if p["views_vs_median"] > 1.5 and p["follows_vs_median"] < 0.8
    ]

    recent_snapshots = (await db.execute(
        select(AccountMetricSnapshot)
        .where(AccountMetricSnapshot.account_id.in_(account_ids))
        .order_by(AccountMetricSnapshot.date.desc())
        .limit(14)
    )).scalars().all()

    follower_deltas = [s.followers_delta for s in recent_snapshots if s.followers_delta is not None]
    avg_daily_growth = mean(follower_deltas) if follower_deltas else 0

    actual_mix = {}
    total = len(post_performances)
    for obj, obj_posts in by_objective.items():
        actual_mix[obj] = round(len(obj_posts) / total, 2)

    return {
        "summary": {
            "total_posts": len(post_performances),
            "baselines_at_7d": baselines_7d,
            "avg_daily_follower_growth": round(avg_daily_growth, 1),
        },
        "top_by_views": [{"post_id": p["post_id"], "caption": p["caption"], "views": p["views"]} for p in top_by_views],
        "top_by_follows": [{"post_id": p["post_id"], "caption": p["caption"], "follows": p["followers_from_post"], "follow_rate": p["follow_rate"]} for p in top_by_follows],
        "top_by_save_rate": [{"post_id": p["post_id"], "caption": p["caption"], "save_rate": p["save_rate"]} for p in top_by_saves],
        "high_views_low_follows": [{"post_id": p["post_id"], "caption": p["caption"], "views": p["views"], "follows": p["followers_from_post"]} for p in high_views_low_follows],
        "objective_analysis": objective_analysis,
        "actual_objective_mix": actual_mix,
        "all_posts": post_performances,
    }


async def create_observation(
    creator_id: int,
    db: AsyncSession,
    category: str,
    statement: str,
    evidence_post_ids: list[int],
    metrics_considered: list[str],
    sample_size: int,
    confidence: float,
) -> ManagerMemory:
    """Store a data-derived observation in the manager's memory."""
    memory = ManagerMemory(
        creator_id=creator_id,
        knowledge_type=KnowledgeType.OBSERVATION,
        category=category,
        statement=statement,
        evidence_post_ids=evidence_post_ids,
        metrics_considered=metrics_considered,
        sample_size=sample_size,
        confidence=confidence,
        is_active=True,
    )
    db.add(memory)
    await db.flush()
    return memory


async def create_recommendation(
    creator_id: int,
    db: AsyncSession,
    agent: str,
    category: str,
    summary: str,
    detail: str | None,
    reasoning: str,
    evidence_post_ids: list[int] | None,
    evidence_memory_ids: list[int] | None,
    metrics_considered: list[str] | None,
    confidence: float,
    priority: int = 5,
    outcome_window_days: int = 7,
) -> Recommendation:
    """Create a recommendation with full provenance."""
    rec = Recommendation(
        creator_id=creator_id,
        agent=agent,
        category=category,
        summary=summary,
        detail=detail,
        reasoning=reasoning,
        evidence_post_ids=evidence_post_ids,
        evidence_memory_ids=evidence_memory_ids,
        metrics_considered=metrics_considered,
        confidence=confidence,
        priority=priority,
        status="pending",
        outcome_window_days=outcome_window_days,
        outcome_measured=False,
    )
    db.add(rec)
    await db.flush()
    return rec


def _get_scoring_weights(objective: str | None) -> dict[str, float]:
    if objective and objective in OBJECTIVE_SCORING_WEIGHTS:
        return OBJECTIVE_SCORING_WEIGHTS[objective]
    return {"views": 0.20, "saves": 0.20, "followers_from_post": 0.20, "retention_rate": 0.20, "completion_rate": 0.20}


async def score_recommendation(
    rec_id: int,
    db: AsyncSession,
    outcome_metrics: dict,
    baseline_metrics: dict,
    objective: str | None = None,
) -> Recommendation:
    """Score a recommendation against actual outcome, weighted by objective."""
    rec = await db.get(Recommendation, rec_id)
    if not rec:
        raise ValueError(f"Recommendation {rec_id} not found")

    weights = _get_scoring_weights(objective)

    weighted_score = 0.0
    total_weight = 0.0
    metric_results = {}

    for metric, weight in weights.items():
        outcome_val = outcome_metrics.get(metric)
        baseline_val = baseline_metrics.get(metric)

        if outcome_val is None or baseline_val is None or baseline_val == 0:
            continue

        total_weight += weight
        ratio = outcome_val / baseline_val
        if ratio >= 1.0:
            metric_score = min(ratio - 1.0, 1.0)
        else:
            metric_score = -(1.0 - ratio)

        weighted_score += metric_score * weight
        metric_results[metric] = {
            "outcome": outcome_val,
            "baseline": baseline_val,
            "ratio": round(ratio, 2),
            "weight": weight,
            "contribution": round(metric_score * weight, 3),
        }

    if total_weight > 0:
        normalized_score = weighted_score / total_weight
        final_score = max(0.0, min(1.0, (normalized_score + 1.0) / 2.0))
    else:
        final_score = 0.5
        normalized_score = 0.0

    if final_score >= 0.65:
        verdict = "successful"
    elif final_score >= 0.45:
        verdict = "mixed"
    else:
        verdict = "unsuccessful"

    scoring_method = f"objective-weighted ({objective or 'default'})"

    rec.outcome_measured = True
    rec.outcome_metrics = outcome_metrics
    rec.outcome_baseline_metrics = baseline_metrics
    rec.outcome_verdict = verdict
    rec.manager_score = round(final_score, 3)
    rec.outcome_explanation = (
        f"Weighted score: {final_score:.3f} using {scoring_method}. "
        f"Metrics: {', '.join(f'{k}: {v['ratio']}x' for k, v in metric_results.items())}. "
        f"Verdict: {verdict}."
    )
    rec.measured_at = datetime.now(timezone.utc)

    await db.flush()
    return rec


async def run_analysis_loop(creator_id: int, db: AsyncSession) -> dict:
    """Run the full manager analysis loop: analyze → observe → recommend."""
    analysis = await analyze_performance(creator_id, db)
    if "error" in analysis:
        return analysis

    observations = []
    recommendations = []

    obj_analysis = analysis["objective_analysis"]
    if "authority" in obj_analysis and "reach" in obj_analysis:
        auth = obj_analysis["authority"]
        reach = obj_analysis["reach"]
        if reach["median_follow_rate"] > 0 and auth["median_follow_rate"] > reach["median_follow_rate"] * 1.3:
            auth_posts = [p["post_id"] for p in analysis["all_posts"] if p["objective"] == "authority"]
            ratio = auth["median_follow_rate"] / reach["median_follow_rate"]
            obs = await create_observation(
                creator_id, db,
                category="content_strategy",
                statement=f"Authority content converts followers at {auth['median_follow_rate']:.4f} rate vs {reach['median_follow_rate']:.4f} for reach content ({ratio:.1f}x higher).",
                evidence_post_ids=auth_posts,
                metrics_considered=["follow_rate", "views", "followers_from_post"],
                sample_size=auth["count"] + reach["count"],
                confidence=min(0.5 + (auth["count"] + reach["count"]) * 0.05, 0.9),
            )
            observations.append({"id": obs.id, "statement": obs.statement})

    if analysis["high_views_low_follows"]:
        post_ids = [p["post_id"] for p in analysis["high_views_low_follows"]]
        obs = await create_observation(
            creator_id, db,
            category="growth",
            statement=f"{len(post_ids)} posts have high views (>1.5x median) but low follower conversion (<0.8x median). These generate reach but not followers.",
            evidence_post_ids=post_ids,
            metrics_considered=["views", "followers_from_post"],
            sample_size=len(post_ids),
            confidence=0.85,
        )
        observations.append({"id": obs.id, "statement": obs.statement})

    top_follows = analysis["top_by_follows"]
    if top_follows:
        best = top_follows[0]
        rec = await create_recommendation(
            creator_id, db,
            agent="growth",
            category="content",
            summary=f"Create content similar to post #{best['post_id']} which has the highest follower conversion rate ({best['follow_rate']:.4f}).",
            detail=f"Post: \"{best['caption']}\" — {best['follows']} followers gained.",
            reasoning=f"This post converts at {best['follow_rate']:.4f} follow rate, highest among all analyzed posts.",
            evidence_post_ids=[best["post_id"]],
            evidence_memory_ids=[o["id"] for o in observations],
            metrics_considered=["follow_rate", "followers_from_post", "views"],
            confidence=0.7,
            priority=1,
        )
        recommendations.append({"id": rec.id, "summary": rec.summary})

    actual_mix = analysis["actual_objective_mix"]
    target_mix = {"reach": 0.35, "follower_conversion": 0.20, "authority": 0.15, "personality": 0.15, "community": 0.10, "experimental": 0.05}
    underrepresented = []
    for obj, target in target_mix.items():
        actual = actual_mix.get(obj, 0)
        if actual < target - 0.1:
            underrepresented.append((obj, target, actual))

    for obj, target, actual in underrepresented:
        rec = await create_recommendation(
            creator_id, db,
            agent="content",
            category="portfolio_balance",
            summary=f"Increase {obj} content — currently {actual:.0%} vs {target:.0%} target.",
            detail=f"The content portfolio is underweight on {obj}. Consider scheduling more {obj}-focused posts this week.",
            reasoning=f"Current mix has {obj} at {actual:.0%}, target is {target:.0%}. Rebalancing maintains brand diversity.",
            evidence_post_ids=None,
            evidence_memory_ids=None,
            metrics_considered=["objective_mix"],
            confidence=0.8,
            priority=3,
        )
        recommendations.append({"id": rec.id, "summary": rec.summary})

    await db.commit()

    return {
        "analysis_summary": analysis["summary"],
        "observations_created": observations,
        "recommendations_created": recommendations,
        "objective_analysis": analysis["objective_analysis"],
        "actual_mix": actual_mix,
    }


# ---------------------------------------------------------------------------
# Content clustering — keyword patterns from captions only
# ---------------------------------------------------------------------------

CONTENT_CLUSTERS: dict[str, list[str]] = {
    "calisthenics": ["calisthenics", "calisthenic", "pullup", "pull up", "pushup", "push up",
                     "muscle up", "muscleup", "dip", "handstand", "planche", "front lever"],
    "workout_routine": ["workout", "routine", "exercise", "training", "warm up", "core day",
                        "leg day", "chest day", "arm day"],
    "physique": ["muscle", "abs", "physique", "body", "shredded", "gains", "bulk", "lean",
                 "bodygoals", "transformation"],
    "lifestyle": ["therapy", "alive", "life", "morning", "sunrise", "vlog", "day in",
                  "grwm", "lifestyle"],
    "motivation": ["never stop", "no excuses", "mindset", "discipline", "grind", "hustle",
                   "level", "unlock"],
    "trend_viral": ["viral", "fyp", "trending", "xyzbca", "parati", "foryou", "trend",
                    "eclipse", "drama", "capcut"],
    "military_outdoor": ["military", "outdoor", "nature", "park", "beach", "street"],
    "collaboration": ["teamwork", "team", "partner", "friend", "bro", "crew"],
}


def _classify_content(caption: str) -> list[str]:
    lower = caption.lower()
    clusters = []
    for cluster, keywords in CONTENT_CLUSTERS.items():
        if any(kw in lower for kw in keywords):
            clusters.append(cluster)
    return clusters or ["uncategorised"]


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    f = int(k)
    c = f + 1
    if c >= len(s):
        return s[f]
    return s[f] + (k - f) * (s[c] - s[f])


def _detect_outliers_iqr(values: list[float], multiplier: float = 1.5) -> tuple[float, list[int]]:
    if len(values) < 4:
        return 0, []
    q1 = _percentile(values, 25)
    q3 = _percentile(values, 75)
    iqr = q3 - q1
    upper = q3 + multiplier * iqr
    outlier_indices = [i for i, v in enumerate(values) if v > upper]
    return upper, outlier_indices


async def run_full_analytics(account_id: int, db: AsyncSession) -> dict:
    """Comprehensive first-run analytics for a real account.

    Pure data analysis — no AI calls. Produces facts, observations, and
    hypotheses with evidence post IDs. Handles outlier detection so the
    breakout post doesn't distort baselines.
    """
    account = await db.get(PlatformAccount, account_id)
    if not account:
        return {"error": f"Account {account_id} not found"}

    rows = (await db.execute(
        select(Post, PostMetric)
        .join(PostMetric, PostMetric.post_id == Post.id)
        .where(Post.account_id == account_id)
        .order_by(Post.published_at)
    )).all()

    if not rows:
        return {"error": "No posts with metrics"}

    posts_data = []
    for post, metric in rows:
        views = metric.views or 0
        likes = metric.likes or 0
        comments = metric.comments_count or 0
        shares = metric.shares or 0
        engagement = likes + comments + shares
        posts_data.append({
            "post_id": post.id,
            "platform_post_id": post.platform_post_id,
            "caption": post.caption or "",
            "published_at": post.published_at,
            "duration": post.duration_seconds,
            "views": views,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "engagement": engagement,
            "like_rate": round(likes / views * 100, 2) if views > 0 else 0,
            "comment_rate": round(comments / views * 100, 3) if views > 0 else 0,
            "share_rate": round(shares / views * 100, 3) if views > 0 else 0,
            "engagement_rate": round(engagement / views * 100, 2) if views > 0 else 0,
            "clusters": _classify_content(post.caption or ""),
        })

    all_views = [p["views"] for p in posts_data]
    outlier_threshold, outlier_indices = _detect_outliers_iqr(all_views)
    outlier_ids = [posts_data[i]["post_id"] for i in outlier_indices]
    outlier_posts = [posts_data[i] for i in outlier_indices]
    normal_posts = [p for i, p in enumerate(posts_data) if i not in outlier_indices]

    normal_views = [p["views"] for p in normal_posts]
    normal_likes = [p["likes"] for p in normal_posts]
    normal_engagements = [p["engagement"] for p in normal_posts]

    total_views = sum(all_views)
    outlier_views = sum(p["views"] for p in outlier_posts)

    # --- 1. Baseline performance ---
    baseline = {
        "total_posts": len(posts_data),
        "total_views": total_views,
        "mean_views_all": round(mean(all_views)),
        "mean_views_normal": round(mean(normal_views)) if normal_views else 0,
        "median_views": round(median(all_views)),
        "median_views_normal": round(median(normal_views)) if normal_views else 0,
        "p25_views": round(_percentile(normal_views, 25)),
        "p75_views": round(_percentile(normal_views, 75)),
        "p90_views": round(_percentile(normal_views, 90)),
        "outlier_count": len(outlier_posts),
        "outlier_threshold": round(outlier_threshold),
        "outlier_share_of_views": round(outlier_views / total_views * 100, 1) if total_views > 0 else 0,
    }

    # --- 2. Outlier detail ---
    outlier_detail = []
    for p in outlier_posts:
        outlier_detail.append({
            "post_id": p["post_id"],
            "caption": p["caption"][:80],
            "views": p["views"],
            "like_rate": p["like_rate"],
            "share_rate": p["share_rate"],
            "share_of_total_views": round(p["views"] / total_views * 100, 1),
        })

    # --- 3. Per-post rates (weighted vs unweighted) ---
    total_likes = sum(p["likes"] for p in posts_data)
    total_comments = sum(p["comments"] for p in posts_data)
    total_shares = sum(p["shares"] for p in posts_data)
    total_engagement = sum(p["engagement"] for p in posts_data)

    weighted_rates = {
        "like_rate": round(total_likes / total_views * 100, 2) if total_views > 0 else 0,
        "comment_rate": round(total_comments / total_views * 100, 3) if total_views > 0 else 0,
        "share_rate": round(total_shares / total_views * 100, 3) if total_views > 0 else 0,
        "engagement_rate": round(total_engagement / total_views * 100, 2) if total_views > 0 else 0,
        "note": "Weighted by views — breakout posts dominate these ratios",
    }

    unweighted_rates = {
        "like_rate": round(mean([p["like_rate"] for p in posts_data]), 2),
        "comment_rate": round(mean([p["comment_rate"] for p in posts_data]), 3),
        "share_rate": round(mean([p["share_rate"] for p in posts_data]), 3),
        "engagement_rate": round(mean([p["engagement_rate"] for p in posts_data]), 2),
        "note": "Unweighted mean of per-post rates — treats every post equally",
    }

    normal_unweighted_rates = {
        "like_rate": round(mean([p["like_rate"] for p in normal_posts]), 2) if normal_posts else 0,
        "comment_rate": round(mean([p["comment_rate"] for p in normal_posts]), 3) if normal_posts else 0,
        "share_rate": round(mean([p["share_rate"] for p in normal_posts]), 3) if normal_posts else 0,
        "engagement_rate": round(mean([p["engagement_rate"] for p in normal_posts]), 2) if normal_posts else 0,
        "note": "Unweighted mean excluding outliers — the true baseline engagement",
    }

    # --- 4. Top posts by different dimensions ---
    top_by_reach = sorted(posts_data, key=lambda p: p["views"], reverse=True)[:5]
    top_by_engagement_rate = sorted(
        [p for p in posts_data if p["views"] >= 50],
        key=lambda p: p["engagement_rate"], reverse=True
    )[:5]
    top_by_shares = sorted(posts_data, key=lambda p: p["shares"], reverse=True)[:5]
    top_by_comments = sorted(posts_data, key=lambda p: p["comments"], reverse=True)[:5]
    top_by_like_rate = sorted(
        [p for p in posts_data if p["views"] >= 50],
        key=lambda p: p["like_rate"], reverse=True
    )[:5]

    def _top_summary(items, metric_key, label):
        return [
            {"post_id": p["post_id"], "caption": p["caption"][:60], label: p[metric_key], "views": p["views"]}
            for p in items
        ]

    tops = {
        "reach": _top_summary(top_by_reach, "views", "views"),
        "engagement_rate": _top_summary(top_by_engagement_rate, "engagement_rate", "engagement_rate"),
        "shares_virality": _top_summary(top_by_shares, "shares", "shares"),
        "comments_community": _top_summary(top_by_comments, "comments", "comments"),
        "like_rate": _top_summary(top_by_like_rate, "like_rate", "like_rate"),
    }

    # --- 5. Content clustering ---
    cluster_stats: dict[str, dict] = {}
    for cluster_name in CONTENT_CLUSTERS:
        cluster_posts = [p for p in posts_data if cluster_name in p["clusters"]]
        if not cluster_posts:
            continue
        cv = [p["views"] for p in cluster_posts]
        cl = [p["like_rate"] for p in cluster_posts]
        ce = [p["engagement_rate"] for p in cluster_posts]
        cluster_normal = [p for p in cluster_posts if p["post_id"] not in outlier_ids]
        cv_normal = [p["views"] for p in cluster_normal] if cluster_normal else cv

        cluster_stats[cluster_name] = {
            "count": len(cluster_posts),
            "median_views": round(median(cv)),
            "median_views_excl_outliers": round(median(cv_normal)) if cv_normal else 0,
            "mean_like_rate": round(mean(cl), 2),
            "mean_engagement_rate": round(mean(ce), 2),
            "top_post_views": max(cv),
            "above_median_count": sum(1 for v in cv_normal if v > baseline["median_views_normal"]),
            "post_ids": [p["post_id"] for p in cluster_posts],
        }

    cluster_stats_sorted = dict(
        sorted(cluster_stats.items(), key=lambda x: x[1]["count"], reverse=True)
    )

    # --- 6. Posting evolution ---
    by_quarter: dict[str, list] = defaultdict(list)
    for p in posts_data:
        if p["published_at"]:
            q = f"{p['published_at'].year}-Q{(p['published_at'].month - 1) // 3 + 1}"
            by_quarter[q].append(p)

    evolution = {}
    for q in sorted(by_quarter.keys()):
        qposts = by_quarter[q]
        qv = [p["views"] for p in qposts]
        qv_normal = [p["views"] for p in qposts if p["post_id"] not in outlier_ids]
        evolution[q] = {
            "posts": len(qposts),
            "median_views": round(median(qv)),
            "median_views_excl_outliers": round(median(qv_normal)) if qv_normal else 0,
            "mean_like_rate": round(mean([p["like_rate"] for p in qposts]), 2),
            "mean_engagement_rate": round(mean([p["engagement_rate"] for p in qposts]), 2),
            "total_views": sum(qv),
        }

    recent_cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    recent = [p for p in normal_posts if p["published_at"] and p["published_at"] >= recent_cutoff]
    older = [p for p in normal_posts if p["published_at"] and p["published_at"] < recent_cutoff]

    recent_vs_older = None
    if recent and older:
        recent_vs_older = {
            "recent_count": len(recent),
            "older_count": len(older),
            "recent_median_views": round(median([p["views"] for p in recent])),
            "older_median_views": round(median([p["views"] for p in older])),
            "recent_mean_like_rate": round(mean([p["like_rate"] for p in recent]), 2),
            "older_mean_like_rate": round(mean([p["like_rate"] for p in older]), 2),
            "recent_mean_engagement": round(mean([p["engagement_rate"] for p in recent]), 2),
            "older_mean_engagement": round(mean([p["engagement_rate"] for p in older]), 2),
        }

    # --- 7. Repeatability analysis ---
    repeatability = {}
    for cluster_name, stats in cluster_stats.items():
        if stats["count"] < 3:
            continue
        cluster_posts = [p for p in normal_posts if cluster_name in p["clusters"]]
        if len(cluster_posts) < 3:
            continue
        cv = sorted([p["views"] for p in cluster_posts])
        above_median = stats["above_median_count"]
        consistency = above_median / stats["count"] if stats["count"] > 0 else 0
        floor_views = cv[0] if cv else 0
        ceiling_views = cv[-1] if cv else 0
        repeatability[cluster_name] = {
            "posts": stats["count"],
            "above_median_pct": round(consistency * 100, 1),
            "floor_views": floor_views,
            "ceiling_views": ceiling_views,
            "median_views": stats["median_views_excl_outliers"],
            "repeatable": consistency >= 0.4 and stats["count"] >= 3,
        }

    # --- 8. Store observations (idempotent — upsert by identity key) ---
    observations = []

    async def _obs(knowledge_type, category, statement, evidence_ids, metrics, sample, confidence):
        identity_key = f"{account.creator_id}:{account_id}:{category}:{knowledge_type.value}"
        if evidence_ids:
            identity_key += f":{sorted(set(evidence_ids[:5]))}"

        existing = (await db.execute(
            select(ManagerMemory).where(
                ManagerMemory.creator_id == account.creator_id,
                ManagerMemory.category == category,
                ManagerMemory.knowledge_type == knowledge_type,
                ManagerMemory.is_active == True,
            )
        )).scalars().all()

        evidence_set = set(evidence_ids or [])
        matched = None
        for m in existing:
            existing_set = set(m.evidence_post_ids or [])
            if evidence_set and existing_set and len(evidence_set & existing_set) / max(len(evidence_set | existing_set), 1) > 0.7:
                matched = m
                break

        if matched:
            matched.statement = statement
            matched.evidence_post_ids = evidence_ids
            matched.metrics_considered = metrics
            matched.sample_size = sample
            matched.confidence = confidence
            await db.flush()
            observations.append({"id": matched.id, "type": knowledge_type.value, "updated": True, "statement": statement})
            return matched

        mem = ManagerMemory(
            creator_id=account.creator_id,
            knowledge_type=knowledge_type,
            category=category,
            statement=statement,
            evidence_post_ids=evidence_ids,
            metrics_considered=metrics,
            sample_size=sample,
            confidence=confidence,
            is_active=True,
        )
        db.add(mem)
        await db.flush()
        observations.append({"id": mem.id, "type": knowledge_type.value, "statement": statement})
        return mem

    # FACT: baseline performance
    await _obs(
        KnowledgeType.FACT, "baseline",
        f"Across {len(posts_data)} TikTok posts, median views = {baseline['median_views_normal']}, "
        f"P25 = {baseline['p25_views']}, P75 = {baseline['p75_views']}, P90 = {baseline['p90_views']}. "
        f"Mean (excl outliers) = {baseline['mean_views_normal']}.",
        [p["post_id"] for p in posts_data],
        ["views"], len(posts_data), 0.95,
    )

    # FACT: outlier identification
    if outlier_posts:
        for op in outlier_posts:
            await _obs(
                KnowledgeType.FACT, "outlier",
                f"Post {op['post_id']} ({op['caption'][:50]}...) is a statistical outlier with "
                f"{op['views']:,} views ({round(op['views'] / total_views * 100, 1)}% of all account views). "
                f"IQR threshold = {round(outlier_threshold):,} views.",
                [op["post_id"]], ["views"], len(posts_data), 0.95,
            )

    # FACT: weighted vs unweighted rates
    await _obs(
        KnowledgeType.FACT, "engagement_rates",
        f"Unweighted mean engagement rate (excl outliers) = {normal_unweighted_rates['engagement_rate']}%. "
        f"View-weighted rate = {weighted_rates['engagement_rate']}%. "
        f"The difference reflects outlier distortion — use unweighted for baseline.",
        [p["post_id"] for p in posts_data],
        ["like_rate", "comment_rate", "share_rate", "engagement_rate"],
        len(posts_data), 0.95,
    )

    # OBSERVATION: breakout share rate anomaly
    for op in outlier_posts:
        if op["share_rate"] > 0 and op["like_rate"] > 0:
            await _obs(
                KnowledgeType.OBSERVATION, "virality",
                f"Breakout post {op['post_id']} has {op['like_rate']}% like rate but only "
                f"{op['share_rate']}% share rate. Yet it achieved {op['views']:,} views vs "
                f"~{baseline['median_views_normal']} median. Something beyond likes drove distribution — "
                f"possibly algorithmic boost from watch time, hook, or trending topic.",
                [op["post_id"]], ["like_rate", "share_rate", "views"], 1, 0.7,
            )

    # OBSERVATION: content cluster performance
    for cluster_name, stats in cluster_stats.items():
        if stats["count"] >= 3 and stats["median_views_excl_outliers"] > baseline["median_views_normal"] * 1.2:
            await _obs(
                KnowledgeType.OBSERVATION, "content_clustering",
                f"'{cluster_name}' content ({stats['count']} posts) has median views "
                f"{stats['median_views_excl_outliers']} vs account median {baseline['median_views_normal']} "
                f"({round(stats['median_views_excl_outliers'] / baseline['median_views_normal'], 1)}x). "
                f"Mean engagement rate: {stats['mean_engagement_rate']}%.",
                stats["post_ids"][:10], ["views", "engagement_rate"],
                stats["count"], min(0.6 + stats["count"] * 0.03, 0.85),
            )

    # OBSERVATION: recent vs older performance
    if recent_vs_older:
        direction = "up" if recent_vs_older["recent_median_views"] > recent_vs_older["older_median_views"] else "down"
        ratio = round(recent_vs_older["recent_median_views"] / max(recent_vs_older["older_median_views"], 1), 2)
        await _obs(
            KnowledgeType.OBSERVATION, "trend",
            f"Recent 90 days ({recent_vs_older['recent_count']} posts): median views "
            f"{recent_vs_older['recent_median_views']} vs older ({recent_vs_older['older_count']} posts): "
            f"{recent_vs_older['older_median_views']} — {direction} {ratio}x. "
            f"Like rate: {recent_vs_older['recent_mean_like_rate']}% recent vs "
            f"{recent_vs_older['older_mean_like_rate']}% older.",
            [p["post_id"] for p in recent[:5]] + [p["post_id"] for p in older[:5]],
            ["views", "like_rate"],
            recent_vs_older["recent_count"] + recent_vs_older["older_count"],
            0.75,
        )

    # OBSERVATION: repeatability
    for cluster_name, rep in repeatability.items():
        if rep["repeatable"]:
            await _obs(
                KnowledgeType.OBSERVATION, "repeatability",
                f"'{cluster_name}' is a repeatable format: {rep['posts']} posts, "
                f"{rep['above_median_pct']}% above account median. "
                f"Floor: {rep['floor_views']} views, ceiling: {rep['ceiling_views']}, "
                f"median: {rep['median_views']}.",
                cluster_stats[cluster_name]["post_ids"][:10],
                ["views"], rep["posts"], 0.7,
            )

    # HYPOTHESIS: what made the breakout distributable
    for op in outlier_posts:
        normal_share_rate = normal_unweighted_rates["share_rate"]
        if op["share_rate"] < normal_share_rate * 1.5:
            await _obs(
                KnowledgeType.HYPOTHESIS, "virality_mechanism",
                f"Breakout post {op['post_id']} did not have an unusually high share rate "
                f"({op['share_rate']}% vs {normal_share_rate}% baseline). Distribution was likely "
                f"driven by algorithmic factors (watch time, completion rate, hook effectiveness) "
                f"rather than peer sharing. Video content analysis needed to identify the specific driver.",
                [op["post_id"]], ["share_rate", "views"], 1, 0.5,
            )

    await db.commit()

    return {
        "baseline": baseline,
        "outliers": outlier_detail,
        "rates": {
            "weighted": weighted_rates,
            "unweighted": unweighted_rates,
            "normal_unweighted": normal_unweighted_rates,
        },
        "top_posts": tops,
        "content_clusters": cluster_stats_sorted,
        "evolution": evolution,
        "recent_vs_older": recent_vs_older,
        "repeatability": repeatability,
        "observations": observations,
    }


# ---------------------------------------------------------------------------
# Instagram-specific analytics — likes-based, format-segmented
# ---------------------------------------------------------------------------

async def run_ig_analytics(account_id: int, db: AsyncSession) -> dict:
    """Instagram analytics segmented by format.

    Uses likes as primary metric since the basic media endpoint does not return
    views/reach/saves. Does not treat missing metrics as zero — marks them absent.
    """
    account = await db.get(PlatformAccount, account_id)
    if not account:
        return {"error": f"Account {account_id} not found"}

    rows = (await db.execute(
        select(Post, PostMetric)
        .join(PostMetric, PostMetric.post_id == Post.id)
        .where(Post.account_id == account_id)
        .order_by(Post.published_at)
    )).all()

    if not rows:
        return {"error": "No posts with metrics"}

    posts_data = []
    for post, metric in rows:
        likes = metric.likes or 0
        comments = metric.comments_count or 0
        posts_data.append({
            "post_id": post.id,
            "platform_post_id": post.platform_post_id,
            "caption": post.caption or "",
            "published_at": post.published_at,
            "post_type": post.post_type.value if post.post_type else "unknown",
            "likes": likes,
            "comments": comments,
            "clusters": _classify_content(post.caption or ""),
        })

    # --- 1. Format-segmented baselines ---
    FORMAT_NAMES = {"reel": "REEL", "carousel": "CAROUSEL", "feed": "FEED"}
    format_stats = {}
    for fmt_key, fmt_label in FORMAT_NAMES.items():
        fmt_posts = [p for p in posts_data if p["post_type"] == fmt_key]
        if not fmt_posts:
            continue
        likes_list = sorted([p["likes"] for p in fmt_posts])
        outlier_thresh, outlier_idx = _detect_outliers_iqr(likes_list)
        normal = [p for i, p in enumerate(fmt_posts) if i not in outlier_idx]
        normal_likes = [p["likes"] for p in normal] if normal else likes_list

        format_stats[fmt_label] = {
            "count": len(fmt_posts),
            "median_likes": round(median(likes_list)),
            "mean_likes": round(mean(likes_list)),
            "p25_likes": round(_percentile(likes_list, 25)),
            "p75_likes": round(_percentile(likes_list, 75)),
            "p90_likes": round(_percentile(likes_list, 90)),
            "median_likes_excl_outliers": round(median(normal_likes)),
            "outlier_count": len(outlier_idx),
            "outlier_threshold": round(outlier_thresh),
            "top_post_likes": max(likes_list),
            "post_ids": [p["post_id"] for p in fmt_posts],
        }

    # --- 2. Overall baseline ---
    all_likes = [p["likes"] for p in posts_data]
    outlier_thresh_all, outlier_idx_all = _detect_outliers_iqr(all_likes)
    normal_all = [p for i, p in enumerate(posts_data) if i not in outlier_idx_all]
    normal_all_likes = [p["likes"] for p in normal_all] if normal_all else all_likes

    baseline = {
        "total_posts": len(posts_data),
        "total_likes": sum(all_likes),
        "median_likes": round(median(all_likes)),
        "median_likes_excl_outliers": round(median(normal_all_likes)),
        "mean_likes": round(mean(all_likes)),
        "p25_likes": round(_percentile(all_likes, 25)),
        "p75_likes": round(_percentile(all_likes, 75)),
        "p90_likes": round(_percentile(all_likes, 90)),
        "primary_metric": "likes",
        "missing_metrics": ["views", "reach", "saves", "shares"],
        "note": "Views/reach/saves require instagram_manage_insights on per-media queries",
    }

    # --- 3. Top posts by likes per format ---
    tops_by_format = {}
    for fmt_label, stats in format_stats.items():
        fmt_posts = [p for p in posts_data if p["post_type"] == fmt_label.lower()]
        top = sorted(fmt_posts, key=lambda p: p["likes"], reverse=True)[:5]
        tops_by_format[fmt_label] = [
            {"post_id": p["post_id"], "caption": p["caption"][:60], "likes": p["likes"]}
            for p in top
        ]

    # --- 4. Content clustering ---
    cluster_stats: dict[str, dict] = {}
    for cluster_name in CONTENT_CLUSTERS:
        cluster_posts = [p for p in posts_data if cluster_name in p["clusters"]]
        if not cluster_posts:
            continue
        cl = [p["likes"] for p in cluster_posts]
        by_fmt = defaultdict(list)
        for p in cluster_posts:
            by_fmt[p["post_type"]].append(p["likes"])

        cluster_stats[cluster_name] = {
            "count": len(cluster_posts),
            "median_likes": round(median(cl)),
            "mean_likes": round(mean(cl)),
            "by_format": {
                fmt: {"count": len(likes), "median_likes": round(median(likes))}
                for fmt, likes in by_fmt.items() if likes
            },
            "above_overall_median": sum(1 for v in cl if v > baseline["median_likes"]),
            "post_ids": [p["post_id"] for p in cluster_posts],
        }

    cluster_stats = dict(sorted(cluster_stats.items(), key=lambda x: x[1]["count"], reverse=True))

    # --- 5. Posting evolution ---
    by_quarter: dict[str, list] = defaultdict(list)
    for p in posts_data:
        if p["published_at"]:
            q = f"{p['published_at'].year}-Q{(p['published_at'].month - 1) // 3 + 1}"
            by_quarter[q].append(p)

    evolution = {}
    for q in sorted(by_quarter.keys()):
        qposts = by_quarter[q]
        ql = [p["likes"] for p in qposts]
        by_fmt = defaultdict(list)
        for p in qposts:
            by_fmt[p["post_type"]].append(p["likes"])
        evolution[q] = {
            "posts": len(qposts),
            "median_likes": round(median(ql)),
            "total_likes": sum(ql),
            "by_format": {
                fmt: {"count": len(likes), "median_likes": round(median(likes))}
                for fmt, likes in by_fmt.items() if likes
            },
        }

    # --- 6. Recent vs older ---
    recent_cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    recent = [p for p in posts_data if p["published_at"] and p["published_at"] >= recent_cutoff]
    older = [p for p in posts_data if p["published_at"] and p["published_at"] < recent_cutoff]

    recent_vs_older = None
    if recent and older:
        recent_vs_older = {
            "recent_count": len(recent),
            "older_count": len(older),
            "recent_median_likes": round(median([p["likes"] for p in recent])),
            "older_median_likes": round(median([p["likes"] for p in older])),
        }

    # --- 7. Repeatability ---
    repeatability = {}
    for cluster_name, stats in cluster_stats.items():
        if stats["count"] < 3:
            continue
        cl = sorted([p["likes"] for p in posts_data if cluster_name in p["clusters"]])
        above = stats["above_overall_median"]
        consistency = above / stats["count"] if stats["count"] > 0 else 0
        repeatability[cluster_name] = {
            "posts": stats["count"],
            "above_median_pct": round(consistency * 100, 1),
            "floor_likes": cl[0] if cl else 0,
            "ceiling_likes": cl[-1] if cl else 0,
            "median_likes": stats["median_likes"],
            "repeatable": consistency >= 0.4 and stats["count"] >= 3,
        }

    # --- 8. Store observations (idempotent) ---
    observations = []

    async def _obs(knowledge_type, category, statement, evidence_ids, metrics, sample, confidence):
        existing = (await db.execute(
            select(ManagerMemory).where(
                ManagerMemory.creator_id == account.creator_id,
                ManagerMemory.category == category,
                ManagerMemory.knowledge_type == knowledge_type,
                ManagerMemory.is_active == True,
            )
        )).scalars().all()

        evidence_set = set(evidence_ids or [])
        matched = None
        for m in existing:
            existing_set = set(m.evidence_post_ids or [])
            if evidence_set and existing_set and len(evidence_set & existing_set) / max(len(evidence_set | existing_set), 1) > 0.7:
                matched = m
                break

        if matched:
            matched.statement = statement
            matched.evidence_post_ids = evidence_ids
            matched.metrics_considered = metrics
            matched.sample_size = sample
            matched.confidence = confidence
            await db.flush()
            observations.append({"id": matched.id, "type": knowledge_type.value, "updated": True, "statement": statement})
            return matched

        mem = ManagerMemory(
            creator_id=account.creator_id,
            knowledge_type=knowledge_type,
            category=category,
            statement=statement,
            evidence_post_ids=evidence_ids,
            metrics_considered=metrics,
            sample_size=sample,
            confidence=confidence,
            is_active=True,
        )
        db.add(mem)
        await db.flush()
        observations.append({"id": mem.id, "type": knowledge_type.value, "statement": statement})
        return mem

    # FACT: Instagram comments data unreliable
    await _obs(
        KnowledgeType.FACT, "ig_data_quality",
        "Instagram comments_count returns 0 for most posts via the basic media API. "
        "Do not interpret zero comments as low engagement — the data is missing, not zero. "
        "Comment analysis requires per-media insights permission.",
        None, ["comments_count"], len(posts_data), 0.95,
    )

    # FACT: baseline by format
    for fmt_label, stats in format_stats.items():
        await _obs(
            KnowledgeType.FACT, f"ig_baseline_{fmt_label.lower()}",
            f"Instagram {fmt_label}: {stats['count']} posts, median likes = {stats['median_likes']}, "
            f"P25 = {stats['p25_likes']}, P75 = {stats['p75_likes']}, P90 = {stats['p90_likes']}. "
            f"Mean = {stats['mean_likes']}.",
            stats["post_ids"][:10], ["likes"], stats["count"], 0.95,
        )

    # OBSERVATION: format comparison (without causal claim)
    if len(format_stats) >= 2:
        sorted_formats = sorted(format_stats.items(), key=lambda x: x[1]["median_likes"], reverse=True)
        best_fmt, best_stats = sorted_formats[0]
        worst_fmt, worst_stats = sorted_formats[-1]
        if best_stats["median_likes"] > worst_stats["median_likes"] * 1.5:
            await _obs(
                KnowledgeType.OBSERVATION, "ig_format_difference",
                f"Instagram {best_fmt} ({best_stats['count']} posts, median {best_stats['median_likes']} likes) "
                f"outperforms {worst_fmt} ({worst_stats['count']} posts, median {worst_stats['median_likes']} likes) "
                f"by {round(best_stats['median_likes'] / max(worst_stats['median_likes'], 1), 1)}x on likes. "
                f"Without reach/views data, this could reflect different distribution mechanics rather than "
                f"content quality. Reels may reach more non-followers while carousels engage existing audience.",
                best_stats["post_ids"][:5] + worst_stats["post_ids"][:5],
                ["likes"], best_stats["count"] + worst_stats["count"], 0.7,
            )

    # OBSERVATION: content clusters on IG
    for cluster_name, stats in cluster_stats.items():
        if stats["count"] >= 3 and stats["median_likes"] > baseline["median_likes"] * 1.2:
            await _obs(
                KnowledgeType.OBSERVATION, f"ig_cluster_{cluster_name}",
                f"Instagram '{cluster_name}' content ({stats['count']} posts) has median "
                f"{stats['median_likes']} likes vs account median {baseline['median_likes']} "
                f"({round(stats['median_likes'] / max(baseline['median_likes'], 1), 1)}x).",
                stats["post_ids"][:10], ["likes"], stats["count"],
                min(0.6 + stats["count"] * 0.03, 0.85),
            )

    # OBSERVATION: recent vs older
    if recent_vs_older:
        direction = "up" if recent_vs_older["recent_median_likes"] > recent_vs_older["older_median_likes"] else "down"
        ratio = round(recent_vs_older["recent_median_likes"] / max(recent_vs_older["older_median_likes"], 1), 2)
        await _obs(
            KnowledgeType.OBSERVATION, "ig_trend",
            f"Instagram recent 90 days ({recent_vs_older['recent_count']} posts): median "
            f"{recent_vs_older['recent_median_likes']} likes vs older ({recent_vs_older['older_count']} "
            f"posts): {recent_vs_older['older_median_likes']} — {direction} {ratio}x.",
            [p["post_id"] for p in recent[:5]] + [p["post_id"] for p in older[:5]],
            ["likes"], recent_vs_older["recent_count"] + recent_vs_older["older_count"], 0.75,
        )

    # OBSERVATION: repeatability
    for cluster_name, rep in repeatability.items():
        if rep["repeatable"]:
            await _obs(
                KnowledgeType.OBSERVATION, f"ig_repeat_{cluster_name}",
                f"Instagram '{cluster_name}' is repeatable: {rep['posts']} posts, "
                f"{rep['above_median_pct']}% above account median. "
                f"Floor: {rep['floor_likes']} likes, ceiling: {rep['ceiling_likes']}, "
                f"median: {rep['median_likes']}.",
                cluster_stats[cluster_name]["post_ids"][:10],
                ["likes"], rep["posts"], 0.7,
            )

    await db.commit()

    return {
        "baseline": baseline,
        "format_stats": format_stats,
        "tops_by_format": tops_by_format,
        "content_clusters": cluster_stats,
        "evolution": evolution,
        "recent_vs_older": recent_vs_older,
        "repeatability": repeatability,
        "observations": observations,
    }


# ---------------------------------------------------------------------------
# Cross-platform comparison — content themes, not raw metrics
# ---------------------------------------------------------------------------

async def run_cross_platform_analysis(creator_id: int, db: AsyncSession) -> dict:
    """Compare content themes across platforms.

    Compares which content clusters perform above/below median on each platform.
    Does NOT compare raw metrics cross-platform (likes != views).
    """
    accounts = (await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.creator_id == creator_id,
            PlatformAccount.is_active == True,
        )
    )).scalars().all()

    real_accounts = [a for a in accounts if "mock" not in (a.platform_user_id or "")]
    if len(real_accounts) < 2:
        return {"error": "Need at least 2 real platform accounts for cross-platform analysis"}

    platform_data: dict[str, dict] = {}

    for account in real_accounts:
        rows = (await db.execute(
            select(Post, PostMetric)
            .join(PostMetric, PostMetric.post_id == Post.id)
            .where(Post.account_id == account.id)
            .order_by(Post.published_at)
        )).all()

        if not rows:
            continue

        from app.models.core import Platform as PlatformEnum
        is_tiktok = account.platform == PlatformEnum.TIKTOK
        metric_name = "views" if is_tiktok else "likes"
        posts = []
        for post, metric in rows:
            val = (metric.views or 0) if is_tiktok else (metric.likes or 0)
            posts.append({
                "post_id": post.id,
                "caption": post.caption or "",
                "published_at": post.published_at,
                "metric_value": val,
                "clusters": _classify_content(post.caption or ""),
            })

        all_values = [p["metric_value"] for p in posts]
        _, outlier_idx = _detect_outliers_iqr(all_values)
        normal = [p for i, p in enumerate(posts) if i not in outlier_idx]
        normal_values = [p["metric_value"] for p in normal] if normal else all_values
        account_median = median(normal_values) if normal_values else 0

        cluster_performance: dict[str, dict] = {}
        for cluster_name in CONTENT_CLUSTERS:
            cposts = [p for p in normal if cluster_name in p["clusters"]]
            if len(cposts) < 2:
                continue
            cv = [p["metric_value"] for p in cposts]
            cluster_med = median(cv)
            ratio = round(cluster_med / account_median, 2) if account_median > 0 else 0
            cluster_performance[cluster_name] = {
                "count": len(cposts),
                "median": round(cluster_med),
                "vs_account_median": ratio,
                "above_median_pct": round(sum(1 for v in cv if v > account_median) / len(cv) * 100, 1),
            }

        platform_key = f"{account.platform.value}_{account.username}"
        platform_data[platform_key] = {
            "platform": account.platform.value,
            "username": account.username,
            "metric": metric_name,
            "total_posts": len(posts),
            "account_median": round(account_median),
            "cluster_performance": cluster_performance,
        }

    # --- Cross-platform theme comparison ---
    platforms = list(platform_data.keys())
    if len(platforms) < 2:
        return {"error": "Insufficient data for comparison", "platforms": platform_data}

    shared_clusters = set()
    for cluster_name in CONTENT_CLUSTERS:
        present_in = [pk for pk, pd in platform_data.items() if cluster_name in pd["cluster_performance"]]
        if len(present_in) >= 2:
            shared_clusters.add(cluster_name)

    theme_comparison = {}
    for cluster_name in sorted(shared_clusters):
        entries = {}
        for pk, pd in platform_data.items():
            cp = pd["cluster_performance"].get(cluster_name)
            if cp:
                entries[pk] = {
                    "platform": pd["platform"],
                    "metric": pd["metric"],
                    "count": cp["count"],
                    "vs_median": cp["vs_account_median"],
                    "above_median_pct": cp["above_median_pct"],
                }
        theme_comparison[cluster_name] = entries

    # Identify themes that outperform on BOTH platforms
    cross_platform_winners = []
    cross_platform_divergent = []
    for cluster_name, entries in theme_comparison.items():
        ratios = {pk: e["vs_median"] for pk, e in entries.items()}
        all_above = all(r >= 1.1 for r in ratios.values())
        mixed = any(r >= 1.2 for r in ratios.values()) and any(r <= 0.9 for r in ratios.values())
        if all_above:
            cross_platform_winners.append({
                "cluster": cluster_name,
                "platforms": {pk: r for pk, r in ratios.items()},
            })
        elif mixed:
            cross_platform_divergent.append({
                "cluster": cluster_name,
                "platforms": {pk: r for pk, r in ratios.items()},
            })

    # --- Store cross-platform observations ---
    observations = []

    async def _xobs(knowledge_type, category, statement, evidence_ids, metrics, sample, confidence):
        existing = (await db.execute(
            select(ManagerMemory).where(
                ManagerMemory.creator_id == creator_id,
                ManagerMemory.category == category,
                ManagerMemory.knowledge_type == knowledge_type,
                ManagerMemory.is_active == True,
            )
        )).scalars().all()

        evidence_set = set(evidence_ids or [])
        for m in existing:
            existing_set = set(m.evidence_post_ids or [])
            if evidence_set and existing_set and len(evidence_set & existing_set) / max(len(evidence_set | existing_set), 1) > 0.7:
                m.statement = statement
                m.evidence_post_ids = evidence_ids
                m.metrics_considered = metrics
                m.sample_size = sample
                m.confidence = confidence
                await db.flush()
                observations.append({"id": m.id, "type": knowledge_type.value, "updated": True, "statement": statement})
                return m

        mem = ManagerMemory(
            creator_id=creator_id,
            knowledge_type=knowledge_type,
            category=category,
            statement=statement,
            evidence_post_ids=evidence_ids,
            metrics_considered=metrics,
            sample_size=sample,
            confidence=confidence,
            is_active=True,
        )
        db.add(mem)
        await db.flush()
        observations.append({"id": mem.id, "type": knowledge_type.value, "statement": statement})
        return mem

    for winner in cross_platform_winners:
        ratios_str = ", ".join(
            f"{pk.split('_')[0]} {r}x" for pk, r in winner["platforms"].items()
        )
        total_sample = sum(
            theme_comparison[winner["cluster"]][pk]["count"]
            for pk in winner["platforms"]
        )
        await _xobs(
            KnowledgeType.OBSERVATION, f"xplat_winner_{winner['cluster']}",
            f"'{winner['cluster']}' content outperforms account median on BOTH platforms "
            f"({ratios_str}). This is stronger evidence than single-platform data.",
            None, ["views", "likes"], total_sample,
            min(0.7 + total_sample * 0.01, 0.9),
        )

    for div in cross_platform_divergent:
        ratios_str = ", ".join(
            f"{pk.split('_')[0]} {r}x" for pk, r in div["platforms"].items()
        )
        await _xobs(
            KnowledgeType.OBSERVATION, f"xplat_diverge_{div['cluster']}",
            f"'{div['cluster']}' content performs differently across platforms ({ratios_str}). "
            f"This may reflect platform-specific audience preferences or distribution mechanics.",
            None, ["views", "likes"], 0, 0.6,
        )

    await db.commit()

    return {
        "platforms": platform_data,
        "shared_clusters": sorted(shared_clusters),
        "theme_comparison": theme_comparison,
        "cross_platform_winners": cross_platform_winners,
        "cross_platform_divergent": cross_platform_divergent,
        "observations": observations,
    }
