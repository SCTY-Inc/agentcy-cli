# brandOS Signal Strategy

Strategic positioning and phased implementation for brand signal intelligence.

---

## Executive Summary

**The Gap**: Paid platforms (Brandwatch, Meltwater, AlphaSense) excel at collecting and displaying signals. They stop at "here's what happened" — leaving users to manually interpret, decide, and act.

**Our Position**: brandOS goes further — from signal detection through to proposed actions, human approval, execution, and outcome tracking. We own the interpretation-to-action layer.

**One-liner**: *"Brandwatch shows you what happened. brandOS tells you what to do about it."*

---

## Positioning

### Market Map

```
INTERPRETATION DEPTH
      ^
      |
 High |    [brandOS]  ← Agent synthesis + action proposals
      |
  Mid |         [Brandwatch, Meltwater, Sprout]  ← Dashboards
      |
  Low |    [GDELT, NewsAPI, Finnhub]  ← Raw feeds
      |
      +-------------------------------------------------> Cost
           Free       $100s/mo     $1000s/mo    Enterprise
```

### What We Do

| Capability | Differentiation |
|------------|-----------------|
| Multi-source fusion | News + filings + jobs + trends in one schema |
| Weak signal detection | Surface anomalies before they trend |
| Agent synthesis | LLM agents produce analysis, not charts |
| Action proposals | "Based on X, we recommend Y" with rationale |
| Human approval gates | High-stakes decisions require sign-off |
| Decision audit trail | What was proposed, approved, executed, outcomes |
| Outcome learning | Results improve future recommendations |

### What We Don't Do

| Skip | Reason |
|------|--------|
| Historical archives | Incumbents' moat; we focus on real-time + forward |
| Dashboard UI | CLI-first, API-second; UI is distraction |
| Enterprise compliance | SOC2/GDPR expensive; target SMB first |
| Social publishing at scale | Hootsuite owns this; we integrate |
| Influencer databases | Different product |
| Ad campaign management | Out of scope |

---

## Signal Taxonomy

### Sources

```
SIGNAL SOURCES
├── MARKET (what the market does)
│   ├── Search trends ─────── Google Trends, pytrends
│   ├── Stock movements ───── yfinance, Finnhub
│   ├── Economic indicators ─ FRED
│   └── Consumer spending ─── (future: alt data)
│
├── COMPETITIVE (what competitors do)
│   ├── SEC filings ───────── edgartools (8-K, 10-K, 10-Q)
│   ├── Patent filings ────── USPTO PatentsView
│   ├── Job postings ──────── LinkedIn, Greenhouse boards
│   ├── Press releases ────── news APIs
│   └── Product changes ───── pricing, features tracking
│
├── REPUTATION (what people say)
│   ├── News mentions ─────── GDELT, Google News RSS
│   ├── Social mentions ───── Reddit (PRAW), Twitter
│   ├── Reviews ───────────── G2, Capterra, app stores
│   └── Forums ────────────── technical communities
│
└── WEAK SIGNALS (early indicators)
    ├── Anomalous mention velocity
    ├── Sentiment shift patterns
    ├── Cross-source correlation spikes
    └── Emerging entity co-occurrence
```

### Value Matrix

| Signal Type | Detection | Actionability | Competition |
|-------------|-----------|---------------|-------------|
| News mentions | Easy | Medium | Crowded |
| Social sentiment | Easy | Medium | Crowded |
| SEC filings | Medium | High | Moderate |
| Patent filings | Medium | High | **Low** |
| Job postings | Medium | High | **Low** |
| Search trends | Easy | Medium | Moderate |
| Weak signals | Hard | Very High | **Empty** |

**Focus areas**: SEC filings, patent filings, job postings, weak signal detection.

---

## Implementation Phases

### Phase 0: Foundation (Weeks 1-2)

**Goal**: Solidify signal schema and storage.

#### Schema Additions

