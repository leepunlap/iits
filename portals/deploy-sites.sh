#!/bin/bash
# Deploy ONLY the two portal web sites (students/, teachers/ + shared/assets) — no services, no nginx.
# Same steps as the first loop of deploy.sh; the assets dir must be re-created after rsync --delete.
set -euo pipefail
cd "$(dirname "$0")"
for site in teachers students; do
    sudo install -d -m 755 /var/www/ycltesthk-portals/$site
    sudo rsync -a --delete --chmod=D755,F644 "$site/" /var/www/ycltesthk-portals/$site/
    sudo install -d -m 755 /var/www/ycltesthk-portals/$site/assets
    sudo install -m 644 shared/assets/* /var/www/ycltesthk-portals/$site/assets/
done
echo "sites deployed"
