# Models left out everywhere (pages, plots, turn counts, CSVs, and the version fallback in fetch.py).
DROPPED = {
    'starfall',    # google/gemini-3.7-flash
    'helm',        # cohere/command-a
    'astrolabe',   # x-ai/grok-4.7
    'lumen-pro',   # claude-opus-5-5
    'meridian',    # gpt-6-astra
    'forge',       # qwen/qwen3.8-max-0902
    'cipher-omni',  # z-ai/glm-5.2
    'crossbill',    # meta/muse-wonder
    'granola-plus', # meta/muse-spark-1.3
    'ecliptic',     # moonshotai/kimi-k3.1-pro
}

# Tasks left out of the report: no graded run from a kept model before the snapshot (26 graded only by dropped models,
# 3 with infrastructure errors only).
EXCLUDED_TASKS = {
    'c15f38ba-0f04-43c0-952f-8fe163f3989f',  # chai-rangescan
    '7a15c41d-2023-4576-9ef8-e86aefe9fb57',  # kombu-codecswap
    '638acc45-29ab-4428-b2a8-f3b11e543327',  # leafwiki-frontpair
    '0320ec16-c314-46a7-9038-9728966b3a16',  # risor-rollbackplan
    '6c9e0c85-592a-4015-b53c-419f19b56a55',  # starlark-optgate
    'c1ae4deb-10ab-4a59-ae91-04ca499c2c5f',  # stonesoup-tracksplit
    '391b7c9e-d035-4ffc-b4eb-3677ae07187b',  # tortoise-tzround
    'd229a26f-93d3-42d3-8e81-ab252c2cb2f3',  # dhcp-bounded-dhcpv4-option-area-layout-and-9fc7
    '0425b4f2-1f88-4878-9a18-dc7a3f1414f6',  # goyave-managed-component-lifecycle
    '883f90ad-2036-4358-b02d-9c00b36c881e',  # protolint-previewable-transactional-auto-8a10
    '1c4c2aa5-c14b-4d62-967a-e1a33adc6e6c',  # austinhellerrepo--shiftnanigans-xai
    '97f103bf-52de-4923-87ef-04e1a7fb532a',  # bugadani--somni-xai
    'dafe115b-3d1c-4140-8789-d868abcd7d51',  # cydhra--vers-xai
    'a3ea1b9d-882b-487a-82d7-437cbf72e92b',  # dahlia--gukhanmun-xai
    '75a02903-3b13-448a-9407-8fe1587f578d',  # dasp-rs--dasp-rs-xai
    '158d0f70-0ed6-48f4-bed8-a1737472894f',  # eriksremess--bbcat-xai
    'b5a338ce-79fd-4e68-a7f3-1861845752ae',  # florian1345--sudoku-variants-xai
    '7c08fcf8-bf10-4412-a239-0245a7319d3b',  # fmeringdal--rust-rrule-xai
    '27dce673-6736-4039-b14f-495c4df3dbf5',  # henquist--audioadapter-rs-xai
    '3e1f4ef3-acca-4410-9975-b3c52521cc79',  # java--apache--commons-rng--commons-rng-core-xai
    'fc9f9aca-4c6b-4ccf-8e5b-6a7ef89da580',  # java--autoffice--luckysheet-lib-xai
    'ef7402f6-3b67-42f1-8462-9e261fa9137b',  # java--fmabap--amdp_pretty_printer--amdp-pretty-printer-java-amdp-pretty-printer-core-xai
    'bca79f0b-cd72-4ee2-8902-c8282db0b0b5',  # java--nscuro--versatile--versatile-core-xai
    '38e83a06-c2ff-4226-8654-c389687a8b6c',  # maltejanz--ludtwig-xai
    '1dce6c29-c289-4c4f-b370-ea5182fdfaf0',  # mamrhein--fpdec.rs-xai
    '956a010b-e739-4e21-9b1c-07cd61980577',  # northaxosky--rust-crates-xai
    'f5f622c4-e970-4c4f-bab9-215f9f571073',  # oxideav--oxideav-id3-xai
    '5d14dbc7-e4dd-4073-802f-df0147899160',  # sim-nest--sim-discrete-xai
    '8f6262ce-fb2e-41a9-93ba-1979bd474d03',  # goreleaser__nfpm.8428c3d
}
