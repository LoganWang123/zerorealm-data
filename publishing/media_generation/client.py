"""Small, testable Agnes image and video API client."""

from __future__ import annotations

import base64
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

import requests


class AgnesAPIError(RuntimeError):
    """A redacted provider error with retry guidance."""

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class AgnesClient:
    """Call Agnes without exposing provider details to publishing code."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://apihub.agnes-ai.com/v1",
        image_model: str = "agnes-image-2.1-flash",
        video_model: str = "agnes-video-v2.0",
        video_create_path: str = "/videos",
        video_status_url_template: str | None = None,
        session: requests.Session | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        request_timeout_seconds: int = 300,
    ):
        if not api_key:
            raise ValueError("AGNES_API_KEY is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._image_model = image_model
        self._video_model = video_model
        self._video_create_path = "/" + video_create_path.lstrip("/")
        self._session = session or requests.Session()
        self._sleeper = sleeper
        self._monotonic = monotonic
        self._request_timeout_seconds = request_timeout_seconds

        parsed = urlsplit(self._base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        self._video_status_url_template = (
            video_status_url_template
            or f"{origin}/agnesapi?video_id={{video_id}}"
        )

    @property
    def image_model(self) -> str:
        return self._image_model

    @property
    def video_model(self) -> str:
        return self._video_model

    def generate_image(self, prompt: str, size: str) -> bytes:
        """Generate one image and return durable bytes."""
        response = self._post_json(
            f"{self._base_url}/images/generations",
            {
                "model": self._image_model,
                "prompt": prompt,
                "n": 1,
                "size": size,
            },
        )
        data = response.get("data")
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise AgnesAPIError("Agnes image response did not contain an output")

        output = data[0]
        encoded = output.get("b64_json")
        if isinstance(encoded, str) and encoded:
            return self._decode_base64(encoded)

        url = output.get("url")
        if isinstance(url, str) and url:
            if url.startswith("data:"):
                _, _, encoded_data = url.partition(",")
                return self._decode_base64(encoded_data)
            return self._download(url)

        raise AgnesAPIError("Agnes image response did not contain image data")

    def generate_video(
        self,
        prompt: str,
        aspect_ratio: str,
        duration_seconds: int,
        poll_interval_seconds: int,
        poll_timeout_seconds: int,
    ) -> bytes:
        """Create an async video task, poll it with a deadline, and download it."""
        task = self._post_json(
            f"{self._base_url}{self._video_create_path}",
            {
                "model": self._video_model,
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "duration": duration_seconds,
            },
        )
        video_id = self._find_first(task, ("video_id", "id", "task_id"))
        if not isinstance(video_id, str) or not video_id:
            raise AgnesAPIError("Agnes video response did not contain a task id")

        started_at = self._monotonic()
        poll_url = self._video_status_url_template.format(video_id=video_id)
        while self._monotonic() - started_at <= poll_timeout_seconds:
            payload = self._get_json(poll_url)
            status = self._find_first(payload, ("status", "state"))
            normalized = str(status or "").lower()

            if normalized in {"completed", "complete", "succeeded", "success"}:
                output_url = self._find_first(
                    payload,
                    ("video_url", "url", "output_url", "download_url"),
                )
                if not isinstance(output_url, str) or not output_url:
                    raise AgnesAPIError(
                        "Agnes completed the video task without an output URL"
                    )
                return self._download(output_url)

            if normalized in {"failed", "cancelled", "canceled", "rejected", "error"}:
                message = self._find_first(payload, ("message", "error_message"))
                if not isinstance(message, str):
                    error = payload.get("error")
                    message = error.get("message") if isinstance(error, dict) else None
                raise AgnesAPIError(
                    f"Agnes video generation failed: {message or normalized}",
                    retryable=False,
                )

            self._sleeper(poll_interval_seconds)

        raise AgnesAPIError("Agnes video generation timed out", retryable=True)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._session.post(
                url,
                headers=self._headers(),
                json=payload,
                timeout=self._request_timeout_seconds,
            )
        except requests.RequestException as exc:
            raise AgnesAPIError(
                "Unable to reach Agnes API",
                retryable=True,
            ) from exc
        return self._parse_json_response(response)

    def _get_json(self, url: str) -> dict[str, Any]:
        try:
            response = self._session.get(
                url,
                headers=self._headers(),
                timeout=self._request_timeout_seconds,
            )
        except requests.RequestException as exc:
            raise AgnesAPIError(
                "Unable to reach Agnes API",
                retryable=True,
            ) from exc
        return self._parse_json_response(response)

    def _download(self, url: str) -> bytes:
        try:
            response = self._session.get(
                url,
                timeout=self._request_timeout_seconds,
            )
        except requests.RequestException as exc:
            raise AgnesAPIError(
                "Unable to download generated Agnes media",
                retryable=True,
            ) from exc
        if not 200 <= response.status_code < 300:
            raise AgnesAPIError(
                f"Agnes media download failed with HTTP {response.status_code}",
                retryable=response.status_code == 429 or response.status_code >= 500,
            )
        if not response.content:
            raise AgnesAPIError("Agnes media download returned an empty file")
        return response.content

    @staticmethod
    def _parse_json_response(response) -> dict[str, Any]:
        if not 200 <= response.status_code < 300:
            retryable = response.status_code == 429 or response.status_code >= 500
            message = f"Agnes API request failed with HTTP {response.status_code}"
            try:
                payload = response.json()
                error = payload.get("error") if isinstance(payload, dict) else None
                detail = error.get("message") if isinstance(error, dict) else None
                if isinstance(detail, str) and detail:
                    message = f"{message}: {detail}"
            except (TypeError, ValueError):
                pass
            raise AgnesAPIError(message, retryable=retryable)
        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise AgnesAPIError("Agnes API returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise AgnesAPIError("Agnes API returned an unexpected response")
        return payload

    @staticmethod
    def _decode_base64(encoded: str) -> bytes:
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise AgnesAPIError("Agnes image response contained invalid Base64") from exc
        if not content:
            raise AgnesAPIError("Agnes image response contained an empty file")
        return content

    @classmethod
    def _find_first(cls, value: Any, keys: tuple[str, ...]) -> Any:
        if isinstance(value, dict):
            for key in keys:
                candidate = value.get(key)
                if candidate is not None:
                    return candidate
            for candidate in value.values():
                nested = cls._find_first(candidate, keys)
                if nested is not None:
                    return nested
        elif isinstance(value, list):
            for candidate in value:
                nested = cls._find_first(candidate, keys)
                if nested is not None:
                    return nested
        return None
