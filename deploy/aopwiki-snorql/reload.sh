#!/bin/bash
#
# AOP-Wiki single-graph endpoint — weekly RDF reload (tgx1/tgx2 swarm)
#
# Swarm port of strato1 /home/MarvinMartens/AOP-Wiki-EP/aopwiki.sh.
# The aopwiki-snorql_virtuoso service is NOT node-pinned, so this cron is
# installed on BOTH nodes. The guard below makes only the node that currently
# hosts the Virtuoso task do the work; the other node exits immediately. Because
# the service is update_config: stop-first, the container is never on two nodes
# at once, so the reload never double-runs and never races on the Gluster dir.
#
# Downloads the latest TTLs, validates them with a containerized `rapper` (host
# has none), and only then wipes+reloads Virtuoso. Runs as a docker-group user.
#
# The dba password is never written here: every isql call runs inside the
# Virtuoso container and reads that container's own DBA_PASSWORD, which the
# stack sets from ~/aopwiki-snorql/.env. Note the single quotes around the
# `bash -c` commands below -- the variable must expand in the container, not on
# the host. Source of truth: marvinm2/AOPWikiRDF deploy/aopwiki-snorql/.
#
set -euo pipefail

DATADIR=/mnt/gluster/docker/aopwiki-snorql/virtuoso-data/data
SCRIPTDIR=/mnt/gluster/docker/aopwiki-snorql/scripts
GITHUB_URL=https://raw.githubusercontent.com/marvinm2/AOPWikiRDF/master/data
FILES="AOPWikiRDF.ttl AOPWikiRDF-Enriched.ttl AOPWikiRDF-Genes.ttl AOPWikiRDF-Void.ttl ServiceDescription.ttl"
SERVICE=aopwiki-snorql_virtuoso
VALIDATOR=aopwiki-rapper:latest

# --- Node guard: only the node hosting the Virtuoso task proceeds. -----------
# Must be the very first action (before any download/log/file op) so the other
# node no-ops with zero side effects.
CID=$(docker ps -q -f "name=$SERVICE" | head -1)
if [ -z "$CID" ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $SERVICE not on $(hostname) — skipping reload."
    exit 0
fi

LOG="$SCRIPTDIR/reload-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1
echo "=== AOP-Wiki RDF reload started $(date -u +%Y-%m-%dT%H:%M:%SZ) on $(hostname) ==="

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# 1. Download the latest TTLs into a scratch dir (never straight into the live dir).
for f in $FILES; do
    echo "Downloading $f ..."
    if ! wget -q -O "$TMP/$f" "$GITHUB_URL/$f"; then
        echo "ERROR: download failed for $f — aborting, existing data untouched."
        exit 1
    fi
    if [ ! -s "$TMP/$f" ]; then
        echo "ERROR: $f is empty — aborting, existing data untouched."
        exit 1
    fi
done

# 2. Validate every file with rapper (containerized). Abort the whole reload if any
#    fails, so a corrupt/partial download can never trigger the RDF_GLOBAL_RESET below.
for f in $FILES; do
    echo "Validating $f ..."
    if ! docker run --rm -v "$TMP:/data:ro" "$VALIDATOR" rapper -i turtle -c "/data/$f" >/dev/null; then
        echo "ERROR: Turtle validation failed for $f — aborting, existing data untouched."
        exit 1
    fi
done
echo "All TTL files valid."

# 3. Stage validated files into the live data dir (keep load.sh; replace TTLs).
rm -f "$DATADIR"/*.ttl
cp "$TMP"/*.ttl "$DATADIR"/
ls -l "$DATADIR"

# 4. Re-resolve the container (in case it moved since the guard) and load.
CID=$(docker ps -q -f "name=$SERVICE" | head -1)
if [ -z "$CID" ]; then
    echo "ERROR: $SERVICE container vanished from this node mid-run — aborting."
    exit 1
fi
echo "Loading into container $CID ..."
docker exec -i "$CID" bash -c '/database/data/load.sh /database/data/load.log "$DBA_PASSWORD"'

# 5. Post-load sanity: every registered file must reach ll_state=2 with no error.
echo "--- load_list status ---"
docker exec -i "$CID" bash -c 'isql -U dba -P "$DBA_PASSWORD" verbose=on exec="SELECT ll_file, ll_state, ll_error FROM DB.DBA.load_list;"'
echo "--- triple count in http://aopwiki.org/ ---"
docker exec -i "$CID" bash -c 'isql -U dba -P "$DBA_PASSWORD" exec="SPARQL SELECT (COUNT(*) AS ?n) FROM <http://aopwiki.org/> WHERE { ?s ?p ?o };"'

# Keep only the 12 most recent reload logs.
ls -t "$SCRIPTDIR"/reload-*.log 2>/dev/null | tail -n +13 | xargs -r rm -f

echo "=== AOP-Wiki RDF reload finished $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
