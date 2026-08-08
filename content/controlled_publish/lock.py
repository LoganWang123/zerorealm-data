"""Durable release lock — prevents concurrent execute on the same RC."""

from __future__ import annotations

import json
import os
import socket
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from content.controlled_publish.errors import RELEASE_LOCKED, ControlledPublishError
from utils.helpers import now_iso


def _parse_iso(ts: str) -> float:
    from datetime import datetime

    return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


@dataclass
class ReleaseLock:
    release_candidate_id: str
    locked_by: str
    locked_at: str
    expires_at: str
    run_id: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ReleaseLock:
        return cls(
            release_candidate_id=str(data["release_candidate_id"]),
            locked_by=str(data["locked_by"]),
            locked_at=str(data["locked_at"]),
            expires_at=str(data["expires_at"]),
            run_id=str(data.get("run_id") or ""),
        )


class ReleaseLockStore:
    """JSON file lock store under data/state (runtime only — never commit)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _load(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return dict(raw.get("locks") or {})

    def _save(self, locks: dict[str, dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"locks": locks, "updated_at": now_iso()}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def status(self, release_candidate_id: str, *, now_ts: float | None = None) -> ReleaseLock | None:
        locks = self._load()
        data = locks.get(release_candidate_id)
        if not data:
            return None
        lock = ReleaseLock.from_dict(data)
        now = now_ts if now_ts is not None else _parse_iso(now_iso())
        if _parse_iso(lock.expires_at) <= now:
            locks.pop(release_candidate_id, None)
            self._save(locks)
            return None
        return lock

    def acquire(
        self,
        release_candidate_id: str,
        *,
        owner: str | None = None,
        ttl_seconds: int = 900,
        now_iso_ts: str | None = None,
    ) -> ReleaseLock:
        from datetime import datetime, timedelta, timezone

        locks = self._load()
        now_s = now_iso_ts or now_iso()
        now_dt = datetime.fromisoformat(now_s.replace("Z", "+00:00"))
        existing = locks.get(release_candidate_id)
        if existing:
            exp = datetime.fromisoformat(str(existing["expires_at"]).replace("Z", "+00:00"))
            if exp > now_dt:
                raise ControlledPublishError(
                    RELEASE_LOCKED,
                    f"RC locked by {existing.get('locked_by')} until {existing.get('expires_at')}",
                )
            locks.pop(release_candidate_id, None)

        locked_by = owner or f"{socket.gethostname()}:{os.getpid()}"
        lock = ReleaseLock(
            release_candidate_id=release_candidate_id,
            locked_by=locked_by,
            locked_at=now_s,
            expires_at=(now_dt + timedelta(seconds=ttl_seconds)).isoformat(),
            run_id=f"run-{uuid.uuid4().hex[:12]}",
        )
        locks[release_candidate_id] = lock.to_dict()
        self._save(locks)
        return lock

    def release(self, release_candidate_id: str, *, owner: str | None = None) -> bool:
        locks = self._load()
        existing = locks.get(release_candidate_id)
        if not existing:
            return False
        if owner and existing.get("locked_by") != owner:
            raise ControlledPublishError(
                RELEASE_LOCKED,
                f"Lock owned by {existing.get('locked_by')}, not {owner}",
            )
        locks.pop(release_candidate_id, None)
        self._save(locks)
        return True
