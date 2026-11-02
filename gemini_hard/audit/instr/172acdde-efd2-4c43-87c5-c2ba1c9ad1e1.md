orb cannot consistently bound resource use while decoding untrusted spatial data in WKB, EWKB, WKT, and MVT. Apply one budget across all four formats. Bounded operations must report comparable, deterministic `limits.Usage`, fail atomically, and treat zero limits as unlimited.

Count committed input, expansion, nesting, geometries, coordinates, containers, and properties once, rolling back abandoned alternatives. Return `limits.LimitError` for the first resource crossed during source traversal, with no partial geometry, destination, feature, or layer. Preserve successful results and native non-limit errors, including earlier format and malformed-input errors. Keep bounded and unlimited operations isolated.

Bounded WKB and EWKB slice decoding must reject attacker-controlled binary container declarations against byte, nesting, geometry, and coordinate limits before allocation failure or truncated-data classification. Preserve stream boundaries, scanner null and hexadecimal handling, concrete destinations, and distinct SRID semantics. Hexadecimal scanner calls must retain unread bytes and report fresh per-operation usage. After EWKB stream exhaustion, prefixed-SRID scanning and the next stream decode must preserve SRIDs and start fresh accounting.

WKT generic and typed paths must account equivalently while preserving type mismatch, empty geometry, whitespace, case, bounds, rings, children, and earlier format errors. MVT must budget raw and gzip-expanded bytes, protobuf structure, layers, features, properties, geometry commands, and coordinates. ClosePath adds no source-coordinate charge. Equivalent point and line inputs across all formats must share coordinate boundaries and common counters. Competing limits in nested WKT, binary polygons, and compressed MVT must identify the first traversed exhaustion.

Provide `wkb.UnmarshalWithLimits(data, lim)`, `wkb.ScannerWithLimits(g, lim)`, `ewkb.UnmarshalWithLimits(data, lim)`, `ewkb.ScannerWithLimits(g, lim)`, `ewkb.ScannerPrefixSRIDWithLimits(g, lim)`, `wkt.UnmarshalWithLimits(s, lim)`, `wkt.UnmarshalPointWithLimits(s, lim)`, `wkt.UnmarshalPolygonWithLimits(s, lim)`, `mvt.UnmarshalWithLimits(data, lim)`, and `mvt.UnmarshalGzippedWithLimits(data, lim)`.

These are required in what you deliver:

- From `github.com/paulmach/orb/encoding/limits`: `limits.Limits`, `limits.Usage`, `limits.Resource`, `limits.LimitError`.
- `limits.Limits(InputBytes, ExpandedBytes, Nesting, Geometries, Coordinates, Containers, Properties)`.
- `limits.Usage(InputBytes, ExpandedBytes, PeakNesting, Geometries, Coordinates, Containers, Properties)`.
- `limits.Resource`: `ResourceInputBytes = iota + 1`, `ResourceExpandedBytes`, `ResourceNesting`, `ResourceGeometries`, `ResourceCoordinates`, `ResourceContainers`, `ResourceProperties`.
- `limits.LimitError(Resource, Limit, Attempted)`.
- `wkb.NewDecoder(r) *Decoder`.
- `(*wkb.Decoder) SetLimits(lim) *Decoder`.
- `(*wkb.Decoder) Usage() limits.Usage`.
- `ewkb.NewDecoder(r) *Decoder`.
- `(*ewkb.Decoder) SetLimits(lim) *Decoder`; `(*ewkb.Decoder) Usage() limits.Usage`.

Before you edit any code, write your research and your plan to /app/RESEARCH_AND_PLANNING.md. Cover what you learned about the existing code and the constraints that shape the change, then how you intend to carry it out and why, including how you will know it works. Be concrete - the files, names and decisions specific to this codebase, not generalities. Complete the document before you touch any code: it is the record of your up-front investigation and decisions, and it should not be rewritten to match whatever the implementation turns into afterwards. Once it is done, implement the plan.
