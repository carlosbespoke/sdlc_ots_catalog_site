# Multi-model router production stack

This stack is the production form of the ECS multi-model-router blueprint. It runs three model services behind one application load balancer, stores model artifacts in dedicated buckets and repositories, spans three availability zones, and provides three asynchronous inference queues for interactive and batch callers.

The repository predates our module standard. Resources are still indexed by ordered lists, and production values are repeated in several files. Run `scripts/ci-plan.sh` before merging; CI plans with refresh disabled against the recorded state and rejects infrastructure changes.
