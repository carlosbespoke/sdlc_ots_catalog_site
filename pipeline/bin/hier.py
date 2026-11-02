# 50 domain categories: id -> (name, previous super-group, revised super-group)
P = {1:"Cloud infrastructure & operations",2:"Security & supply chain",3:"Data engineering & databases",4:"AI, ML & scientific computing",5:"Programming languages & developer tooling",6:"Systems & low-level software",7:"Distributed systems & coordination",8:"Applications & business domains"}
R = {"A":"Cloud infrastructure & IaC","B":"Observability & reliability","C":"Build, release & supply chain","D":"Security","E":"Data engineering & databases","F":"Scientific & ML software","G":"Languages & developer tooling","H":"Systems, hardware & accelerators","I":"Distributed systems & coordination","J":"Applications & business domains"}
CAT = {
1:("AI agents & retrieval",4,"F"),2:("Machine learning & MLOps",4,"F"),3:("Medical imaging & healthcare",4,"F"),4:("Scientific computing",4,"F"),
5:("Statistics & numerical methods",4,"F"),6:("Geospatial",4,"F"),7:("Sports analytics",4,"F"),8:("Analytics engineering",3,"E"),
9:("Data pipelines & ETL",3,"E"),10:("Data validation",3,"E"),11:("Data formats & serialization",3,"E"),12:("Parser security hardening",2,"D"),
13:("Compression & data integrity",6,"H"),14:("Probabilistic data structures",4,"F"),15:("Graph algorithms",4,"F"),16:("Databases & storage engines",3,"E"),
17:("SQL tooling",3,"E"),18:("Compilers & language runtimes",5,"G"),19:("Logic programming",5,"G"),20:("Memory management",6,"H"),
21:("Binary analysis",2,"D"),22:("Build systems",5,"C"),23:("CI/CD",1,"C"),24:("Software supply chain",2,"C"),
25:("API tooling",5,"G"),26:("CLI tooling",5,"G"),27:("Configuration management",1,"A"),28:("Filesystems",6,"H"),
29:("Cloud infra: containers & self-hosted platforms",1,"A"),30:("Cloud infra: serverless & event-driven",1,"A"),31:("Cloud infra: AWS platform stacks",1,"A"),32:("Cloud security & compliance",2,"D"),
33:("Secrets & access control",2,"D"),34:("Cryptography & secure protocols",2,"D"),35:("Secret scanning",2,"D"),36:("Monitoring & observability",1,"B"),
37:("Messaging & event streaming",7,"I"),38:("Job scheduling",7,"I"),39:("Calendaring & recurrence",7,"I"),40:("Rate limiting",7,"B"),
41:("Networking & HTTP",6,"H"),42:("IoT & smart home",6,"H"),43:("Workflow automation",7,"I"),44:("Payments & banking",8,"J"),
45:("Web applications",8,"J"),46:("Collaborative documents",8,"J"),47:("Media processing",8,"J"),48:("Frontend & UI state",8,"J"),
49:("Education tooling",8,"J"),50:("Web crawling",8,"J"),
# added from the task-shapes sheet: no tasks in the shortlist yet (gaps)
51:("GPU kernels",None,"H"),52:("Hardware RTL",None,"H"),53:("Mobile apps (Android)",None,"J"),
}
DOM = {
"AI agents / retrieval (RAG)":1,"Analytics engineering (FX conversion)":8,"API tooling (OpenAPI breaking-change detection)":25,"Banking / fintech":44,
"Banking data (bank codes / IBAN)":44,"Binary analysis (disassembly)":21,"Binary parsing / serialization":11,"Build systems (BUILD-file generation)":22,
"Calendaring / recurrence rules":39,"CI/CD":23,"CLI argument parsing":26,"Cloud infrastructure (AWS alerting / event routing)":30,
"Cloud infrastructure (AWS Cognito, game backend)":31,"Cloud infrastructure (AWS ECS)":29,"Cloud infrastructure (AWS serverless)":30,"Cloud infrastructure (AWS workflows)":30,
"Cloud infrastructure (AWS, geospatial data platform)":31,"Cloud infrastructure (AWS, Kubernetes, IPv6)":29,"Cloud infrastructure (AWS, ML model routing)":31,"Cloud infrastructure (AWS)":31,
"Cloud infrastructure (Terraform Enterprise air-gapped)":29,"Cloud infrastructure (Terraform Enterprise on Nomad)":29,"Cloud monitoring / alarming (OpenStack)":36,"Cloud security (multi-account scanning)":32,
"Cloud security & compliance":32,"Collaborative spreadsheets":46,"Compilers (user-schedulable kernel language)":18,"Compilers / API schema languages (GraphQL)":18,
"Compilers / language runtimes":18,"Compression / binary codecs":13,"Configuration management (config-file editing)":27,"Data engineering (CSV/JSON pipelines)":9,
"Data engineering (incremental loads / change logs)":9,"Data engineering (LLM pretraining data pipelines)":9,"Data formats (XML)":11,"Data validation":10,
"Databases":16,"Databases (in-memory)":16,"Databases (SQL engine)":16,"Databases / audit history":16,
"Databases / SQL tooling (parser, transpiler)":17,"Distributed business app (booking)":45,"Education tooling (Jupyter grading)":49,"Filesystems (FAT, crash recovery)":28,
"Frontend / UI state (forms)":48,"Geospatial indexing":6,"Government digital services / messaging":45,"Graph layout algorithms":15,
"Healthcare / medical imaging networking (DICOM)":3,"IoT / smart home (Zigbee)":42,"Job scheduling":38,"Logic programming (Datalog engine)":19,
"Machine learning":2,"Media processing (AV1 video encoding)":47,"Media processing (video editing)":47,"Media storage / photo management":47,
"Medical imaging / deep learning":3,"Memory management / garbage collection":20,"Messaging / event streaming":37,"Messaging / task queues":37,
"ML experiment tracking":2,"Networking / HTTP":41,"Numerical / histograms":5,"Numerical / random number generation":5,
"Observability (OpenTelemetry instrumentation)":36,"Observability / metrics storage":36,"Observability data (OpenTelemetry)":36,"Parsers / XML security (entity amplification limits)":12,
"Payments (Stripe webhooks sync)":44,"Probabilistic data structures / streaming":14,"Programming languages / interpreters (Scheme)":18,"Rate limiting":40,
"Scientific computing (geometric statistics)":4,"Scientific computing (target tracking)":4,"Secrets & database access control":33,"Security (secret scanning)":35,
"Security / cryptography":34,"Security / network protocols (DTLS)":34,"Serialization frameworks":11,"Software supply chain (reproducible builds)":24,
"Software supply chain / vulnerability data":24,"Sports analytics (tracking time series)":7,"Statistics / numerical":5,"Storage / data integrity (compression, CRC, erasure codes)":13,
"Web application (CTF platform) data":45,"Web application (wiki)":45,"Web crawling / scraping":50,"Workflow automation":43,
}
# Task shapes: (shape, shape category) as in the "SDLC Task shapes" sheet; NEW = proposed shape not in that sheet
def shape(name, family, change):
    if family.startswith("ProgramBench – clean-room"): return ("Rebuild a program from its binary","Greenfield / reimplementation","Exact")
    if family == "Cross-language migration": return ("Evolve a repo from one release to the next","Software evolution","Near: sheet counts migration-ots here; this is a language port, not a release")
    if family.startswith("RCA bug fix"): return ("On-call root cause analysis","SRE / incident response","Near: sheet counts rca-xai-ots here, but the cause is found in code, not in runtime telemetry")
    if name.startswith("db-migration") or name.startswith("livesvc-"): return ("Live system change","Operations / migration","Exact")
    if name.startswith("qfn-"): return ("Incident response","SRE / incident response","Exact (sheet counts SRE-xai-ots here)")
    if family.startswith("System design") or "diskfs-crash" in name: return ("Failure-proofing","Reliability","Exact (sheet counts deepswe crash/durability and chaos tasks here)")
    if name == "otel-contrib-pdk-ots": return ("Add OpenTelemetry instrumentation","Observability","Near: repairs existing instrumentation to spec, does not add tracing")
    if family.startswith("Spec drift"): return ("NEW: Docs-vs-code drift repair","Software evolution","New: no shape in the sheet")
    if family.startswith("Blind multi-bug"): return ("NEW: Multi-bug diagnosis & fault localization","Debugging","New: closest sheet shape is 'Fix concurrency bugs', which is narrower")
    if family.startswith("Infrastructure as code") or name.startswith(("pulumi-","cdk-","policy-","terraform-")): return ("NEW: State-preserving IaC change","Infrastructure as code","New: sheet counts SRE-xai-ots under Incident response, but these are plan-checked refactors, ports and policy fixes")
    if family.startswith("Data processing"): return ("NEW: Data pipeline repair / extension","Data engineering","New: no shape in the sheet")
    if family.startswith("Performance"): return ("NEW: CPU performance optimization","Performance","New: the sheet only has GPU performance shapes")
    if family.startswith(("Feature implementation","Blueprint","DeepSWE")): return ("Feature development across several PRs","Feature development","Near: single-task feature, not a multi-PR feature")
    return ("?","?","?")
