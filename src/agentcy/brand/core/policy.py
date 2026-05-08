"""Policy engine for autonomous decision-making.

Defines guardrails for what the system can do autonomously vs. what
requires human intervention. Follows "human-over-the-loop" design:
humans set policies, system operates within them.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel, Field

from agentcy.brand.core.config import utc_now
from agentcy.brand.core.decision import Decision, DecisionStatus, DecisionType


class PolicyVerdict(StrEnum):
    """Result of policy evaluation."""

    ALLOW = "allow"  # Execute autonomously
    ESCALATE = "escalate"  # Requires human review
    DENY = "deny"  # Blocked by policy


class PolicyRule(BaseModel):
    """A rule governing autonomous behavior for specific decision types."""

    name: str
    description: str = ""

    # What this rule applies to
    decision_types: list[DecisionType]

    # Thresholds for autonomous approval
    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    min_signals: int = Field(default=1, ge=0)  # Minimum supporting signals

    # Rate limiting
    cooldown_minutes: int = Field(default=0, ge=0)  # Min time between similar actions
    max_per_hour: int | None = Field(default=None, ge=1)  # Rate limit
    max_per_day: int | None = Field(default=None, ge=1)

    # Budget/resource limits (optional, decision-type specific)
    max_budget: float | None = Field(default=None, ge=0)

    # Content rules (for content_publish)
    require_brand_voice_check: bool = False
    max_content_length: int | None = None

    # Escalation conditions (if any match, escalate instead of allow)
    escalate_keywords: list[str] = Field(default_factory=list)  # Keywords that trigger review
    escalate_on_negative_sentiment: bool = False
    escalate_if_mentions_competitor: bool = False


class BrandPolicy(BaseModel):
    """Complete policy configuration for a brand."""

    brand: str
    enabled: bool = True  # Master switch for autonomous operation

    # Default behavior when no rule matches
    default_verdict: PolicyVerdict = PolicyVerdict.ESCALATE

    # Global thresholds (can be overridden by rules)
    global_min_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    global_cooldown_minutes: int = Field(default=5, ge=0)

    # Decision types that are always autonomous (high trust)
    always_allow: list[DecisionType] = Field(default_factory=list)

    # Decision types that always require human (never autonomous)
    always_escalate: list[DecisionType] = Field(default_factory=lambda: [
        DecisionType.BUDGET_ALLOCATION,
        DecisionType.ALERT_ESCALATION,
    ])

    # Decision types that are blocked entirely
    always_deny: list[DecisionType] = Field(default_factory=list)

    # Specific rules (evaluated in order)
    rules: list[PolicyRule] = Field(default_factory=list)

    # Notification settings (for escalations)
    notify_on_escalate: bool = True
    notify_channels: list[str] = Field(default_factory=lambda: ["cli"])  # cli, slack, email

    # Audit settings
    log_all_evaluations: bool = True


class PolicyEvaluation(BaseModel):
    """Result of evaluating a decision against policy."""

    decision_id: str
    brand: str
    verdict: PolicyVerdict
    rule_matched: str | None = None  # Which rule determined the verdict
    reasons: list[str] = Field(default_factory=list)  # Why this verdict
    evaluated_at: datetime = Field(default_factory=utc_now)

    # For ESCALATE verdicts
    escalation_priority: str = "normal"  # low, normal, high, critical

    # For rate limiting
    rate_limit_remaining: int | None = None
    cooldown_until: datetime | None = None


class PolicyEngine:
    """Evaluates decisions against brand policies.

    Usage:
        engine = PolicyEngine()
        policy = engine.load_policy("acme")
        evaluation = engine.evaluate(decision, policy, recent_decisions)

        if evaluation.verdict == PolicyVerdict.ALLOW:
            # Execute autonomously
        elif evaluation.verdict == PolicyVerdict.ESCALATE:
            # Queue for human review
        else:
            # Blocked, log and skip
    """

    def __init__(self):
        self._policy_cache: dict[str, BrandPolicy] = {}

    def load_policy(self, brand: str) -> BrandPolicy:
        """Load policy for a brand from its config."""
        if brand in self._policy_cache:
            return self._policy_cache[brand]

        # Try to load from brand config
        policy = self._load_from_brand_config(brand)
        if policy is None:
            # Return default policy
            policy = BrandPolicy(brand=brand)

        self._policy_cache[brand] = policy
        return policy

    def _load_from_brand_config(self, brand: str) -> BrandPolicy | None:
        """Load policy section from brand.yml."""
        from agentcy.brand.core.config import load_brand_config

        config = load_brand_config(brand)
        if config and "policy" in config:
            policy_data = config["policy"]
            policy_data["brand"] = brand
            return BrandPolicy.model_validate(policy_data)
        return None

    def evaluate(
        self,
        decision: Decision,
        policy: BrandPolicy,
        recent_decisions: list[Decision] | None = None,
    ) -> PolicyEvaluation:
        """Evaluate a decision against the policy.

        Args:
            decision: The decision to evaluate
            policy: The brand's policy configuration
            recent_decisions: Recent decisions for rate limiting checks

        Returns:
            PolicyEvaluation with verdict and reasoning
        """
        reasons: list[str] = []
        recent = recent_decisions or []

        # Master switch check
        if not policy.enabled:
            return PolicyEvaluation(
                decision_id=decision.id,
                brand=decision.brand,
                verdict=PolicyVerdict.ESCALATE,
                reasons=["Autonomous operation disabled for this brand"],
                escalation_priority="low",
            )

        # Check always_deny first
        if decision.type in policy.always_deny:
            return PolicyEvaluation(
                decision_id=decision.id,
                brand=decision.brand,
                verdict=PolicyVerdict.DENY,
                reasons=[f"Decision type {decision.type.value} is blocked by policy"],
            )

        # Check always_escalate
        if decision.type in policy.always_escalate:
            return PolicyEvaluation(
                decision_id=decision.id,
                brand=decision.brand,
                verdict=PolicyVerdict.ESCALATE,
                reasons=[f"Decision type {decision.type.value} always requires human review"],
                escalation_priority="normal",
            )

        # Check always_allow (but still check confidence)
        if decision.type in policy.always_allow:
            if decision.confidence >= policy.global_min_confidence:
                return PolicyEvaluation(
                    decision_id=decision.id,
                    brand=decision.brand,
                    verdict=PolicyVerdict.ALLOW,
                    reasons=[f"Decision type {decision.type.value} is pre-approved"],
                )
            else:
                reasons.append(
                    f"Confidence {decision.confidence:.2f} below threshold "
                    f"{policy.global_min_confidence:.2f}"
                )

        # Find matching rule
        matched_rule: PolicyRule | None = None
        for rule in policy.rules:
            if decision.type in rule.decision_types:
                matched_rule = rule
                break

        if matched_rule:
            return self._evaluate_rule(decision, matched_rule, recent, policy)

        # No rule matched, use default
        if reasons:
            return PolicyEvaluation(
                decision_id=decision.id,
                brand=decision.brand,
                verdict=PolicyVerdict.ESCALATE,
                reasons=reasons,
                escalation_priority="normal",
            )

        return PolicyEvaluation(
            decision_id=decision.id,
            brand=decision.brand,
            verdict=policy.default_verdict,
            reasons=["No matching rule, using default policy"],
            escalation_priority="low" if policy.default_verdict == PolicyVerdict.ESCALATE else None,
        )

    def _evaluate_rule(
        self,
        decision: Decision,
        rule: PolicyRule,
        recent: list[Decision],
        policy: BrandPolicy,
    ) -> PolicyEvaluation:
        """Evaluate decision against a specific rule."""
        escalate_reasons: list[str] = []

        # Confidence check
        if decision.confidence < rule.min_confidence:
            escalate_reasons.append(
                f"Confidence {decision.confidence:.2f} below rule threshold {rule.min_confidence:.2f}"
            )

        # Signal count check
        if len(decision.signals_used) < rule.min_signals:
            escalate_reasons.append(
                f"Only {len(decision.signals_used)} supporting signals, "
                f"rule requires {rule.min_signals}"
            )

        # Rate limiting checks
        if rule.cooldown_minutes > 0:
            cooldown_check = self._check_cooldown(decision, recent, rule.cooldown_minutes)
            if cooldown_check:
                escalate_reasons.append(cooldown_check)

        if rule.max_per_hour:
            hour_count = self._count_recent(decision, recent, minutes=60)
            if hour_count >= rule.max_per_hour:
                escalate_reasons.append(
                    f"Rate limit: {hour_count}/{rule.max_per_hour} per hour reached"
                )

        if rule.max_per_day:
            day_count = self._count_recent(decision, recent, minutes=1440)
            if day_count >= rule.max_per_day:
                escalate_reasons.append(
                    f"Rate limit: {day_count}/{rule.max_per_day} per day reached"
                )

        # Budget check
        if rule.max_budget is not None:
            budget = decision.proposal.get("budget", 0)
            if budget > rule.max_budget:
                escalate_reasons.append(
                    f"Budget ${budget} exceeds limit ${rule.max_budget}"
                )

        # Keyword escalation
        if rule.escalate_keywords:
            content = str(decision.proposal)
            for keyword in rule.escalate_keywords:
                if keyword.lower() in content.lower():
                    escalate_reasons.append(f"Contains escalation keyword: {keyword}")
                    break

        # Competitor mention check
        if rule.escalate_if_mentions_competitor:
            if decision.context.get("mentions_competitor"):
                escalate_reasons.append("Mentions competitor - requires review")

        # Negative sentiment check
        if rule.escalate_on_negative_sentiment:
            if decision.context.get("sentiment", 0) < -0.3:
                escalate_reasons.append("Negative sentiment context - requires review")

        # Determine verdict
        if escalate_reasons:
            priority = "high" if len(escalate_reasons) > 2 else "normal"
            return PolicyEvaluation(
                decision_id=decision.id,
                brand=decision.brand,
                verdict=PolicyVerdict.ESCALATE,
                rule_matched=rule.name,
                reasons=escalate_reasons,
                escalation_priority=priority,
            )

        # All checks passed
        return PolicyEvaluation(
            decision_id=decision.id,
            brand=decision.brand,
            verdict=PolicyVerdict.ALLOW,
            rule_matched=rule.name,
            reasons=[f"Passed all checks for rule: {rule.name}"],
        )

    def _check_cooldown(
        self,
        decision: Decision,
        recent: list[Decision],
        cooldown_minutes: int,
    ) -> str | None:
        """Check if cooldown period has passed since last similar decision."""
        cutoff = utc_now() - timedelta(minutes=cooldown_minutes)

        for r in recent:
            if r.type == decision.type and r.created_at > cutoff:
                if r.status in (DecisionStatus.EXECUTED, DecisionStatus.APPROVED):
                    remaining = (r.created_at + timedelta(minutes=cooldown_minutes)) - utc_now()
                    return f"Cooldown active: {remaining.seconds // 60}m remaining"

        return None

    def _count_recent(
        self,
        decision: Decision,
        recent: list[Decision],
        minutes: int,
    ) -> int:
        """Count recent decisions of the same type."""
        cutoff = utc_now() - timedelta(minutes=minutes)
        return sum(
            1 for r in recent
            if r.type == decision.type
            and r.created_at > cutoff
            and r.status in (DecisionStatus.EXECUTED, DecisionStatus.APPROVED)
        )


# Default policy templates
def default_conservative_policy(brand: str) -> BrandPolicy:
    """Conservative policy - most things require human review."""
    return BrandPolicy(
        brand=brand,
        default_verdict=PolicyVerdict.ESCALATE,
        global_min_confidence=0.8,
        always_allow=[],
        always_escalate=[
            DecisionType.CONTENT_PUBLISH,
            DecisionType.BUDGET_ALLOCATION,
            DecisionType.THREAT_RESPONSE,
            DecisionType.ALERT_ESCALATION,
        ],
    )


def default_balanced_policy(brand: str) -> BrandPolicy:
    """Balanced policy - routine actions autonomous, high-stakes escalate."""
    return BrandPolicy(
        brand=brand,
        default_verdict=PolicyVerdict.ESCALATE,
        global_min_confidence=0.7,
        always_allow=[
            DecisionType.SIGNAL_ACTION,
        ],
        always_escalate=[
            DecisionType.BUDGET_ALLOCATION,
            DecisionType.ALERT_ESCALATION,
        ],
        rules=[
            PolicyRule(
                name="content-auto-publish",
                description="Auto-publish content with high confidence",
                decision_types=[DecisionType.CONTENT_PUBLISH, DecisionType.CONTENT_SCHEDULE],
                min_confidence=0.8,
                min_signals=2,
                max_per_hour=5,
                max_per_day=20,
                cooldown_minutes=10,
                escalate_keywords=["controversial", "political", "urgent"],
            ),
            PolicyRule(
                name="campaign-adjustments",
                description="Auto-adjust campaigns within limits",
                decision_types=[DecisionType.CAMPAIGN_ADJUSTMENT],
                min_confidence=0.75,
                min_signals=3,
                max_budget=100.0,
                cooldown_minutes=30,
            ),
            PolicyRule(
                name="threat-monitoring",
                description="Auto-respond to low-level threats",
                decision_types=[DecisionType.THREAT_RESPONSE],
                min_confidence=0.85,
                min_signals=5,
                cooldown_minutes=60,
                escalate_on_negative_sentiment=True,
            ),
        ],
    )


def default_autonomous_policy(brand: str) -> BrandPolicy:
    """Autonomous policy - system operates with minimal human intervention."""
    return BrandPolicy(
        brand=brand,
        default_verdict=PolicyVerdict.ALLOW,
        global_min_confidence=0.6,
        always_allow=[
            DecisionType.SIGNAL_ACTION,
            DecisionType.CONTENT_SCHEDULE,
            DecisionType.CAMPAIGN_ADJUSTMENT,
        ],
        always_escalate=[
            DecisionType.BUDGET_ALLOCATION,  # Always review spending
        ],
        always_deny=[],
        rules=[
            PolicyRule(
                name="content-auto-publish",
                description="Auto-publish most content",
                decision_types=[DecisionType.CONTENT_PUBLISH],
                min_confidence=0.7,
                min_signals=1,
                max_per_hour=10,
                max_per_day=50,
                cooldown_minutes=5,
            ),
            PolicyRule(
                name="threat-auto-response",
                description="Auto-respond to threats",
                decision_types=[DecisionType.THREAT_RESPONSE],
                min_confidence=0.7,
                min_signals=2,
                cooldown_minutes=15,
            ),
            PolicyRule(
                name="competitor-response",
                description="Auto-respond to competitor moves",
                decision_types=[DecisionType.COMPETITOR_RESPONSE],
                min_confidence=0.75,
                min_signals=2,
                cooldown_minutes=30,
                escalate_if_mentions_competitor=False,  # We expect competitor mentions
            ),
        ],
    )


# Convenience functions
_engine: PolicyEngine | None = None


def get_policy_engine() -> PolicyEngine:
    """Get the default policy engine instance."""
    global _engine
    if _engine is None:
        _engine = PolicyEngine()
    return _engine


def evaluate_decision(
    decision: Decision,
    recent_decisions: list[Decision] | None = None,
) -> PolicyEvaluation:
    """Evaluate a decision using the default engine and brand policy."""
    engine = get_policy_engine()
    policy = engine.load_policy(decision.brand)
    return engine.evaluate(decision, policy, recent_decisions)
