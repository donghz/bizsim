# Community Subsystem Spec (Non-Agent)

> Extracted from: agent-behavior.md §3.6 (lines 768–880) + §6.5 (lines 1330–1355)
> Cross-references: EVENTS.md (community_propagation_batch), CONSUMER.md (share_purchase action)

## Overview

The Community Subsystem is a batch computation that runs once per tick as step 4 of the simulation tick loop (see ARCHITECTURE.md). It is NOT an agent — it has no inbox, emits no Ch.2 messages, and does not participate in the agent scheduling system. It reads from a dedicated activation queue and directly mutates consumer agent state.

## State

- **Social Graph**: In-memory directed graph (NetworkX or equivalent)
  - Nodes: one per consumer agent (consumer_id)
  - Edges: (source_consumer_id, target_consumer_id) → {weight: float, topic_weights: {category: float}}
  - Average degree: ~6 (configurable)
  
- **Activation Queue**: List of SharePurchase activations accumulated during the current tick
  - Populated by consumer agents calling `community.enqueue_activation(share_purchase_data)` during their step
  - Drained and processed during tick loop step 4

## Graph Initialization

Generated once at simulation startup from a configuration seed:

```yaml
# community_graph.yaml
social_graph:
  model: "watts_strogatz"          # small-world graph
  params:
    k: 6                           # each node connected to k nearest neighbors
    p: 0.1                         # rewiring probability (creates shortcuts)
  edge_weight:
    distribution: "beta"
    alpha: 2.0
    beta: 5.0                      # skewed toward weaker ties (realistic)
    range: [0.01, 0.5]             # P(influence) per edge
  topic_weights:
    initialization: "demographic"   # topic relevance derived from consumer interest profiles
    noise: 0.1                     # random perturbation to topic weights
```

## Per-Tick Execution

Called by the simulation engine at tick loop step 4, AFTER all agents have completed their step:

1. **Drain activation queue**: Collect all SharePurchase activations from this tick
2. **Group by topic**: Group activations by category (topic)
3. **For each topic group, run Independent Cascade**:
   a. Initialize activated set = {consumer_ids from SharePurchase messages for this topic}
   b. For hop = 1 to K_MAX (default 3):
      - For each newly activated consumer C:
        - For each outgoing neighbor N of C in the social graph:
          - If N is not already activated:
            - P(activate) = edge_weight(C,N) × topic_weight(C→N, category) × satisfaction_boost
            - Where satisfaction_boost = SharePurchase.satisfaction (range [0.0, 1.0])
            - Draw random: if < P(activate), add N to newly_activated set
      - If no new activations this hop, stop early
   c. Record all activated consumers for this topic
4. **Apply interest boosts to activated consumers**:
   - For each activated consumer C (excluding original purchasers):
     - C.trend_multiplier[category] = min(C.trend_multiplier[category] + BOOST_INCREMENT, TREND_MAX)
     - Where BOOST_INCREMENT = 0.3 (configurable), TREND_MAX = 3.0
5. **Apply trend decay to ALL consumers** (not just activated):
   - For each consumer C, for each category:
     - C.trend_multiplier[category] = max(C.trend_multiplier[category] × DECAY_RATE, 1.0)
     - Where DECAY_RATE = 0.98 per tick (configurable) — trends fade toward neutral (1.0)
6. **Emit Ch.1 event** (if any activations occurred):
   - `community_propagation_batch` → batch UPDATE influence_edges (update edge weights based on successful activations — edges that successfully propagated get slightly stronger)
   - Edge weight update: successful_edge.weight = min(weight + 0.01, MAX_WEIGHT)

## Configuration

```yaml
# community_config.yaml
community:
  k_max_hops: 3
  boost_increment: 0.3             # how much trend_multiplier increases per activation
  trend_max: 3.0                   # maximum trend_multiplier value
  decay_rate: 0.98                 # per-tick multiplicative decay toward 1.0
  edge_strengthen_delta: 0.01      # successful propagation strengthens edge
  max_edge_weight: 0.5
  max_activations_per_tick: 10000  # safety cap to prevent runaway cascades
```

## Interface

```python
class CommunitySubsystem:
    def __init__(self, graph: nx.DiGraph, config: CommunityConfig):
        self._graph = graph
        self._config = config
        self._activation_queue: list[SharePurchaseData] = []

    def enqueue_activation(self, data: SharePurchaseData) -> None:
        """Called by consumer agents during their step. NOT a Ch.2 message."""
        self._activation_queue.append(data)

    def run_propagation(self, tick: int, consumers: dict[int, ConsumerAgent]) -> list[ActionEvent]:
        # ... (implements the algorithm above)
        # Returns: list of community_propagation_batch events
```

## Why This Is Not Ch.2

SharePurchase is NOT delivered via the Ch.2 inter-agent message inbox. It uses a dedicated `enqueue_activation()` call because:
- Community is not an agent — it has no agent ID, no inbox
- The activation queue is drained synchronously during the tick loop, not asynchronously via inbox drain
- No 1-tick delivery delay — propagation happens in the SAME tick as the SharePurchase

This is equivalent to a consumer calling a library function, not sending a message.

## DB Workload Generated

| Operation | Pattern | Frequency |
|---|---|---|
| Batch UPDATE influence_edges | Strengthen edges that propagated | Once per tick (if activations occurred) |
| Typical batch size | 10-500 edge updates | Proportional to cascade size |

---

## Pipeline Sequence: Social Propagation (§6.5)

```
Tick   Consumer (Purchaser)        Community Layer             Consumer (Influenced)
─────  ─────────────────────────   ────────────────────────    ─────────────────────
 N     share_purchase()
       └─ Call Community Subsystem
          (enqueue_activation)

 N                                 Batch propagation (step 4):
                                   └─ For each activation:
                                      └─ Activate purchaser node
                                         on topic = category
                                      └─ Independent Cascade:
                                         For each neighbor:
                                         P(activate) = edge_weight
                                         × topic_relevance
                                      └─ Activated neighbors get
                                         interest boost for category
                                   └─ Ch.1: (Social Graph tenant)
                                      batch UPDATE influence_edges

 N+1                                                            browse_catalog() picks up
                                                                boosted category interest
                                                                └─ higher P(browse→view)
```
