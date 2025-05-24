#!/bin/sh
rm -f star_server.zip
zip -r star_server.zip . -x ".git/*" "__pycache__/*" .gitignore .python-version package.sh conf.txt
