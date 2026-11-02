libp2p cannot currently report connection and stream establishment without changing existing operations. Export its opt-in reporting vocabulary and `Host.ConnectWithReport` and `Host.NewStreamWithReport` from `github.com/libp2p/go-libp2p/core/host`.

Each call returns an immutable snapshot with its peer, terminal outcome, and phases in occurrence order. Preserve dial ranking and every considered address's disposition and provenance without marking excluded addresses as started. Joined swarm operations get separate reports with shared attempt facts; cancellation and later mutations stay local.

BasicHost reports acceptable connection reuse or dialing, including forced-direct and limited-connection decisions. Forced-direct connections expose ranked attempts and never report reuse. One joined operation may cancel during identify while another completes with the same dial facts. BlankHost and RoutedHost report their distinct routing, identify, and protocol-selection behavior without invented phases.

Address sources must match visible peerstore mutations for supplied, resolved, discovered, refreshed, and relay addresses. Relay discovery precedes destination attempts and stores relay addresses under the relay peer. Successful protocol selection matches the returned stream and later peerstore knowledge; failures preserve errors, cleanup, and knowledge effects. A BasicHost stream's installed protocol matches its selection provenance and later peerstore observations.

RoutedHost preserves failed cached attempts, refreshed discovery provenance, successful swarm facts, resulting destination state, and delegation. BlankHost absorbs supplied addresses and reports direct dialing and eager negotiation without routing, identify, or cached-selection claims. Existing `Connect` and `NewStream` behavior, including context handling, error precedence, and side effects, remains unchanged. `x/simlibp2p.GetBasicHostPair` supplies suitable BasicHost and Host instances for exercising these operations.

These are required in what you deliver:

- DialPhase: DialPhaseAddressSelection = iota, DialPhaseConnection, DialPhaseIdentify, DialPhaseProtocolSelection, DialPhaseComplete
- DialOutcome: DialOutcomeSucceeded = iota, DialOutcomeFailed, DialOutcomeCancelled
- AddressDisposition: AddressExcluded = iota, AddressFailed, AddressCancelled, AddressSucceeded
- AddressSource: AddressSourceSupplied = iota, AddressSourcePeerstore, AddressSourceRouting, AddressSourceRoutingRefresh, AddressSourceRelayRouting
- ConnectionDisposition: ConnectionReused = iota, ConnectionDialed
- IdentifyDisposition: IdentifyNotRequired = iota, IdentifyCompleted, IdentifyCancelled
- ProtocolSelection: ProtocolNotSelected = iota, ProtocolSelectedFromCache, ProtocolSelectedByNegotiation
- AddressAttempt { Address ma.Multiaddr; Source AddressSource; Disposition AddressDisposition; Err error }
- DialReport { Peer peer.ID; Outcome DialOutcome; Phases []DialPhase; Attempts []AddressAttempt; Connection ConnectionDisposition; Identify IdentifyDisposition; Protocol protocol.ID; ProtocolSelection ProtocolSelection; Err error }
- Host: ConnectWithReport(ctx context.Context, pi peer.AddrInfo) (DialReport, error); NewStreamWithReport(ctx context.Context, p peer.ID, pids ...protocol.ID) (network.Stream, DialReport, error)

Before you edit any code, write your research and your plan to /app/RESEARCH_AND_PLANNING.md. Cover what you learned about the existing code and the constraints that shape the change, then how you intend to carry it out and why, including how you will know it works. Be concrete - the files, names and decisions specific to this codebase, not generalities. Complete the document before you touch any code: it is the record of your up-front investigation and decisions, and it should not be rewritten to match whatever the implementation turns into afterwards. Once it is done, implement the plan.
