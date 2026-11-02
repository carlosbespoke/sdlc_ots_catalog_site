import os
KEEP = lambda p: (os.path.basename(p) in ('instruction.md', 'task.toml', 'Dockerfile', 'docker-compose.yml', 'docker-compose.yaml', 'compose.yml', 'compose.yaml', 'solve.sh', 'test.sh', 'entrypoint.sh', 'setup.sh', 'README.md')
                  or p.startswith('tests/') and p.endswith(('.py', '.sh', '.toml', '.json', '.yaml', '.yml'))) and p.count('/') <= 3
