import argparse
import os
import socket
import tkinter as tk
from pathlib import Path
from datetime import datetime
from xml.etree import ElementTree as ET
import base64


def get_username():
    return os.getenv("USER") or os.getenv("USERNAME") or "user"


def get_hostname():
    try:
        return socket.gethostname()
    except Exception:
        return "localhost"


def ensure_xml_log(path):
    if not path:
        return None
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        root = ET.Element("log")
        ET.ElementTree(root).write(p, encoding="utf-8", xml_declaration=True)
    return p


def xml_log(p, user, host, cmd, args, cwd, source):
    if not p:
        return
    try:
        tree = ET.parse(p)
        root = tree.getroot()
        ev = ET.SubElement(root, "event")
        ET.SubElement(ev, "user").text = user
        ET.SubElement(ev, "host").text = host
        ET.SubElement(ev, "datetime").text = datetime.now().isoformat(timespec="seconds")
        ET.SubElement(ev, "command").text = cmd
        ET.SubElement(ev, "args").text = " ".join(args)
        ET.SubElement(ev, "cwd").text = cwd
        ET.SubElement(ev, "source").text = source
        tree.write(p, encoding="utf-8", xml_declaration=True)
    except Exception:
        pass


def _vfs_dir():
    return {"type": "dir", "children": {}}


def load_vfs_from_xml(xml_path: Path | None):
    if not xml_path:
        return _vfs_dir()
    p = Path(xml_path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"VFS XML not found: {p}")
    tree = ET.parse(p)
    root = tree.getroot()

    def build(elem):
        if elem.tag == "dir":
            node = _vfs_dir()
            for ch in elem:
                if ch.tag == "dir":
                    node["children"][ch.get("name")] = build(ch)
                elif ch.tag == "file":
                    name = ch.get("name")
                    is_b64 = (ch.get("base64") == "true")
                    raw = ch.text or ""
                    if is_b64:
                        try:
                            data = base64.b64decode(raw.encode("utf-8"))
                        except Exception:
                            data = b""
                        node["children"][name] = {"type": "file", "binary": True, "data": data}
                    else:
                        node["children"][name] = {"type": "file", "binary": False, "data": raw}
            return node
        elif elem.tag == "file":
            is_b64 = (elem.get("base64") == "true")
            raw = elem.text or ""
            if is_b64:
                try:
                    data = base64.b64decode(raw.encode("utf-8"))
                except Exception:
                    data = b""
                return {"type": "file", "binary": True, "data": data}
            return {"type": "file", "binary": False, "data": raw}
        else:
            return _vfs_dir()

    vroot = build(root)
    if vroot.get("type") != "dir":
        wrapper = _vfs_dir()
        wrapper["children"]["root"] = vroot
        vroot = wrapper
    return vroot


def path_parts(cwd: str):
    if cwd == "~":
        return []
    return [p for p in cwd.strip("~/").split("/") if p]


def vfs_walk(vroot, parts):
    node = vroot
    for name in parts:
        if node.get("type") != "dir":
            return None
        node = node["children"].get(name)
        if node is None:
            return None
    return node


