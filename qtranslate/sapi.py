"""Offline SAPI TTS fallback — port of FUN_00448BEC (SpVoice via COM).

Native: CoCreateInstance({29333BF9-7B36-11D2-B20E-00C04F983E60}) -> OleRun
-> ISpVoice::Speak. Used by TaskListenText when online mp3 fails.

Requires: pip install comtypes   (pure-CTypes IDispatch late-binding is
possible but fragile; comtypes is the maintained path.)
"""
import subprocess


def speak(text: str, rate: int = 0) -> None:
    """Speak with system SAPI voices (offline, no network)."""
    try:
        import comtypes.client  # type: ignore
    except ImportError:
        # No-dependency fallback: PowerShell SAPI via stdin (same engine).
        import base64
        ps = (
            "$v=New-Object -ComObject SAPI.SpVoice;"
            f"$v.Rate={int(rate)};"
            "[void]$v.Speak([Console]::In.ReadToEnd())"
        )
        enc = base64.b64encode(ps.encode("utf-16-le")).decode()
        r = subprocess.run(
            ["powershell", "-NoProfile", "-EncodedCommand", enc],
            input=text.encode("utf-8"), capture_output=True, timeout=60)
        if r.returncode:
            raise RuntimeError(
                "SAPI unavailable (pip install comtypes, or enable "
                "Windows speech voices). stderr: "
                + r.stderr.decode(errors="replace")[:200])
        return
    voice = comtypes.client.CreateObject("SAPI.SpVoice")
    voice.Rate = rate
    voice.Speak(text)


if __name__ == "__main__":
    speak("Hello")
