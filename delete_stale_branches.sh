#!/usr/bin/env bash
# delete_stale_branches.sh
# Usuwa wszystkie gałęzie w blakinio/thesslagreen OPRÓCZ chronionych.
#
# Użycie:
#   export GH_TOKEN="ghp_twój_token"
#   bash delete_stale_branches.sh
#
# Lub z tokenem inline:
#   GH_TOKEN="ghp_twój_token" bash delete_stale_branches.sh
#
# Token potrzebuje zakresu: repo (lub delete_branch dla fine-grained PAT)

set -euo pipefail

OWNER="blakinio"
REPO="thesslagreen"
API="https://api.github.com"

# Gałęzie do zachowania (regex)
KEEP_PATTERN="^(main|claude/validate-dashboard-entities-0fmkw)$"

if [[ -z "${GH_TOKEN:-}" ]]; then
    echo "ERROR: Ustaw GH_TOKEN=ghp_... przed uruchomieniem"
    echo "  export GH_TOKEN='ghp_twój_personal_access_token'"
    exit 1
fi

AUTH_HEADER="Authorization: Bearer $GH_TOKEN"

echo "=== Pobieranie listy gałęzi z $OWNER/$REPO ==="

branches=()
page=1
while true; do
    result=$(curl -sSf \
        -H "$AUTH_HEADER" \
        -H "Accept: application/vnd.github+json" \
        "$API/repos/$OWNER/$REPO/branches?per_page=100&page=$page")

    count=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))")
    if [[ "$count" -eq 0 ]]; then
        break
    fi

    while IFS= read -r branch; do
        branches+=("$branch")
    done < <(echo "$result" | python3 -c "
import sys, json
for b in json.load(sys.stdin):
    print(b['name'])
")
    echo "  Strona $page: $count gałęzi"
    page=$((page + 1))
done

total=${#branches[@]}
echo "Znaleziono $total gałęzi łącznie."
echo ""

to_delete=()
to_keep=()
for branch in "${branches[@]}"; do
    if echo "$branch" | grep -qE "$KEEP_PATTERN"; then
        to_keep+=("$branch")
    else
        to_delete+=("$branch")
    fi
done

echo "=== Gałęzie do ZACHOWANIA (${#to_keep[@]}) ==="
for b in "${to_keep[@]}"; do echo "  ✓ $b"; done
echo ""
echo "=== Gałęzie do USUNIĘCIA: ${#to_delete[@]} ==="
echo "  Przykłady:"
for b in "${to_delete[@]:0:5}"; do echo "  ✗ $b"; done
[[ ${#to_delete[@]} -gt 5 ]] && echo "  ... (+$((${#to_delete[@]}-5)) więcej)"
echo ""

read -r -p "Czy usunąć ${#to_delete[@]} gałęzi? [tak/N] " confirm
if [[ "$confirm" != "tak" ]]; then
    echo "Anulowano."
    exit 0
fi

echo ""
echo "=== Usuwanie ==="
deleted=0
failed=0
for branch in "${to_delete[@]}"; do
    encoded=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1],safe=''))" "$branch")
    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        -X DELETE \
        -H "$AUTH_HEADER" \
        -H "Accept: application/vnd.github+json" \
        "$API/repos/$OWNER/$REPO/git/refs/heads/$encoded")

    if [[ "$http_code" == "204" ]]; then
        deleted=$((deleted+1))
        [[ $((deleted % 50)) -eq 0 ]] && echo "  Usunięto: $deleted/${#to_delete[@]}"
    else
        failed=$((failed+1))
        echo "  BŁĄD ($http_code): $branch"
    fi
done

echo ""
echo "=== Gotowe ==="
echo "  Usunięto:  $deleted"
echo "  Błędy:     $failed"
echo "  Zachowano: ${#to_keep[@]}"
