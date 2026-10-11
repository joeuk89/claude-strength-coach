"""The Hevy API client: reads, paging, rate-limited and audited writes (contract C3, C9).

Every non-GET request appends one `write` line to `data/hevy/writes.jsonl`,
whether it succeeds or fails. Every 429 waits 30 s and retries; the third
429 in a row gives up. The API key goes only into the request header and is
scrubbed from any message built from Hevy's replies.
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from coach import jsonio, paths
from coach.errors import ConfigError, NetworkError, ValidationError
from coach.hevy import envfile
from coach.hevy import transport as transport_module
from coach.hevy.ratelimit import WRITE_BURST, TokenBucket
from coach.hevy.transport import TransportTimeout, TransportUnreachable

AUDIT_VERSION = 1
BACKOFF_SECONDS = 30
MAX_ATTEMPTS_ON_429 = 3
_ROUTINE_PATH = re.compile(r"^/v1/routines/([^/]+)$")


class HevyRequestError(ValidationError):
    """Hevy refused a request with a 4xx other than 401, 403 or 429."""

    def __init__(self, message, status, body=None):
        super().__init__(message)
        self.status = status
        self.body = body


def _utc_now():
    return datetime.now(timezone.utc)


def timestamp(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def created_routine(body):
    """The routine in Hevy's answer to POST /v1/routines, which may wrap it in a one-item list; else None."""
    routine = body.get("routine") if isinstance(body, dict) else None
    if isinstance(routine, list) and len(routine) == 1:
        routine = routine[0]
    return routine if isinstance(routine, dict) and routine.get("id") else None


def _hevy_says(body):
    if isinstance(body, dict) and isinstance(body.get("error"), str):
        return body["error"]
    if isinstance(body, str) and body.strip():
        return body.strip()[:200]
    return None


class HevyClient:
    def __init__(self, transport, api_key, clock=None, sleep=None, *, audit_path=None, write_burst=WRITE_BURST):
        self.transport = transport
        self._api_key = api_key or ""
        self.clock = clock or _utc_now
        self.sleep = sleep or time.sleep
        self.audit_path = Path(audit_path) if audit_path else None
        self._bucket = TokenBucket(self.clock, self.sleep, burst=write_burst)

    @classmethod
    def from_context(cls, ctx):
        """A client for the instance: fixtures when COACH_HEVY_FIXTURES is set, else the real API.

        Raises ConfigError (exit 5) when the real API is needed and there is no key.
        """
        fixtures = bool(ctx.env.get(transport_module.FIXTURES_ENV))
        key = envfile.api_key(ctx.root, ctx.env)
        if key is None and not fixtures:
            raise ConfigError(
                f"No Hevy API key: set {envfile.KEY_NAME} in the environment or in .env at the instance root."
            )
        return cls(transport_module.from_env(ctx.env), key, clock=ctx.now, sleep=time.sleep,
                   audit_path=ctx.root / paths.HEVY_WRITES)

    def get(self, path, params=None):
        return self._send("GET", path, params=params)

    def paginate(self, path, key, page_size=10, params=None):
        page = 1
        while True:
            body = self.get(path, dict(params or {}, page=page, pageSize=page_size))
            yield from body.get(key) or []
            if page >= (body.get("page_count") or 0):
                return
            page += 1

    def put(self, path, body, *, routine_id=None, overlay_id=None, overlay_hash=None):
        return self._write("PUT", path, body, routine_id, overlay_id, overlay_hash)

    def post(self, path, body, *, routine_id=None, overlay_id=None, overlay_hash=None):
        return self._write("POST", path, body, routine_id, overlay_id, overlay_hash)

    def _write(self, method, path, body, routine_id, overlay_id, overlay_hash):
        if self.audit_path is None:
            raise RuntimeError("HevyClient writes need an audit_path")
        if routine_id is None:
            match = _ROUTINE_PATH.match(path)
            routine_id = match.group(1) if match else None
        line = {
            "schema_version": AUDIT_VERSION, "at": timestamp(self.clock()), "kind": "write", "method": method,
            "path": path, "status": None, "routine_id": routine_id, "overlay_id": overlay_id,
            "overlay_hash": overlay_hash, "request_body": body, "request_sha256": jsonio.canonical_hash(body),
        }
        try:
            result = self._send(method, path, body=body, line=line)
            if method == "POST" and path == "/v1/routines" and line["routine_id"] is None:
                line["routine_id"] = (created_routine(result) or {}).get("id")
        finally:
            self._append(line)
        return result if isinstance(result, dict) else {"text": result}

    def _append(self, line):
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(line, ensure_ascii=False, separators=(",", ":"))
        with open(self.audit_path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(self._scrub(text) + "\n")

    def _scrub(self, text):
        # Hevy keys are UUIDs; scrubbing a stub key of a few characters would mangle the text.
        if len(self._api_key) < 8:
            return text
        return text.replace(self._api_key, f"[{envfile.KEY_NAME}]")

    def _send(self, method, path, params=None, body=None, line=None):
        headers = {"api-key": self._api_key} if self._api_key else {}
        for attempt in range(1, MAX_ATTEMPTS_ON_429 + 1):
            if method != "GET":
                self._bucket.acquire()
                if line is not None:
                    line["at"] = timestamp(self.clock())
            try:
                response = self.transport.request(method, path, params=params, body=body, headers=headers)
            except TransportTimeout:
                raise NetworkError(f"Hevy did not answer {method} {path} in time; try again later.") from None
            except TransportUnreachable as exc:
                raise NetworkError(self._scrub(f"Could not reach Hevy for {method} {path}: {exc}.")) from None
            if line is not None:
                line["status"] = response.status
            if response.status != 429:
                return self._result(method, path, response)
            if attempt < MAX_ATTEMPTS_ON_429:
                self.sleep(BACKOFF_SECONDS)
        raise NetworkError(
            f"Hevy kept answering 429 (too many requests) to {method} {path} after "
            f"{MAX_ATTEMPTS_ON_429} tries {BACKOFF_SECONDS} s apart; try again in a few minutes."
        )

    def _result(self, method, path, response):
        status = response.status
        if 200 <= status < 300:
            return response.body if response.body is not None else {}
        said = _hevy_says(response.body)
        suffix = f": {said}" if said else ""
        if status in (401, 403):
            raise ConfigError(self._scrub(
                f"Hevy refused {method} {path} (HTTP {status}{suffix}); check {envfile.KEY_NAME} "
                "(Hevy Pro is required for the API)."
            ))
        if status >= 500:
            raise NetworkError(self._scrub(f"Hevy failed {method} {path} with HTTP {status}{suffix}."))
        raise HevyRequestError(self._scrub(f"Hevy rejected {method} {path} (HTTP {status}){suffix}."),
                               status, response.body)
