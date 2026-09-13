"""Minimal Tkinter GUI for Pen-Andro.

Uses only the standard library (no extra dependency) so it works anywhere
Python's Tk bindings are installed. The CLI (cli.py) and interactive menu
(menu.py) remain the primary interfaces; this is for users who'd rather
click buttons than type commands.
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import scrolledtext

from . import adb as adb_mod
from . import android_apps, frida_tools, network, pc_tools
from . import burp as burp_mod
from .config import load_config


class PenAndroGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Pen-Andro")
        self.cfg = load_config()
        self.cfg.workdir.mkdir(parents=True, exist_ok=True)
        self.log_queue: queue.Queue[str] = queue.Queue()

        actions = [
            ("Run full setup", self.run_all),
            ("Install Burp certificate", self.run_cert),
            ("Install PC tools", self.run_pc_tools),
            ("Install Frida server", self.run_frida_server),
            ("Check Frida versions", self.run_frida_check),
            ("Install Android apps", self.run_apps),
        ]
        button_frame = tk.Frame(root)
        button_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)
        for label, handler in actions:
            tk.Button(button_frame, text=label, command=handler, width=22).pack(side=tk.LEFT, padx=4)

        self.log_box = scrolledtext.ScrolledText(root, width=110, height=32, state="disabled")
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.root.after(200, self._drain_log_queue)

    def log(self, message: str) -> None:
        self.log_queue.put(message)

    def _drain_log_queue(self) -> None:
        while not self.log_queue.empty():
            message = self.log_queue.get_nowait()
            self.log_box.configure(state="normal")
            self.log_box.insert(tk.END, message + "\n")
            self.log_box.see(tk.END)
            self.log_box.configure(state="disabled")
        self.root.after(200, self._drain_log_queue)

    def _run_in_thread(self, task) -> None:
        def wrapped():
            try:
                task()
            except Exception as exc:
                self.log(f"ERROR: {exc}")

        threading.Thread(target=wrapped, daemon=True).start()

    def _device(self) -> str:
        device = adb_mod.resolve_device(self.cfg.device_serial)
        self.log(f"adb connected: {device.serial}")
        if not adb_mod.check_root(device.serial):
            raise RuntimeError("Root access denied; grant root to adb and retry.")
        return device.serial

    def run_all(self) -> None:
        def task():
            if not network.has_internet():
                self.log("No internet connectivity.")
                return
            serial = self._device()
            pc_tools.install_missing()
            frida_tools.install_pc_tools()
            self.log(str(android_apps.install_all(serial, self.cfg.workdir)))
            version = frida_tools.ensure_frida_server(serial, self.cfg.workdir, prefer_magisk=self.cfg.prefer_magisk)
            self.log(f"frida-server ready: {version}")
            if burp_mod.is_burp_running(self.cfg.burp.host, self.cfg.burp.port):
                try:
                    name = burp_mod.install_certificate(
                        serial, self.cfg.burp.host, self.cfg.burp.port, self.cfg.workdir
                    )
                    self.log(f"Certificate installed: {name}")
                except burp_mod.BurpError as exc:
                    self.log(str(exc))
            self.log("Setup complete. Reboot the device to apply changes.")

        self._run_in_thread(task)

    def run_cert(self) -> None:
        def task():
            serial = self._device()
            if not burp_mod.is_burp_running(self.cfg.burp.host, self.cfg.burp.port):
                self.log(f"Burp not reachable at {self.cfg.burp.host}:{self.cfg.burp.port}")
                return
            name = burp_mod.install_certificate(
                serial, self.cfg.burp.host, self.cfg.burp.port, self.cfg.workdir, force=True
            )
            self.log(f"Installed {name}. Reboot to apply.")

        self._run_in_thread(task)

    def run_pc_tools(self) -> None:
        def task():
            missing = pc_tools.install_missing()
            self.log(f"Still missing: {missing}" if missing else "jadx/apktool/scrcpy ready.")
            frida_tools.install_pc_tools()
            self.log("frida & objection ready.")

        self._run_in_thread(task)

    def run_frida_server(self) -> None:
        def task():
            serial = self._device()
            version = frida_tools.ensure_frida_server(serial, self.cfg.workdir, prefer_magisk=self.cfg.prefer_magisk)
            self.log(f"frida-server ready: {version}")

        self._run_in_thread(task)

    def run_frida_check(self) -> None:
        def task():
            serial = self._device()
            self.log(str(frida_tools.check_version_mismatch(serial)))

        self._run_in_thread(task)

    def run_apps(self) -> None:
        def task():
            serial = self._device()
            self.log(str(android_apps.install_all(serial, self.cfg.workdir)))

        self._run_in_thread(task)


def main():
    root = tk.Tk()
    PenAndroGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
