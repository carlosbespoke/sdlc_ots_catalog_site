# AtlasGrid production ECS platform (dev) - Pulumi

Pulumi project `atlasgrid-ecs`, stack `dev`. The stack already holds every production resource: the platform team
bulk-imported what `/workspace/terraform` manages into the local backend `/workspace/pulumi-state`
(`PULUMI_BACKEND_URL` and `PULUMI_CONFIG_PASSPHRASE` are set in the environment). The program that matches it is
still to be written, in TypeScript (`index.ts`).

- `Pulumi.dev.yaml`, `Pulumi.yaml`, `package.json`, `templates/`, `tsconfig.json` are owned by the platform team; keep them as they are.
- `pulumi preview --refresh=false` compares the program with production; there is no AWS access from this machine.
- `pulumi stack export` shows every resource of the stack with its URN, inputs and outputs.
