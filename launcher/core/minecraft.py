"""Обёртка над minecraft-launcher-lib: установка версий/загрузчиков и запуск."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable, Optional

import requests
import minecraft_launcher_lib as mll
from minecraft_launcher_lib import command, install, java_utils, mod_loader, utils

from .config import CONFIG


class MinecraftError(Exception):
    pass


# id загрузчика -> отображаемое имя
LOADERS = {
    "vanilla": "Vanilla",
    "fabric": "Fabric",
    "forge": "Forge",
    "neoforge": "NeoForge",
    "quilt": "Quilt",
}


class Minecraft:
    def __init__(self, game_dir: Optional[str] = None) -> None:
        self.game_dir = str(game_dir or CONFIG.game_dir)

    # --- информация о версиях ----------------------------------------------

    def installed_versions(self) -> list[str]:
        try:
            return [v["id"] for v in utils.get_installed_versions(self.game_dir)]
        except Exception:
            return []

    def all_versions(self) -> list[dict]:
        try:
            out = []
            for v in utils.get_version_list():
                out.append({"id": v["id"], "type": v["type"], "releaseTime": v.get("releaseTime", "")})
            return out
        except Exception as e:
            raise MinecraftError(f"Не удалось получить список версий: {e}")

    def release_versions(self) -> list[str]:
        return [v["id"] for v in self.all_versions() if v["type"] == "release"]

    # --- Java ---------------------------------------------------------------

    def java_candidates(self) -> list[str]:
        found: list[str] = []
        try:
            found = list(java_utils.find_system_java_versions())
        except Exception:
            found = []
        extra = [
            os.path.join(os.environ.get("ProgramFiles", ""), "Java"),
            os.path.join(os.environ.get("ProgramFiles", ""), "Eclipse Adoptium"),
            os.path.join(os.environ.get("ProgramFiles", ""), "Microsoft", "jdk"),
        ]
        for base in extra:
            if base and os.path.isdir(base):
                for root, _dirs, files in os.walk(base):
                    if "java.exe" in files:
                        found.append(os.path.join(root, "java.exe"))
        seen, result = set(), []
        for p in found:
            if p and p not in seen:
                seen.add(p)
                result.append(p)
        return result

    def _resolve_java(self, path: Optional[str]) -> Optional[str]:
        """Превращает путь к java.exe, папке JDK или bin в путь к java.exe."""
        if not path:
            return None
        p = Path(path)
        if p.is_file():
            return str(p)
        if p.is_dir():
            for rel in ("bin/java.exe", "bin/java", "java.exe", "java"):
                cand = p / rel
                if cand.is_file():
                    return str(cand)
        return None

    def find_best_java(self) -> Optional[str]:
        configured = self._resolve_java(CONFIG.get("java_path"))
        if configured:
            return configured
        best, best_ver = None, -1
        for path in self.java_candidates():
            exe = self._resolve_java(path)
            if not exe:
                continue
            try:
                info = java_utils.get_java_information(path)
                if isinstance(info, dict):
                    ver = info.get("version")
                else:
                    ver = getattr(info, "version", None)
                major = int(str(ver).split(".")[0]) if ver else 0
            except Exception:
                major = 0
            if major > best_ver:
                best, best_ver = exe, major
        return best

    # --- Установка ----------------------------------------------------------

    def install(
        self,
        minecraft_version: str,
        loader_id: str = "vanilla",
        callback: Optional[dict] = None,
        java: Optional[str] = None,
    ) -> str:
        """Устанавливает версию/загрузчик, возвращает id готовой для запуска версии."""
        try:
            if loader_id in ("", None, "vanilla"):
                install.install_minecraft_version(minecraft_version, self.game_dir, callback=callback)
                return minecraft_version
            ml = mod_loader.get_mod_loader(loader_id)
            return ml.install(
                minecraft_version,
                self.game_dir,
                callback=callback,
                java=java or self.find_best_java(),
            )
        except mll.exceptions.VersionNotFound:
            raise MinecraftError(f"Версия {minecraft_version} не найдена")
        except mll.exceptions.UnsupportedVersion:
            raise MinecraftError(f"{loader_id} не поддерживает {minecraft_version}")
        except Exception as e:
            raise MinecraftError(str(e))

    # --- Запуск -------------------------------------------------------------

    def build_command(
        self,
        version_id: str,
        username: str,
        uuid: str,
        token: str,
        ram_mb: int = 4096,
    ) -> list[str]:
        options = {
            "username": username,
            "uuid": uuid.replace("-", ""),
            "token": token or ("0" * 32),
            "executablePath": self.find_best_java() or "java",
            "jvmArguments": [f"-Xmx{ram_mb}M", f"-Xms{min(ram_mb, 2048)}M"],
            "launcherName": "PixelPeak",
            "launcherVersion": "1.0.0",
            "gameDirectory": self.game_dir,
        }
        try:
            return command.get_minecraft_command(version_id, self.game_dir, options)
        except Exception as e:
            raise MinecraftError(f"Ошибка запуска: {e}")

    def is_installed(self, version_id: str) -> bool:
        return version_id in self.installed_versions()

    # --- FPS / графика ------------------------------------------------------

    def apply_video_settings(self, max_fps: int = 260, vsync: bool = False) -> None:
        """Прописывает лимит FPS и VSync в options.txt (снимает кап 60)."""
        opts = Path(self.game_dir) / "options.txt"
        try:
            lines = opts.read_text(encoding="utf-8").splitlines() if opts.exists() else []
        except Exception:
            lines = []

        def setkey(key: str, value: str) -> None:
            for i, line in enumerate(lines):
                if line.split(":", 1)[0] == key:
                    lines[i] = f"{key}:{value}"
                    return
            lines.append(f"{key}:{value}")

        try:
            fps = int(max_fps) or 260
        except Exception:
            fps = 260
        setkey("maxFps", str(fps))
        setkey("enableVsync", "true" if vsync else "false")
        try:
            opts.parent.mkdir(parents=True, exist_ok=True)
            opts.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception:
            pass

    # --- скин в игре (CustomSkinLoader) ------------------------------------

    def install_skin_loader(self, mc_version: str, loader_id: str) -> Optional[str]:
        if loader_id in ("", None, "vanilla"):
            return None
        loader = {"fabric": "fabric", "forge": "forge", "neoforge": "neoforge", "quilt": "quilt"}.get(loader_id)
        if not loader:
            return None

        headers = {"User-Agent": "PixelPeak/1.0.0 (github.com/matvey-matvey123/pixelpeak)"}
        mods = Path(self.game_dir) / "mods"

        def _remove_existing() -> None:
            if mods.is_dir():
                for f in mods.glob("CustomSkinLoader*.jar"):
                    try:
                        f.unlink()
                    except OSError:
                        pass

        # Ищем версию ТОЛЬКО с точным совпадением game_version. На неподдерживаемых
        # версиях CustomSkinLoader крашит игру при загрузке, поэтому лучше пропустить.
        try:
            r = requests.get(
                "https://api.modrinth.com/v2/project/customskinloader/version",
                params={
                    "loaders": json.dumps([loader]),
                    "game_versions": json.dumps([mc_version]),
                },
                headers=headers,
                timeout=20,
            )
            versions = r.json() if r.ok else []
        except Exception:
            versions = []

        if not versions:
            _remove_existing()
            return None

        files = versions[0].get("files") or []
        primary = next((f for f in files if f.get("primary")), files[0] if files else None)
        if not primary or not primary.get("url"):
            raise MinecraftError("Не удалось получить ссылку на CustomSkinLoader")
        url, fname = primary["url"], primary.get("filename") or "CustomSkinLoader.jar"

        try:
            content = requests.get(url, headers=headers, timeout=90).content
        except Exception as e:
            raise MinecraftError(f"Не удалось скачать скин-загрузчик: {e}")

        mods.mkdir(parents=True, exist_ok=True)
        _remove_existing()
        (mods / fname).write_bytes(content)

        root = (CONFIG.get("api_base") or "").rstrip("/") + "/api/csl/"
        el = Path(self.game_dir) / "CustomSkinLoader" / "ExtraList"
        el.mkdir(parents=True, exist_ok=True)
        (el / "pixelpeak.json").write_text(
            json.dumps(
                {"name": "PixelPeak", "type": "CustomSkinAPI", "root": root},
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
        return fname
