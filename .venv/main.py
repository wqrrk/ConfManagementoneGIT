import os
import socket
import tkinter as tk

def get_username() -> str:
    return os.getenv("USER") or os.getenv("USERNAME") or "user"

def get_hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "localhost"

def handle_ls(args):
    return f"Command: ls, args: {', '.join(args) if args else '(no args)'}"

def handle_cd(args):
    if len(args) > 1:
        return "Err: Illegal args for 'cd' (1 required)"
    return f"Command: cd, args: {args[0] if args else '(no args)'}"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Console Simulator")
        self.text = tk.Text(self)
        self.text.pack(fill="both", expand=True)

        self.username = get_username()
        self.hostname = get_hostname()
        self.cwd = "~"
        self.prompt_index = None  # где начинается ввод

        self.text.bind("<Return>", self.on_enter)
        self.text.bind("<BackSpace>", self.on_backspace)
        self.text.bind("<Left>", self.on_left)
        self.text.bind("<Button-1>", self.on_click)

        self.show_prompt()
        self.text.focus_set()

    def prompt(self):
        return f"{self.username}@{self.hostname}:{self.cwd}$ "

    def show_prompt(self):
        self.text.insert("end", self.prompt())
        self.prompt_index = self.text.index("insert")

    def current_input(self):
        return self.text.get(self.prompt_index, "end-1c")

    def print_line(self, s: str = ""):
        self.text.insert("end", s + "\n")
        self.text.see("end")

    def at_input_start(self):
        return self.text.compare("insert", "<=", self.prompt_index)

    def on_backspace(self, _):
        if self.at_input_start():
            return "break"

    def on_left(self, _):
        pos = self.text.index("insert -1c")
        if self.text.compare(pos, "<", self.prompt_index):
            return "break"

    def on_click(self, _):
        self.after(1, self._fix_cursor)

    def _fix_cursor(self):
        if self.at_input_start():
            self.text.mark_set("insert", "end")

    def on_enter(self, _):
        line = self.current_input().strip()
        self.print_line()
        self.execute(line)
        self.show_prompt()
        return "break"

    def execute(self, line: str):
        if not line:
            return
        parts = line.split()
        cmd, *args = parts

        if cmd == "exit":
            self.print_line("Exiting")
            self.after(100, self.destroy)
            return
        if cmd == "ls":
            self.print_line(handle_ls(args))
            return
        if cmd == "cd":
            self.print_line(handle_cd(args))
            if not args:
                self.cwd = "~"
            elif len(args) == 1 and args[0] not in (".", "..", "/"):
                self.cwd = (self.cwd.rstrip("/") + "/" if self.cwd != "~" else "~/") + args[0]
            return

        self.print_line(f"Unknown cmd '{cmd}'")
if __name__ == "__main__":
    App().mainloop()