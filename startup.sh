#!/bin/bash
sleep 15
export PATH="$HOME/.local/bin:$PATH"
cd /home/master/applications/ctaaqxskeb/public_html
nohup gunicorn worldinflationtracker.wsgi:application --bind 127.0.0.1:8000 --workers 2 --daemon > /tmp/gunicorn_wit.log 2>&1 &
