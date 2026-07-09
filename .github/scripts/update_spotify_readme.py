from __future__ import annotations

import base64
import html
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


README_PATH = Path(os.environ.get("README_PATH", "README.md"))
PROFILE_URL = os.environ.get(
    "SPOTIFY_PROFILE_URL",
    "https://open.spotify.com/user/andrew.peter.link?si=7e84c22874c04bc3",
)
START_MARKER = "<!-- spotify-start -->"
END_MARKER = "<!-- spotify-end -->"


def request_json(url: str, *, data: bytes | None = None, headers: dict[str, str] | None = None) -> tuple[int, dict]:
    request = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8")
            return response.status, json.loads(payload) if payload else {}
    except urllib.error.HTTPError as error:
        payload = error.read().decode("utf-8")
        return error.code, json.loads(payload) if payload else {}


def get_access_token() -> str | None:
    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
    refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN", "")

    if not client_id or not client_secret or not refresh_token:
        return None

    auth = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    body = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
    ).encode("utf-8")
    status, payload = request_json(
        "https://accounts.spotify.com/api/token",
        data=body,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    if status != 200:
        return None
    return payload.get("access_token")


def get_now_playing(token: str) -> tuple[str, dict | None]:
    status, payload = request_json(
        "https://api.spotify.com/v1/me/player/currently-playing",
        headers={"Authorization": "Bearer " + token},
    )
    if status == 204:
        return "offline", None
    if status != 200:
        return "unavailable", None
    if not payload.get("is_playing") or not payload.get("item"):
        return "offline", None
    return "playing", payload


def render_section(state: str, now_playing: dict | None) -> str:
    if state == "setup":
        message = "🎧 Spotify now playing will show here after the repo secrets are connected."
    elif state == "unavailable":
        message = "🎧 Spotify status is unavailable right now."
    elif state == "offline":
        message = "🎧 Not playing anything on Spotify right now."
    else:
        message = ""

    if state != "playing" or not now_playing:
        return f"""{START_MARKER}
<div align="center">
  <a href="{PROFILE_URL}">
    <strong>{message}</strong>
  </a>
  <br />
  <sub>Powered by a GitHub Actions refresh instead of a third-party widget.</sub>
</div>
{END_MARKER}"""

    item = now_playing["item"]
    track_name = html.escape(item.get("name", "Unknown track"))
    artists = html.escape(", ".join(artist["name"] for artist in item.get("artists", [])) or "Unknown artist")
    album = html.escape(item.get("album", {}).get("name", "Unknown album"))
    track_url = item.get("external_urls", {}).get("spotify", PROFILE_URL)
    images = item.get("album", {}).get("images", [])
    image_url = images[0]["url"] if images else ""
    image_html = f'  <a href="{track_url}"><img src="{image_url}" width="280" alt="Album art for {track_name} by {artists}" /></a>\n' if image_url else ""

    return f"""{START_MARKER}
<div align="center">
{image_html}  <a href="{track_url}">
    <strong>🎧 {track_name}</strong>
  </a>
  <br />
  <sub>{artists} • {album}</sub>
</div>
{END_MARKER}"""


def update_readme(section: str) -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    start = readme.find(START_MARKER)
    end = readme.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        raise RuntimeError("Spotify markers were not found in README.md")

    updated = readme[:start] + section + readme[end + len(END_MARKER) :]
    README_PATH.write_text(updated, encoding="utf-8")


def main() -> None:
    token = get_access_token()
    if not token:
        update_readme(render_section("setup", None))
        return

    state, now_playing = get_now_playing(token)
    update_readme(render_section(state, now_playing))


if __name__ == "__main__":
    main()
