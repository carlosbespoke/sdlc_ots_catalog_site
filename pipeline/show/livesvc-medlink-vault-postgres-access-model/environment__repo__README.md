# medlink-platform

Terraform for the Medlink platform services: HashiCorp Vault (secrets, workload identities, dynamic database
credentials) and the PostgreSQL databases of every environment. Owned by the platform team (#plat-infra).

The target state is [ACCESS_MODEL.md](ACCESS_MODEL.md). The inventory of environments, teams, schemas and workloads is
`inventory.auto.tfvars.json`.

## Layout

| File | Owner | What it is |
| --- | --- | --- |
| `versions.tf`, `providers.tf`, `backend.tf` | CI platform (do not edit) | pinned Terraform and providers, credentials from the environment, the state location |
| `variables.tf`, `inventory.auto.tfvars.json` | generated from the service catalogue (do not edit) | the inventory and its types |
| `vault.tf` | platform team | phase 0 (see History) |
| everything else | platform team | yours |

CI applies `main` with the production state as it is. Only the configuration reaches production: local state surgery
(`terraform import`, `terraform state mv/rm`) does not. Adopting existing objects and moving resources between
addresses is done with `import`, `moved` and `removed` blocks in the configuration. CI runs every plan and apply with
the providers pinned in `versions.tf` and nothing else: no provisioners, no other providers, no local modules from
outside the repository.

The inventory is regenerated whenever the service catalogue changes (new teams and workloads, decommissions, a
workload moving to a team, new lifetimes...). CI then applies `main` again with the new inventory on top of the
current state, so the configuration must derive everything from the inventory: no names copied out of it.

## Working locally

The workstation runs a copy of production restored from last night's snapshot: Vault at `http://127.0.0.1:8200`
(root token in `~/.vault-token`) and PostgreSQL at `127.0.0.1:5432` (superuser `postgres`; `PGHOST`, `PGUSER` and
`PGPASSWORD` are set). The local Terraform state is the copy of the production state that came with the snapshot
(`/var/lib/platform/terraform/terraform.tfstate`).

```sh
terraform init
terraform plan
vault policy list
psql -d medlink_prod -c '\dn+'
platform-reset        # throw away every change to Vault, PostgreSQL and the local state: back to the snapshot
```

`platform-reset` is how you rehearse the CI apply: reset, then `terraform apply` once and `terraform plan` again.

## History

- 2023: Vault introduced by hand for the first services; applications still used static PostgreSQL logins
  (`portal_app`, `etl_reader`).
- 2024-05, PLAT-212 "phase 0": the engines and the first workloads on AppRole (patient-api, portal-web, fax-gateway,
  auth-service) were codified in `vault.tf`; PLAT-230 added the `apps-read-all` stop-gap policy so those workloads
  could read shared settings until they had their own paths.
- 2024-06 to 2026-08: everything else was done by hand with the `vault` and `psql` CLIs by the owning teams, the
  identity team and the DBA team: most workload policies and AppRole roles, the database secrets engine's
  connections (the DBA team ran `rotate-root` on both right after creating them) and roles, the team groups of three
  teams, every PostgreSQL role, schema, grant and extension. Conventions drifted; several incidents were mitigated
  directly on the servers (INC-311, INC-342, FIN-19).
- 2025-03: fax-gateway decommissioned (its Vault objects were never removed).
- 2026-09, PLAT-412: access model v3 approved ([ACCESS_MODEL.md](ACCESS_MODEL.md)). This repository must manage all of
  it.
