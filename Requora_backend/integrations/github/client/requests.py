"""A tiny passthrough module so tests can patch
Requora_backend.integrations.github.client.requests.Session.get

This simply re-exports the real `requests` module under the package namespace.
"""
import requests as requests

# expose Session for convenience
Session = requests.Session
get = requests.get
