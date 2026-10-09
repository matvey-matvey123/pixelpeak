"""Обёртка над minecraft-launcher-lib: установка версий/загрузчиков и запуск."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

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

    def find_best_java(self) -> Optional[str]:
        configured = CONFIG.get("java_path")
        if configured and Path(configured).exists():
            return configured
        candidates = self.java_candidates()
        best, best_ver = None, -1
        for path in candidates:
            try:
                info = java_utils.get_java_information(path)
                ver = getattr(info, "version", None) or (info.get("version") if isinstance(info, dict) else 0)
                major = int(str(ver).split(".")[0]) if ver else 0
            except Exception:
                major = 0
            if major > best_ver:
                best, best_ver = path, major
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
