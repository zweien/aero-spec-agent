"""Project-wide test configuration."""

import os

# Remove proxy env vars at import time so OpenAI/httpx doesn't choke on
# unsupported schemes like socks://.  Must happen before any module that
# creates an OpenAI client is imported (e.g. chat_service via chat router).
_PROXY_VARS = (
    "http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
    "all_proxy", "ALL_PROXY",
)
for _var in _PROXY_VARS:
    os.environ.pop(_var, None)