Extend existing `Signal` model:

```python
class Signal(BaseModel):
    # Existing fields from ROADMAP.md...

    # Weak signal detection
    velocity: float | None         # mentions/hour delta
    novelty_score: float | None    # how "new" is this
    correlation_ids: list[str]     # related signal IDs

    # Outcome tracking
    action_taken: str | None
    outcome: dict | None
```

#### Storage

- SQLite for MVP
- Alembic migrations
- 90-day hot retention, archive to Parquet

#### CLI Baseline

```bash
brandos signals sources list
brandos signals fetch --brand acme
brandos signals show <id>
brandos signals stats --brand acme
```

**Deliverable**: Signal storage + existing Google News provider working.

---

### Phase 1: Source Expansion (Weeks 3-5)

**Goal**: Add high-value, low-competition sources.

#### 1.1 SEC EDGAR

```python
# signals/providers/sec_edgar.py
from edgartools import Company

def fetch_competitor_filings(ticker: str, form_types: list[str], since_days: int) -> list[Signal]:
    company = Company(ticker)
    filings = company.get_filings(form=form_types)
    # Extract key sections, summarize
    ...
```

Extract:
- Risk factor changes (10-K section 1A diffs)
- Material events (8-K items)
- Revenue segment changes
- Executive departures

#### 1.2 GDELT

```python
# signals/providers/gdelt.py
import gdelt

gd = gdelt.gdelt(version=2)

def fetch_gdelt_mentions(query: str, timespan: str = "1d") -> list[Signal]:
    results = gd.Search(query, table='gkg', coverage=True)
    ...
```

Extract:
- Global mention volume
- Tone/sentiment by region
- Source diversity
- Theme taxonomy

#### 1.3 Job Postings

Track competitor hiring patterns:
- Role distribution (engineering vs sales)
- Seniority levels
- Location expansion
- Tech stack mentions

**Deliverable**: 3 new providers feeding unified schema.

---

### Phase 2: Enrichment (Weeks 6-8)

**Goal**: Transform raw signals into scored intelligence.

#### 2.1 Domain-Specific Sentiment

```python
# signals/enrichment/sentiment.py
from transformers import AutoModelForSequenceClassification

class FinancialSentiment:
    """FinBERT for financial text, VADER for social."""

    def __init__(self):
        self.model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")

    def score(self, text: str, source: str) -> float:
        if source in ["sec_edgar", "finnhub", "news"]:
            return self._finbert_score(text)
        return self._vader_score(text)
```

#### 2.2 Entity Extraction

```python
# signals/enrichment/entities.py
import spacy

nlp = spacy.load("en_core_web_sm")

def extract_entities(text: str) -> dict:
    doc = nlp(text)
    return {
        "organizations": [e.text for e in doc.ents if e.label_ == "ORG"],
        "people": [e.text for e in doc.ents if e.label_ == "PERSON"],
        "products": [...]  # Custom NER
    }
```

#### 2.3 Velocity Tracking

```python
# signals/enrichment/velocity.py
def calculate_velocity(brand: str, window_hours: int = 24) -> dict:
    recent = get_signals(brand, since=f"{window_hours}h")
    baseline = get_average_rate(brand, days=30)

    return {
        "current_rate": len(recent) / window_hours,
        "baseline_rate": baseline,
        "velocity_ratio": len(recent) / window_hours / baseline,
        "is_anomalous": (len(recent) / window_hours) > baseline * 2
    }
```

**Deliverable**: All signals have sentiment, entities, velocity scores.

---

### Phase 3: Weak Signal Detection (Weeks 9-12)

**Goal**: The differentiator. Surface signals before they're obvious.

#### 3.1 Anomaly Detection

Statistical first (no training):

