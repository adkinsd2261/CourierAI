"""Use installed ffmpeg, or the wheel's bundled executable. No network download here."""
import shutil
import sys
from pathlib import Path


def prepare():
    existing = shutil.which("ffmpeg")
    if existing:
        return existing
    target = Path(sys.executable).parent / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    if not target.exists():
        import imageio_ffmpeg
        shutil.copy2(imageio_ffmpeg.get_ffmpeg_exe(), target)
    return str(target)


if __name__ == "__main__":
    print(prepare())
