MetalLB cannot currently bound Prometheus series created by dynamic cluster and network identities. Add live, configurable cardinality governance with deterministic overflow aggregation.

Admit each family's declared dynamic-label identities up to its limit. Reuse equivalent identities, reserve overflow values, and combine excess identities into one stable series. Preserve allocator pool capacities, activity, allocations, replacement, removal, and cleanup.

Share admission decisions across native BGP peer metrics under the `metallb_bgp_native_peers` policy family while preserving session deletion, pending and advertised prefixes, and monotonic update counters. Share one bounded IP decision under the `metallb_layer2_ips` policy family across layer-two ARP and NDP request, response, and gratuitous counters without losing concurrent increments. Bound speaker service-protocol-node-IP announcements and withdraw them precisely when protocol ownership changes, including overflowed identities. Keep fixed Kubernetes reconciliation and configuration families exact, unaggregated, and exempt.

Apply BGP and BFD limits to identities found during each FRR scrape. Aggregate excess samples without changing command output or failing collection. Malformed or failed collection must continue normally without phantom identities.

Make policy replacement atomic with updates, deletions, snapshots, and scrapes. Contraction must transfer contributions exactly; expansion must not duplicate them. Immutable Policy.Snapshot results must consistently report each family's Policy.Limit, admitted and overflowed counts, cumulative rejections, and exemption status.

Below capacity, preserve metric names, help text, label keys, values, cleanup timing, and endpoint exposure. Configuration functions must apply one Policy. Lowering allocator limits before pool replacement must reflect current state. Contracting peer limits during session changes must release gauges without reducing update totals. With shared overflowed IPs across protocols, withdrawal must preserve remaining announcements and traffic totals. Independent BGP and BFD replacement during an FRR scrape must use one policy generation while layer-two collection continues through failure and recovery.

These are required in what you deliver:

- Imports: go.universe.tf/metallb/internal/metrics/cardinality exports Policy, IdentitySpec, PolicySnapshot, FamilySnapshot, NewPolicy, NewGaugeVec, GaugeVec.Set, GaugeVec.Delete, NewCounterVec, CounterVec.Add, NewCollector, Collector.Collect; go.universe.tf/metallb/internal/allocator exports allocator.ConfigureMetricCardinality; go.universe.tf/metallb/internal/bgp/native exports native.ConfigureMetricCardinality; go.universe.tf/metallb/internal/layer2 exports layer2.ConfigureMetricCardinality; go.universe.tf/metallb/internal/k8s/controllers exports controllers.ConfigureMetricCardinality.
- IdentitySpec { DynamicLabels []string; OverflowValue string }
- PolicySnapshot { Families map[string]FamilySnapshot }
- FamilySnapshot { Limit int; Admitted int; Overflowed int; Rejections uint64; Exempt bool }
- NewPolicy(limits map[string]int) (*Policy, error)
- (p *Policy) Limit(family string) int
- (p *Policy) Replace(limits map[string]int) error
- (p *Policy) Snapshot() PolicySnapshot
- NewCollector(policy *Policy, family string, collector prometheus.Collector, identity IdentitySpec) (*Collector, error)
- (c *Collector) Collect(ch chan<- prometheus.Metric)

Before you edit any code, write your research and your plan to /app/RESEARCH_AND_PLANNING.md. Cover what you learned about the existing code and the constraints that shape the change, then how you intend to carry it out and why, including how you will know it works. Be concrete - the files, names and decisions specific to this codebase, not generalities. Complete the document before you touch any code: it is the record of your up-front investigation and decisions, and it should not be rewritten to match whatever the implementation turns into afterwards. Once it is done, implement the plan.
