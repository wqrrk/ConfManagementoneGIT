import argparse
import os
import socket
import tkinter as tk
from pathlib import Path
from datetime import datetime
from xml.etree import ElementTree as ET

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
        ET.SubElement(ev, "source").text = source  # "interactive" | "script"
        tree.write(p, encoding="utf-8", xml_declaration=True)
    except Exception:
        pass



class App(tk.Tk):
    def __init__(self, vfs_path, log_path, script_path):
        super().__init__()
        self.title("Console Simulator — Stage 2")
        self.geometry("800x500")

        self.text = tk.Text(self)
        self.text.pack(fill="both", expand=True)

        self.user = get_username()
        self.host = get_hostname()
        self.cwd = "~"
        self.vfs_path = vfs_path
        self.log_file = ensure_xml_log(log_path)
        self.script = Path(script_path) if script_path else None

        self.prompt_index = None

        # клавиши
        self.text.bind("<Return>", self.on_enter)
        self.text.bind("<BackSpace>", self.on_backspace)
        self.text.bind("<Left>", self.on_left)
        self.text.bind("<Button-1>", lambda e: self.after(1, self.fix_cursor))

        # Показать отладочную инфу о переданных путях
        self.print_line("# Debug parameters")
        self.print_line(f"VFS path   : {self.vfs_path or '(none)'}")
        self.print_line(f"Log (XML)  : {str(self.log_file) if self.log_file else '(none)'}")
        self.print_line(f"Startup script: {str(self.script) if self.script else '(none)'}")
        self.print_line("----------------------------------------")

        self.show_prompt()
        self.text.focus_set()

        if self.script:
            self.after(200, self.run_script)

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
        self.cwd = (self.cwd.rstrip("/") + "/" if self.cwd != "~" else "~/") + target

    def cmd_ls(self, args):
        self.print_line(f"Command: ls, args: {', '.join(args) if args else '(no args)'}")

    def run_script(self):
        try:
            text = self.script.read_text(encoding="utf-8")
        except Exception as e:
            self.print_line("[SCRIPT ERROR] " + str(e))
            self.show_prompt()
            return
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
            except Exception as e:
                self.print_line("[SCRIPT ERROR] " + str(e))
        self.show_prompt()


def main():
    parser = argparse.ArgumentParser(description="Simple console simulator (Stage 2): params, XML log, startup script")
    parser.add_argument("--vfs", default=None, help="Path to VFS root (stored only; no FS access at Stage 2)")
    parser.add_argument("--log", default=None, help="Path to XML log file")
    parser.add_argument("--script", default=None, help="Path to startup script")
    args = parser.parse_args()

    app = App(args.vfs, args.log, args.script)
    app.mainloop()

if __name__ == "__main__":
    main()