```python
# signals/detection/anomaly.py
from scipy import stats

def detect_anomalies(signals: list[Signal], threshold: float = 2.5) -> list[Signal]:
    velocities = [s.velocity for s in signals]
    z_scores = stats.zscore(velocities)
    return [s for s, z in zip(signals, z_scores) if abs(z) > threshold]
```

Then Isolation Forest for multivariate:

```python
from pyod.models.iforest import IForest

def detect_multivariate(features: np.ndarray) -> np.ndarray:
    clf = IForest(contamination=0.05)
    clf.fit(features)
    return clf.predict(features)
```

#### 3.2 Changepoint Detection

```python
# signals/detection/changepoint.py
import ruptures as rpt

def detect_changepoints(series: np.ndarray, min_size: int = 5) -> list[int]:
    algo = rpt.Pelt(model="rbf", min_size=min_size)
    algo.fit(series)
    return algo.predict(pen=10)
```

#### 3.3 Cross-Source Correlation

The key insight: when multiple independent sources mention the same thing.

```python
# signals/detection/correlation.py
def detect_emergence(entity: str, window_hours: int = 48) -> dict:
    signals = get_signals_mentioning(entity, since=f"{window_hours}h")
    sources = set(s.source for s in signals)

    # 3+ independent sources = emerging signal
    return {
        "entity": entity,
        "sources": list(sources),
        "is_emerging": len(sources) >= 3,
        "confidence": min(1.0, len(sources) / 5)
    }
```

**Deliverable**: Automated weak signal alerts with confidence scores.

---

### Phase 4: Agent Synthesis (Weeks 13-16)

**Goal**: Connect detection to agent architecture from `AGENTS.md`.

#### 4.1 Signal Digest Agent

```python
# agents/digest.py
from pydantic_ai import Agent

digest_agent = Agent(
    'anthropic:claude-sonnet-4-20250514',
    system_prompt="""Brand intelligence analyst. Given signals, produce:
    1. Executive summary (3 bullets)
    2. Key threats
    3. Opportunities
    4. Recommended actions with rationale
    Cite signal IDs.""",
    result_type=SignalDigest
)
```

#### 4.2 Threat Assessor

Extends existing `ThreatAssessor` from AGENTS.md with signal detection:

```python
# agents/threat.py
threat_agent = Agent(
    'anthropic:claude-sonnet-4-20250514',
    system_prompt="""Assess competitive threats. Focus on:
    - Competitor launches
    - Pricing changes
    - Executive moves
    - Patent filings
    - Hiring patterns

    Rate: LOW / MEDIUM / HIGH / CRITICAL
    Cite evidence.""",
    result_type=ThreatAssessment
)
```

#### 4.3 Action Proposer

The differentiator — from analysis to recommendation:

```python
# agents/action.py
action_agent = Agent(
    'anthropic:claude-sonnet-4-20250514',
    system_prompt="""Propose specific actions from signal analysis.
    Actions must be:
    - Concrete (not "monitor situation")
    - Time-bound
    - Assigned to function (content, product, PR, legal)

    Format each:
    - Action: [specific]
    - Rationale: [citing signals]
    - Urgency: LOW/MEDIUM/HIGH
    - Owner: [function]""",
    result_type=ActionProposal
)
```

**Deliverable**: Agent pipeline producing actionable recommendations.

---

### Phase 5: Decision Loop (Weeks 17-20)

**Goal**: Close the loop with approval and learning.

#### 5.1 Rejection Learning

Extend existing approval workflow:

```python
# workflows/approval.py
def on_enter_rejected(self, reason: str):
    log_decision(action=self.action, status="rejected", reason=reason)

    # Improve future proposals
    update_action_model(
        action_type=self.action.type,
        was_approved=False,
        reason=reason
    )
```

#### 5.2 Outcome Tracking

```python
# core/outcome.py
class ActionOutcome(BaseModel):
    action_id: str
    executed_at: datetime
    metrics_before: dict
    metrics_after: dict
    success_score: float
    learnings: str
```

#### 5.3 Feedback Loop

