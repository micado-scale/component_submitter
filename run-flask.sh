#!/bin/sh


export FLASK_APP=api.py
export PYTHONPATH=/home/abdo/MyGitHub/component_submitter/
export FLASK_DEBUG=0
export FLASK_ENV=production
flask run
