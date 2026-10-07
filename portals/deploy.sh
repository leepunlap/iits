#!/bin/bash
# Deploy both portal sites, the sign-up/recovery service and the nginx config to the NUC.  Usage: ./deploy.sh
# One-time (holds the SMTP password, so not in this folder): /etc/iits-portal-reg/{config.json,smtp.env}, root:www-data 640.
set -euo pipefail
cd "$(dirname "$0")"
sudo test -f /etc/iits-portal-reg/config.json && sudo test -f /etc/iits-portal-reg/smtp.env \
    || { echo "missing /etc/iits-portal-reg/config.json or smtp.env — see README"; exit 1; }

for site in teachers students; do
    sudo install -d -m 755 /var/www/ycltesthk-portals/$site
    sudo rsync -a --delete --chmod=D755,F644 "$site/" /var/www/ycltesthk-portals/$site/
    sudo install -d -m 755 /var/www/ycltesthk-portals/$site/assets
    sudo install -m 644 shared/assets/* /var/www/ycltesthk-portals/$site/assets/
done

# sign-up / recovery service
sudo install -d -m 755 /opt/iits-portal-reg
sudo install -m 644 backend/reg.py /opt/iits-portal-reg/reg.py
sudo install -d -o www-data -g www-data -m 700 /var/lib/iits-portal-reg
sudo install -m 644 backend/iits-portal-reg.service /etc/systemd/system/iits-portal-reg.service
sudo systemctl daemon-reload
sudo systemctl enable iits-portal-reg >/dev/null 2>&1
sudo systemctl restart iits-portal-reg

# login/file service: patched checker (reads self-registered accounts too); keep a backup of the old one
if ! sudo cmp -s backend/checker.py /opt/iits-teacher-auth/checker.py; then
    sudo cp -p /opt/iits-teacher-auth/checker.py /opt/iits-teacher-auth/checker.py.bak-$(date +%Y%m%d-%H%M%S)
    sudo install -o root -g root -m 644 backend/checker.py /opt/iits-teacher-auth/checker.py
    sudo systemctl restart iits-teacher-auth
fi

sudo install -m 644 nginx/ycltesthk-portals.conf /etc/nginx/sites-available/ycltesthk-portals
sudo ln -sf /etc/nginx/sites-available/ycltesthk-portals /etc/nginx/sites-enabled/ycltesthk-portals
sudo nginx -t && sudo systemctl reload nginx
sleep 1
systemctl is-active --quiet iits-portal-reg && systemctl is-active --quiet iits-teacher-auth \
    && echo "deployed: https://teachers.ycltesthk.com/  https://students.ycltesthk.com/" \
    || { echo "a service is not running:"; systemctl --no-pager status iits-portal-reg iits-teacher-auth | tail -20; exit 1; }
