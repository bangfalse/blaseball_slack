#!/usr/bin/env bash

cd "${0%/*}"

. venv/bin/activate
python3 blaseball_slack.py
