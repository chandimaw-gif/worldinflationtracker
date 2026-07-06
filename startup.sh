#!/bin/bash
# Startup script for World Inflation Tracker Gunicorn
sleep 15
export PATH="$HOME/.local/bin:$PATH"
cd /home/master/applications/ctaaqxskeb/public_html

# Kill any existing gunicorn processes for this app
pkill -9 -f 'gunicorn.*worldinflationtracker.wsgi' 2>/dev/null
sleep 2

# Start gunicorn with logs in /tmp to avoid permission issues
nohup gunicorn worldinflationtracker.wsgi:application \
  --bind 127.0.0.1:8000 \
  --workers 2 \
  --timeout 60 \
  --daemon \
  --log-file /tmp/gunicorn_wit.log \
  --access-logfile /tmp/gunicorn_wit_access.log \
  --pid /tmp/gunicorn_wit.pid \
  > /tmp/gunicorn_wit_nohup.log 2>&1 &