Use outcomes to improve relevance:

```python
def update_relevance_weights(outcomes: list[ActionOutcome]):
    for outcome in outcomes:
        signals = get_signals_for_action(outcome.action_id)
        delta = 0.1 if outcome.success_score > 0.5 else -0.1
        for signal in signals:
            update_source_weight(signal.source, delta)
```

**Deliverable**: Full decision loop with learning.

---

## Success Metrics

### Phase 0-1

- [ ] 5+ signal sources integrated
- [ ] 1000+ signals/day capacity
- [ ] < 5 min latency source → storage

### Phase 2-3

- [ ] Sentiment accuracy > 80%
- [ ] Anomaly precision > 70%
- [ ] Weak signals surfaced 24-48h before mainstream

### Phase 4-5

- [ ] Recommendation acceptance > 60%
- [ ] Signal → action latency < 1 hour
- [ ] Outcome tracking coverage > 90%
- [ ] Relevance scores improve over time

---

## Resources

### Open-Source Tools

| Tool | Purpose | Link |
|------|---------|------|
| GDELT | Global news, 15-min updates | [gdeltproject.org](https://gdeltproject.org) |
| edgartools | SEC filing analysis | [github.com/dgunning/edgartools](https://github.com/dgunning/edgartools) |
| FinBERT | Financial sentiment | [github.com/ProsusAI/finBERT](https://github.com/ProsusAI/finBERT) |
| FinGPT | Financial LLM | [github.com/AI4Finance-Foundation/FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) |
| pyod | Anomaly detection | [github.com/yzhao062/pyod](https://github.com/yzhao062/pyod) |
| ruptures | Changepoint detection | [github.com/deepcharles/ruptures](https://github.com/deepcharles/ruptures) |
| spaCy | NLP/NER | [spacy.io](https://spacy.io) |
| PRAW | Reddit API | [praw.readthedocs.io](https://praw.readthedocs.io) |

### Research

| Topic | Source |
|-------|--------|
| Weak signal mining | [Springer: Systematic Literature Review](https://link.springer.com/article/10.1007/s11573-018-0898-4) |
| Organizational sensemaking | [ScienceDirect: Digital Strategic Agility](https://www.sciencedirect.com/science/article/pii/S0378720625000333) |
| Brand health metrics | [Ehrenberg-Bass Institute](https://marketingscience.info) |
| Multi-source aggregation | [arXiv: AIMM-X](https://arxiv.org/abs/2601.15304) |

### Paid Landscape (for reference)

| Platform | Focus | Moat |
|----------|-------|------|
| Brandwatch | Social listening | Historical archive |
| Meltwater | Media monitoring | Publisher relationships |
| AlphaSense | Market intelligence | Expert transcripts |
| RavenPack | Financial NLP | Hedge fund integrations |

---

## CLI Reference

```bash
# Sources
brandos signals sources list
brandos signals sources add sec-edgar --tickers AAPL,GOOGL,MSFT
brandos signals sources add gdelt --query "brand name"
brandos signals sources test <name>

# Fetching
brandos signals fetch --brand acme
brandos signals fetch --brand acme --sources sec-edgar,gdelt

# Analysis
brandos signals stats --brand acme --period 7d
brandos signals anomalies --brand acme
brandos signals emerging --brand acme

# Agent integration
brandos agent run signal-digest --brand acme
brandos agent run threat-assessor --brand acme --signals latest
```

---

## Summary

| Layer | Incumbents | brandOS |
|-------|------------|---------|
| L1: Raw data | Free APIs | Same (GDELT, SEC, etc.) |
| L2: Normalized | Their moat | We build this |
| L3: Interpreted | Dashboards | Agents do better |
| L4: Actionable | **Gap** | **We own this** |
| L5: Outcomes | **Gap** | **We own this** |

The competitive landscape focuses on L1-L3. We differentiate at L4-L5.
