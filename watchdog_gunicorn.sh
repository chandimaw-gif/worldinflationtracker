#!/bin/bash
# Watchdog: restart WIT Gunicorn if it's not responding
if ! curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/ | grep -q "200\|301\|302"; then
    export PATH="$HOME/.local/bin:$PATH"
    cd /home/master/applications/ctaaqxskeb/public_html
    pkill -9 -f 'gunicorn.*worldinflationtracker.wsgi' 2>/dev/null
    sleep 2
    nohup gunicorn worldinflationtracker.wsgi:application \
      --bind 127.0.0.1:8000 \
      --workers 2 \
      --timeout 60 \
      --daemon \
      --log-file /tmp/gunicorn_wit.log \
      --access-logfile /tmp/gunicorn_wit_access.log \
      --pid /tmp/gunicorn_wit.pid \
      > /tmp/gunicorn_wit_nohup.log 2>&1 &
    echo "$(date): Gunicorn restarted" >> /tmp/gunicorn_watchdog.log
fi
