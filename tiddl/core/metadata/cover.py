import requests
import shutil

from pathlib import Path
from logging import getLogger

log = getLogger(__name__)


class Cover:
    uid: str
    url: str
    data: bytes | None

    def __init__(self, uid: str, size=1280) -> None:
        self.uid = uid

        if size > 1280:
            log.warning(f"can not set cover size higher than 1280 (user set: {size})")
            size = 1280

        formatted_uid = uid.replace("-", "/")

        self.url = (
            f"https://resources.tidal.com/images/{formatted_uid}/{size}x{size}.jpg"
        )

        self.data = None

    def fetch_data(self) -> bytes:
        req = requests.get(self.url)

        if req.status_code != 200:
            log.error(f"could not download cover. ({req.status_code}) {self.url}")
            self.data = b""
            return b""

        log.debug(f"got cover data of {self.url}")

        self.data = req.content

        return req.content

    def save_to_directory(self, path: Path, filename: str = "cover.jpg"):
        """Save the cover inside ``path`` instead of beside the album directory."""
        file = path / Path(filename).name
        legacy_file = path.with_suffix(".jpg")

        if file.exists():
            log.debug(f"cover exists ({file})")
            return

        # Previous releases stored ``Album.jpg`` next to the ``Album``
        # directory. Reuse it when present, so existing downloads are fixed
        # even if the artwork endpoint is temporarily unavailable.
        if legacy_file.exists() and legacy_file.is_file():
            file.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(legacy_file), str(file))
                log.debug(f"moved legacy cover ({legacy_file} -> {file})")
                return
            except OSError as exc:
                log.warning(f"could not move legacy cover ({legacy_file}): {exc}")

        if not self.data:
            self.data = self.fetch_data()

            if not self.data:
                log.debug(f"cover data is empty ({file})")
                return

        file.parent.mkdir(parents=True, exist_ok=True)

        try:
            file.write_bytes(self.data)
        except FileNotFoundError as e:
            log.error(f"could not save cover. {file} -> {e}")