class App(tk.Tk):
    def __init__(self, vfs_xml_path, log_path, script_path):
        super().__init__()
        self.title("Console Simulator — Stage 3")
        self.geometry("800x520")

        self.text = tk.Text(self)
        self.text.pack(fill="both", expand=True)

        self.user = get_username()
        self.host = get_hostname()
        self.cwd = "~"

        self.vfs_path = Path(vfs_xml_path).expanduser().resolve() if vfs_xml_path else None
        try:
            self.vroot = load_vfs_from_xml(self.vfs_path)
            self.vfs_error = None
        except Exception as e:
            self.vroot = _vfs_dir()
            self.vfs_error = str(e)

        self.log_file = ensure_xml_log(log_path)
        self.script = Path(script_path).expanduser().resolve() if script_path else None

        self.prompt_index = None

        self.text.bind("<Return>", self.on_enter)
        self.text.bind("<BackSpace>", self.on_backspace)
        self.text.bind("<Left>", self.on_left)
        self.text.bind("<Button-1>", lambda e: self.after(1, self.fix_cursor))

        self.print_line("# Debug parameters")
        self.print_line(f"VFS XML    : {str(self.vfs_path) if self.vfs_path else '(none)'}")
        self.print_line(f"Log (XML)  : {str(self.log_file) if self.log_file else '(none)'}")
        self.print_line(f"Startup script: {str(self.script) if self.script else '(none)'}")
        if self.vfs_error:
            self.print_line(f"[VFS ERROR] {self.vfs_error}")
        self.print_line("----------------------------------------")

        # motd
        motd = self.vroot["children"].get("motd") if self.vroot.get("type") == "dir" else None
        if isinstance(motd, dict) and motd.get("type") == "file" and not motd.get("binary"):
            text = (motd.get("data") or "").strip()
            if text:
                self.print_line(text)
                self.print_line("----------------------------------------")

        self.show_prompt()
        self.text.focus_set()

        if self.script:
            if not self.script.exists() or not self.script.is_file():
                self.print_line(f"[SCRIPT ERROR] File not found: {self.script}")
            else:
                self.after(150, self.run_script)

    # basics
    def prompt(self):
        return f"{self.user}@{self.host}:{self.cwd}$ "

    def show_prompt(self):
        self.text.insert("end", self.prompt())
        self.prompt_index = self.text.index("insert")

    def print_line(self, s=""):
        self.text.insert("end", s + "\n")
        self.text.see("end")

    def current_input(self):
        return self.text.get(self.prompt_index, "end-1c")

    def at_start(self):
        return self.text.compare("insert", "<=", self.prompt_index)

    def on_backspace(self, _):
        if self.at_start():
            return "break"

    def on_left(self, _):
        if self.text.compare("insert -1c", "<", self.prompt_index):
            return "break"

    def fix_cursor(self):
        if self.at_start():
            self.text.mark_set("insert", "end")

    # core
    def on_enter(self, _):
        line = self.current_input().strip()
        self.print_line()
        self.execute(line, source="interactive")
        self.show_prompt()
        return "break"

    def execute(self, line, source):
        if not line:
            return
        parts = line.split()
        cmd, *args = parts
        xml_log(self.log_file, self.user, self.host, cmd, args, self.cwd, source)

        if cmd == "exit":
            self.print_line("Exiting")
            self.after(100, self.destroy)
            return
        if cmd == "echo":
            self.print_line(" ".join(args))
            return
        if cmd == "cd":
            self.cmd_cd(args)
            return
        if cmd == "ls":
            self.cmd_ls(args)
            return
        if cmd == "cat":
            self.cmd_cat(args)
            return
        self.print_line(f"Unknown cmd '{cmd}'")


    def cmd_cd(self, args):
        if len(args) > 1:
            self.print_line("Err: Illegal args for 'cd' (1 required)")
            return
        target = args[0] if args else "~"
        if target in ("~", "/"):
            self.cwd = "~"
            return
        if target == ".":
            return
        if target == "..":
            if self.cwd != "~":
                self.cwd = ("~/" + "/".join(self.cwd.strip("~/").split("/")[:-1])).rstrip("/") or "~"
            return
        new_cwd = (self.cwd.rstrip("/") + "/" if self.cwd != "~" else "~/") + target
        node = vfs_walk(self.vroot, path_parts(new_cwd))
        if not node or node.get("type") != "dir":
            self.print_line("Err: no such directory in VFS: " + target)
            return
        self.cwd = new_cwd

    def cmd_ls(self, args):
        if args:
            self.print_line("Err: ls doesn't take arguments (Stage 3 simplified)")
            return
        node = vfs_walk(self.vroot, path_parts(self.cwd))
        if not node or node.get("type") != "dir":
            self.print_line("Err: current directory is invalid")
            return
        names = []
        for name, child in node["children"].items():
            names.append(name + ("/" if child.get("type") == "dir" else ""))
        names.sort()
        self.print_line("  ".join(names) if names else "(empty)")

    def cmd_cat(self, args):
        if len(args) != 1:
            self.print_line("Usage: cat <file>")
            return
        node = vfs_walk(self.vroot, path_parts(self.cwd))
        if not node or node.get("type") != "dir":
            self.print_line("Err: current directory is invalid")
            return
        child = node["children"].get(args[0])
        if not child or child.get("type") != "file":
            self.print_line("Err: no such file: " + args[0])
            return
        if child.get("binary"):
            self.print_line(f"[binary file] {len(child.get('data') or b'')} bytes")
        else:
            self.print_line(child.get("data") or "")

    def run_script(self):
        try:
            text = self.script.read_text(encoding="utf-8")
        except Exception as e:
            self.print_line("[SCRIPT ERROR] " + str(e))
            self.show_prompt()
            return
        executed = 0
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if raw.startswith("#"):
                self.print_line(raw)
                continue
            self.text.insert("end", self.prompt() + line + "\n")
            try:
                self.execute(line, source="script")
                executed += 1
            except Exception as e:
                self.print_line("[SCRIPT ERROR] " + str(e))
        if executed == 0:
            self.print_line("[SCRIPT] Нет команд для выполнения")
        self.show_prompt()


def main():
    parser = argparse.ArgumentParser(description="Console simulator (Stage 3): in-memory VFS + Stage 2 features")
    parser.add_argument("--vfs", default=None, help="Path to VFS XML file")
    parser.add_argument("--log", default=None, help="Path to XML log file")
    parser.add_argument("--script", default=None, help="Path to startup script")
    args = parser.parse_args()

    app = App(args.vfs, args.log, args.script)
    app.mainloop()


if __name__ == "__main__":
    main()
