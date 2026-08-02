"""微信公众号 API 客户端.

封装 access_token / 素材上传 / 草稿 / 发布等接口。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

TOKEN_CACHE = Path(".cache/token.json")
BASE_URL = "https://api.weixin.qq.com"

# 错误码映射
ERROR_MAP = {
    40001: "access_token 无效或过期",
    40007: "media_id 无效",
    45009: "接口调用超过限制",
    40014: "access_token 不合法",
}


class WechatAPIError(Exception):
    """微信 API 错误."""

    def __init__(self, errcode: int, errmsg: str):
        self.errcode = errcode
        self.errmsg = errmsg
        friendly = ERROR_MAP.get(errcode, errmsg)
        super().__init__(f"WeChat API Error {errcode}: {friendly}")


class WechatClient:
    """微信公众号 API 客户端."""

    def __init__(self, app_id: str, app_secret: str):
        self._app_id = app_id
        self._app_secret = app_secret
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # Access Token
    # ------------------------------------------------------------------

    def get_access_token(self) -> str:
        """获取 access_token（带本地缓存）."""
        cached = self._load_token_cache()
        if cached:
            return cached

        resp = self._get(
            f"{BASE_URL}/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": self._app_id,
                "secret": self._app_secret,
            },
            timeout=10,
        )
        data = resp.json()
        if "access_token" not in data:
            raise WechatAPIError(data.get("errcode", -1), data.get("errmsg", "unknown"))

        # 缓存（提前 200s 过期）
        token_data = {
            "access_token": data["access_token"],
            "expires_at": time.time() + data.get("expires_in", 7200) - 200,
        }
        self._save_token_cache(token_data)
        return data["access_token"]

    # ------------------------------------------------------------------
    # 素材上传
    # ------------------------------------------------------------------

    def upload_permanent_image(self, path: str) -> dict:
        """上传永久图片素材（封面用）."""
        token = self.get_access_token()
        with open(path, "rb") as f:
            resp = self._post(
                f"{BASE_URL}/cgi-bin/material/add_material",
                params={"access_token": token, "type": "image"},
                files={"media": f},
                timeout=30,
            )
        return self._check_response(resp)

    def upload_content_image(self, path: str) -> str:
        """上传正文图片（返回微信 CDN URL）."""
        token = self.get_access_token()
        with open(path, "rb") as f:
            resp = self._post(
                f"{BASE_URL}/cgi-bin/media/uploadimg",
                params={"access_token": token},
                files={"media": f},
                timeout=30,
            )
        data = self._check_response(resp)
        return data["url"]

    def upload_permanent_video(
        self,
        path: str,
        title: str,
        introduction: str,
    ) -> dict:
        """Upload a reusable permanent video material."""
        token = self.get_access_token()
        description = json.dumps(
            {"title": title, "introduction": introduction},
            ensure_ascii=False,
        )
        with open(path, "rb") as media_file:
            resp = self._post(
                f"{BASE_URL}/cgi-bin/material/add_material",
                params={"access_token": token, "type": "video"},
                data={"description": description},
                files={"media": media_file},
                timeout=120,
            )
        return self._check_response(resp)

    # ------------------------------------------------------------------
    # 草稿
    # ------------------------------------------------------------------

    def create_draft(self, articles: list[dict]) -> str:
        """新建草稿，返回 media_id."""
        token = self.get_access_token()
        resp = self._post_utf8_json(
            f"{BASE_URL}/cgi-bin/draft/add",
            params={"access_token": token},
            payload={"articles": articles},
            timeout=30,
        )
        data = self._check_response(resp)
        return data["media_id"]

    def update_draft(self, media_id: str, index: int, article: dict) -> dict:
        """更新草稿."""
        token = self.get_access_token()
        resp = self._post_utf8_json(
            f"{BASE_URL}/cgi-bin/draft/update",
            params={"access_token": token},
            payload={"media_id": media_id, "index": index, "articles": article},
            timeout=30,
        )
        return self._check_response(resp)

    def get_draft(self, media_id: str) -> dict:
        """读取指定草稿，用于创建后的内容核验."""
        token = self.get_access_token()
        resp = self._post_utf8_json(
            f"{BASE_URL}/cgi-bin/draft/get",
            params={"access_token": token},
            payload={"media_id": media_id},
            timeout=30,
        )
        return self._check_response(resp)

    def delete_draft(self, media_id: str) -> dict:
        """Delete the specified draft."""
        token = self.get_access_token()
        resp = self._post_utf8_json(
            f"{BASE_URL}/cgi-bin/draft/delete",
            params={"access_token": token},
            payload={"media_id": media_id},
            timeout=30,
        )
        return self._check_response(resp)

    # ------------------------------------------------------------------
    # 群发素材
    # ------------------------------------------------------------------

    def create_mass_article(self, articles: list[dict]) -> str:
        """Create permanent mpnews material for an explicit follower send."""
        token = self.get_access_token()
        resp = self._post_utf8_json(
            f"{BASE_URL}/cgi-bin/material/add_news",
            params={"access_token": token},
            payload={"articles": articles},
            timeout=30,
        )
        data = self._check_response(resp)
        return data["media_id"]

    # ------------------------------------------------------------------
    # 发表 / 群发通知
    # ------------------------------------------------------------------

    def submit_publish(self, media_id: str) -> str:
        """自由发表，返回 publish_id；不会通知关注者."""
        token = self.get_access_token()
        resp = self._post(
            f"{BASE_URL}/cgi-bin/freepublish/submit",
            params={"access_token": token},
            json={"media_id": media_id},
            timeout=30,
        )
        data = self._check_response(resp)
        return data.get("publish_id", "")

    def send_mass_article(self, media_id: str) -> str:
        """Send one mpnews item to all followers and return its message id."""
        token = self.get_access_token()
        resp = self._post(
            f"{BASE_URL}/cgi-bin/message/mass/sendall",
            params={"access_token": token},
            json={
                "filter": {"is_to_all": True},
                "mpnews": {"media_id": media_id},
                "msgtype": "mpnews",
                "send_ignore_reprint": 0,
            },
            timeout=30,
        )
        data = self._check_response(resp)
        return str(data.get("msg_id", ""))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_response(self, resp: requests.Response) -> dict:
        """检查响应，抛出友好错误."""
        try:
            data = json.loads(resp.content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            data = resp.json()
        errcode = data.get("errcode", 0)
        if errcode != 0:
            raise WechatAPIError(errcode, data.get("errmsg", ""))
        return data

    def _post_utf8_json(
        self,
        url: str,
        *,
        params: dict,
        payload: dict,
        timeout: int,
    ) -> requests.Response:
        """Send literal UTF-8 JSON for WeChat endpoints that store article text."""
        return self._post(
            url,
            params=params,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=timeout,
        )

    def _get(self, url: str, **kwargs) -> requests.Response:
        """Issue a GET without exposing credential-bearing URLs on failure."""
        try:
            return self._session.get(url, **kwargs)
        except requests.RequestException as exc:
            self._raise_redacted_network_error(exc)

    def _post(self, url: str, **kwargs) -> requests.Response:
        """Issue a POST without exposing access tokens on failure."""
        try:
            return self._session.post(url, **kwargs)
        except requests.RequestException as exc:
            self._raise_redacted_network_error(exc)

    @staticmethod
    def _raise_redacted_network_error(exc: requests.RequestException) -> None:
        safe_cause = exc.__class__(
            "WeChat request failed (sensitive query parameters redacted)"
        )
        raise WechatAPIError(-1, "Unable to reach WeChat API") from safe_cause

    def _load_token_cache(self) -> str | None:
        if not TOKEN_CACHE.exists():
            return None
        try:
            with open(TOKEN_CACHE, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("expires_at", 0) > time.time():
                return data["access_token"]
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    def _save_token_cache(self, data: dict) -> None:
        TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_CACHE, "w", encoding="utf-8") as f:
            json.dump(data, f)
