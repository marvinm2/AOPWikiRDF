# Endpoint deployment files (`aopwiki-snorql` stack)

These are the files that load and serve the production SPARQL endpoint
(`https://aopwiki.rdf.bigcat-bioinformatics.org/sparql/`), which runs as the
`aopwiki-snorql` stack on the VHP4Safety Strato cluster (tgx1/tgx2). This folder
is their source of truth; the cluster copies are deployed from here. The
operational doc is `services/aopwiki-snorql.md` in the cluster documentation.

Change them here, in the same pull request as any data change that needs them
(for example a change to which graph a TTL file is loaded into), then deploy.

| File | Live path | What it does |
|---|---|---|
| `reload.sh` | `/mnt/gluster/docker/aopwiki-snorql/scripts/reload.sh` | Weekly reload (cron, Sunday 06:00 UTC, on both nodes; only the node hosting Virtuoso acts). Downloads the five TTLs from `master/data/`, validates them with `rapper`, stages them, runs `load.sh`. |
| `load.sh` | `/mnt/gluster/docker/aopwiki-snorql/virtuoso-data/data/load.sh` (`/database/data/load.sh` in the container) | In-container isql loader: `RDF_GLOBAL_RESET`, prefixes, `ld_dir` per file and graph, `rdf_loader_run`. |
| `sd-rewrite.sql` | `/mnt/gluster/docker/aopwiki-snorql/scripts/sd-rewrite.sql` | Virtuoso URL-rewrite rule: `/sparql-sd-full` → CONSTRUCT of the service description graph. |
| `void-rewrite.sql` | `/mnt/gluster/docker/aopwiki-snorql/scripts/void-rewrite.sql` | Virtuoso URL-rewrite rule: `/void-full` → CONSTRUCT of the VoID. |
| `aopwiki-sd.yml` | `/mnt/gluster/docker/traefik/dynamic/aopwiki-sd.yml` | Traefik file-provider router sending SD requests on `/sparql` to `/sparql-sd-full`, and `/.well-known/void` to `/void-full`. |

The other `load.sh` copies (`aopwiki-snorql-extended/load.sh`, an untracked
`server-scripts/`) belong to the retired strato1 deployment and are not what
production runs.

## No credentials in these files

The Virtuoso dba password comes from the stack's `.env` (`~/aopwiki-snorql/.env`
on tgx1) and is set in the Virtuoso container's environment. `reload.sh` never
holds it: each isql call runs inside the container and expands the container's
own `$DBA_PASSWORD` (note the single quotes around `bash -c`). Keep it that way.

## Deploying

```bash
# scripts and loader (GlusterFS, so both nodes see them)
scp reload.sh sd-rewrite.sql void-rewrite.sql tgx1:/mnt/gluster/docker/aopwiki-snorql/scripts/
scp load.sh tgx1:/mnt/gluster/docker/aopwiki-snorql/virtuoso-data/data/

# Traefik route: inotify does not cross nodes, so poke the other node's watcher
scp aopwiki-sd.yml tgx1:/mnt/gluster/docker/traefik/dynamic/
ssh tgx2 "touch /mnt/gluster/docker/traefik/dynamic/aopwiki-sd.yml"

# rewrite rules (idempotent), on whichever node hosts Virtuoso
for n in tgx1 tgx2; do
  ssh "$n" 'CID=$(docker ps -q -f name=aopwiki-snorql_virtuoso | head -1); [ -z "$CID" ] && exit 0;
    docker exec -i "$CID" sh -c "isql -U dba -P \"\$DBA_PASSWORD\""' < void-rewrite.sql
done
```

A `load.sh` change takes effect at the next reload; to apply it now, run
`ssh tgx1 "bash /mnt/gluster/docker/aopwiki-snorql/scripts/reload.sh"` (and on
tgx2: the guard makes the node without Virtuoso exit immediately). Afterwards,
update `services/aopwiki-snorql.md` in the cluster documentation.
