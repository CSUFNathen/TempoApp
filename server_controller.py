# server_controller.py
import os, subprocess, threading, time

try:
    import psutil
except Exception:
    psutil = None


# ---- helpers: parse sizes like "2G", "1024M" into bytes ----
def _parse_mem_string_to_bytes(s: str | None) -> int | None:
    if not s:
        return None
    s = s.strip().upper()
    mult = 1
    if s.endswith("G"):
        mult = 1024 ** 3
        s = s[:-1]
    elif s.endswith("M"):
        mult = 1024 ** 2
        s = s[:-1]
    elif s.endswith("K"):
        mult = 1024
        s = s[:-1]
    try:
        return int(float(s) * mult)
    except Exception:
        return None


class ServerController:
    def __init__(self, on_output=None, on_exit=None):
        self.on_output = on_output or (lambda s: None)
        self.on_exit = on_exit or (lambda rc: None)
        self.proc = None
        self.proc_ps = None
        self.server_root = None  # directory where the server files live

    def find_jar(self, pattern="*.jar", search_dirs=None):
        import glob
        search_dirs = search_dirs or [os.getcwd()]
        matches = []
        for d in search_dirs:
            matches.extend(glob.glob(os.path.join(d, pattern)))
        matches.sort()
        return matches[0] if matches else ""

    def start(self, jar_path, min_ram, max_ram, use_nogui=True, server_root=None):
        if not jar_path or not os.path.isfile(jar_path):
            raise FileNotFoundError("Server jar not found.")

        # Always run the server with cwd = jar folder (server root)
        self.server_root = server_root or os.path.dirname(os.path.abspath(jar_path))

        cmd = ["java", f"-Xms{min_ram}", f"-Xmx{max_ram}", "-jar", jar_path]
        if use_nogui:
            cmd.append("nogui")

        creationflags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = subprocess.CREATE_NO_WINDOW  # Windows only

        self.proc = subprocess.Popen(
            cmd,
            cwd=self.server_root,  # important: world/eula/logs in the right place
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1,
            creationflags=creationflags,
        )
        self.proc_ps = psutil.Process(self.proc.pid) if (psutil and self.proc and self.proc.pid) else None
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        try:
            for line in self.proc.stdout:
                self.on_output(line.rstrip("\n"))
        except Exception as e:
            self.on_output(f"[reader] {e}")
        finally:
            rc = self.proc.poll()
            self.on_output(f"> Server exited with code {rc}")
            self.proc_ps = None
            self.on_exit(rc)

    def send_command(self, raw, echo=True):
        if raw and self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.write(raw + "\n")
                self.proc.stdin.flush()
                if echo:
                    self.on_output(f"> {raw}")
                return True
            except Exception as e:
                self.on_output(f"ERROR sending command: {e}")
        return False

    def stop(self):
        if not self.proc or self.proc.poll() is not None:
            return
        try:
            if self.proc.stdin:
                self.proc.stdin.write("stop\n")
                self.proc.stdin.flush()
        except Exception:
            pass

        def _wait_then_terminate():
            time.sleep(5)
            if self.proc and self.proc.poll() is None:
                self.proc.terminate()

        threading.Thread(target=_wait_then_terminate, daemon=True).start()

    def is_running(self):
        return bool(self.proc and self.proc.poll() is None)

    # ---- RAM verification ----
    def get_heap_limits(self):
        """
        Returns {'initial': bytes|None, 'max': bytes|None, 'source': 'jcmd'|'cmdline'|'unknown'}
        for the running Java process, or None if not running.
        """
        if not self.proc or self.proc.poll() is not None:
            return None
        pid = self.proc.pid

        # 1) Try jcmd (JDK on PATH) with a short timeout
        try:
            exe = "jcmd.exe" if os.name == "nt" else "jcmd"
            res = subprocess.run(
                [exe, str(pid), "VM.flags"],
                capture_output=True, text=True, timeout=2
            )
            if res.returncode == 0 and res.stdout:
                out = res.stdout
                init = None
                maxh = None
                for tok in out.replace("\n", " ").split():
                    if tok.startswith("-XX:InitialHeapSize="):
                        try: init = int(tok.split("=", 1)[1])
                        except Exception: pass
                    elif tok.startswith("-XX:MaxHeapSize="):
                        try: maxh = int(tok.split("=", 1)[1])
                        except Exception: pass
                if init is not None or maxh is not None:
                    return {"initial": init, "max": maxh, "source": "jcmd"}
        except Exception:
            pass

        # 2) Fallback: parse the process command line (-Xms / -Xmx)
        cmdline = None
        try:
            if psutil and self.proc_ps:
                cmdline = self.proc_ps.cmdline()
        except Exception:
            cmdline = None
        if not cmdline:
            try:
                cmdline = list(self.proc.args) if isinstance(self.proc.args, (list, tuple)) else None
            except Exception:
                cmdline = None

        if cmdline:
            def _find_flag(flag):
                # "-Xms2G" style
                for arg in cmdline:
                    if isinstance(arg, str) and arg.startswith(flag):
                        return _parse_mem_string_to_bytes(arg[len(flag):])
                # "-Xms", "2G" split style
                for i in range(len(cmdline) - 1):
                    if cmdline[i] == flag:
                        return _parse_mem_string_to_bytes(str(cmdline[i + 1]))
                return None

            init = _find_flag("-Xms")
            maxh = _find_flag("-Xmx")
            if init is not None or maxh is not None:
                return {"initial": init, "max": maxh, "source": "cmdline"}

        return {"initial": None, "max": None, "source": "unknown"}

    # ---- EULA helpers use server_root ----
    def check_eula_state(self, root=None):
        root = root or self.server_root or os.getcwd()
        path = os.path.join(root, "eula.txt")
        if not os.path.exists(path):
            return (False, False)
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            return (True, "eula=true" in content.lower())
        except Exception:
            return (True, False)

    def accept_eula(self, root=None):
        root = root or self.server_root or os.getcwd()
        path = os.path.join(root, "eula.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("eula=true\n")
        self.on_output("EULA accepted.")
