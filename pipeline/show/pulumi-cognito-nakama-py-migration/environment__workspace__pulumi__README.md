# Cognito-backed Nakama game service (dev) - Pulumi

Pulumi project `cognito-nakama`, stack `dev`. The stack already holds every production resource: the platform team
bulk-imported what `/workspace/terraform` manages into the local backend `/workspace/pulumi-state`
(`PULUMI_BACKEND_URL` and `PULUMI_CONFIG_PASSPHRASE` are set in the environment). The program that matches it is
still to be written, in Python (`__main__.py`).

- `Pulumi.dev.yaml`, `Pulumi.yaml` are owned by the platform team; keep them as they are.
- `pulumi preview --refresh=false` compares the program with production; there is no AWS access from this machine.
- `pulumi stack export` shows every resource of the stack with its URN, inputs and outputs.
