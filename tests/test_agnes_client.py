import base64

import pytest

from publishing.media_generation.client import AgnesAPIError, AgnesClient


class FakeResponse:
    def __init__(self, status_code=200, payload=None, content=b""):
        self.status_code = status_code
        self._payload = payload
        self.content = content

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, post_responses=None, get_responses=None):
        self.post_responses = list(post_responses or [])
        self.get_responses = list(get_responses or [])
        self.requests = []

    def post(self, url, **kwargs):
        self.requests.append(("POST", url, kwargs))
        return self.post_responses.pop(0)

    def get(self, url, **kwargs):
        self.requests.append(("GET", url, kwargs))
        return self.get_responses.pop(0)


def test_generate_image_decodes_base64_and_sends_openai_compatible_payload():
    encoded = base64.b64encode(b"png-bytes").decode("ascii")
    session = FakeSession(
        post_responses=[FakeResponse(payload={"data": [{"b64_json": encoded}]})]
    )
    client = AgnesClient(api_key="test-key", session=session)

    image = client.generate_image("retail intelligence", "900x383")

    assert image == b"png-bytes"
    method, url, request = session.requests[0]
    assert method == "POST"
    assert url == "https://apihub.agnes-ai.com/v1/images/generations"
    assert request["headers"]["Authorization"] == "Bearer test-key"
    assert request["json"] == {
        "model": "agnes-image-2.1-flash",
        "prompt": "retail intelligence",
        "n": 1,
        "size": "900x383",
        "response_format": "b64_json",
    }


def test_generate_image_downloads_url_response():
    session = FakeSession(
        post_responses=[
            FakeResponse(payload={"data": [{"url": "https://cdn.example/image.png"}]})
        ],
        get_responses=[FakeResponse(content=b"downloaded-png")],
    )
    client = AgnesClient(api_key="test-key", session=session)

    image = client.generate_image("retail intelligence", "1280x720")

    assert image == b"downloaded-png"
    assert session.requests[1][0:2] == ("GET", "https://cdn.example/image.png")


def test_generate_video_polls_until_complete_and_downloads_output():
    session = FakeSession(
        post_responses=[FakeResponse(payload={"video_id": "video-123"})],
        get_responses=[
            FakeResponse(payload={"status": "queued"}),
            FakeResponse(
                payload={
                    "status": "completed",
                    "data": {"video_url": "https://cdn.example/short.mp4"},
                }
            ),
            FakeResponse(content=b"mp4-bytes"),
        ],
    )
    client = AgnesClient(
        api_key="test-key",
        session=session,
        sleeper=lambda _: None,
    )

    video = client.generate_video(
        prompt="vertical retail intelligence animation",
        aspect_ratio="9:16",
        duration_seconds=15,
        poll_interval_seconds=0,
        poll_timeout_seconds=30,
    )

    assert video == b"mp4-bytes"
    method, url, request = session.requests[0]
    assert method == "POST"
    assert url == "https://apihub.agnes-ai.com/v1/videos"
    assert request["json"] == {
        "model": "agnes-video-v2.0",
        "prompt": "vertical retail intelligence animation",
        "aspect_ratio": "9:16",
        "duration": 15,
    }
    assert session.requests[1][1].endswith("/agnesapi?video_id=video-123")


def test_generate_video_raises_non_retryable_error_for_failed_task():
    session = FakeSession(
        post_responses=[FakeResponse(payload={"id": "video-123"})],
        get_responses=[
            FakeResponse(payload={"status": "failed", "error": {"message": "policy rejected"}})
        ],
    )
    client = AgnesClient(api_key="test-key", session=session, sleeper=lambda _: None)

    with pytest.raises(AgnesAPIError, match="policy rejected") as exc_info:
        client.generate_video("prompt", "9:16", 15, 0, 30)

    assert exc_info.value.retryable is False


def test_generate_video_times_out_without_unbounded_polling():
    times = iter([0.0, 0.0, 31.0])
    session = FakeSession(
        post_responses=[FakeResponse(payload={"task_id": "video-123"})],
        get_responses=[FakeResponse(payload={"status": "queued"})],
    )
    client = AgnesClient(
        api_key="test-key",
        session=session,
        sleeper=lambda _: None,
        monotonic=lambda: next(times),
    )

    with pytest.raises(AgnesAPIError, match="timed out") as exc_info:
        client.generate_video("prompt", "9:16", 15, 0, 30)

    assert exc_info.value.retryable is True
    poll_requests = [request for request in session.requests if "agnesapi" in request[1]]
    assert len(poll_requests) == 1


@pytest.mark.parametrize(
    ("status_code", "retryable"),
    [(401, False), (403, False), (429, True), (500, True)],
)
def test_http_errors_are_classified_without_leaking_api_key(status_code, retryable):
    session = FakeSession(
        post_responses=[
            FakeResponse(
                status_code=status_code,
                payload={"error": {"message": "request rejected"}},
            )
        ]
    )
    client = AgnesClient(api_key="secret-agnes-key", session=session)

    with pytest.raises(AgnesAPIError) as exc_info:
        client.generate_image("prompt", "900x383")

    assert exc_info.value.retryable is retryable
    assert "secret-agnes-key" not in str(exc_info.value)
