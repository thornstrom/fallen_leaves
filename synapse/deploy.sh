#!/usr/bin/env bash
# Deployar SQL-objekten till Synapse serverless.
#
# Användning: synapse/deploy.sh <serverless-endpoint> <gold_root>
#   t.ex.     synapse/deploy.sh syn-fallenleaves-dev-abcde-ondemand.sql.azuresynapse.net \
#                               abfss://gold@stfldevabcde.dfs.core.windows.net/delta
#
# Kräver go-sqlcmd och att du är inloggad med `az login` (eller OIDC i GitHub Actions).
# Skripten är idempotenta och kan köras om.
set -euo pipefail

endpoint="$1"
gold_root="$2"
here="$(cd "$(dirname "$0")" && pwd)"

# Används bara första gången master key skapas; lösenordet behövs inte senare.
master_key_password="$(openssl rand -base64 32 | tr -d '/+=')Aa1!"

run() {
  local db="$1" file="$2"
  echo "==> $file ($db)"
  sqlcmd -S "$endpoint" -d "$db" --authentication-method ActiveDirectoryAzCli -b \
    -v gold_root="$gold_root" master_key_password="$master_key_password" \
    -i "$file"
}

# Serverless-poolen startar kallt efter en tids inaktivitet och svarar då
# "The SQL pool is warming up". Vänta tills den svarar; andra fel avbryter direkt.
wait_for_pool() {
  local attempt out
  for attempt in $(seq 1 12); do
    if out="$(sqlcmd -S "$endpoint" -d master --authentication-method ActiveDirectoryAzCli -b \
      -Q "SELECT 1" 2>&1)"; then
      return 0
    fi
    if ! grep -q "warming up" <<<"$out"; then
      echo "$out" >&2
      return 1
    fi
    echo "Synapse-poolen värms upp (försök $attempt/12), väntar 15 s..."
    sleep 15
  done
  echo "Synapse-poolen svarade inte inom 3 minuter." >&2
  return 1
}

wait_for_pool
run master "$here/sql/00_database.sql"
run fallen_leaves "$here/sql/10_security.sql"

# Vyerna kräver att gold-tabellerna finns. Före första jobbkörningen i en ny miljö
# fallerar de; kör då om skriptet (eller workflowet) efter att fallen_leaves_daily har gått.
if ! run fallen_leaves "$here/sql/20_views.sql"; then
  echo "::warning::Synapse-vyerna kunde inte skapas – finns gold-tabellerna? Kör om efter första jobbkörningen."
fi
