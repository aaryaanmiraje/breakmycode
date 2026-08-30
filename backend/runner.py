import subprocess
import tempfile
import os
import time
import signal
import uuid


# ============================================================
# DOCKER CONFIGURATION
# ============================================================

DOCKER_IMAGE = "break-my-code-sandbox"

COMPILE_TIMEOUT = 15
DEFAULT_RUN_TIMEOUT = 2

MEMORY_LIMIT = "256m"
CPU_LIMIT = "1"
PIDS_LIMIT = "64"


# ============================================================
# CPP PROGRAM
# ============================================================

class CppProgram:

    def __init__(
        self,
        code,
        use_sanitizer=True
    ):

        self.code = code
        self.use_sanitizer = use_sanitizer

        self.temp_dir = tempfile.TemporaryDirectory()

        self.source_file = os.path.join(
            self.temp_dir.name,
            "main.cpp"
        )

        self.build_dir = os.path.join(
            self.temp_dir.name,
            "build"
        )

        self.executable = os.path.join(
            self.build_dir,
            "main"
        )

        os.makedirs(
            self.build_dir,
            exist_ok=True
        )

        # ----------------------------------------------------
        # Save source code
        # ----------------------------------------------------

        with open(
            self.source_file,
            "w"
        ) as f:

            f.write(code)

        self.status = "success"
        self.error = ""

        # ----------------------------------------------------
        # Compile
        # ----------------------------------------------------

        self._compile()

    # ========================================================
    # COMMON DOCKER SECURITY OPTIONS
    # ========================================================

    def _docker_security_options(self):

        return [

            # No internet access
            "--network",
            "none",

            # Drop Linux capabilities
            "--cap-drop",
            "ALL",

            # Prevent privilege escalation
            "--security-opt",
            "no-new-privileges",

            # Memory limit
            "--memory",
            MEMORY_LIMIT,

            # Do not allow swap to bypass memory limit
            "--memory-swap",
            MEMORY_LIMIT,

            # CPU limit
            "--cpus",
            CPU_LIMIT,

            # Process limit
            "--pids-limit",
            PIDS_LIMIT,

            # Read-only root filesystem
            "--read-only",

            # Temporary writable filesystem
            "--tmpfs",
            "/tmp:rw,nosuid,size=64m"
        ]

    # ========================================================
    # COMPILE
    # ========================================================

    def _compile(self):

        command = [
            "docker",
            "run",

            "--rm",

            # ------------------------------------------------
            # Mount project directory
            # ------------------------------------------------

            "-v",
            f"{self.temp_dir.name}:/workspace",

            DOCKER_IMAGE,

            "g++",

            "/workspace/main.cpp",

            "-o",

            "/workspace/build/main",

            "-std=c++17"
        ]

        # ----------------------------------------------------
        # Sanitizers
        # ----------------------------------------------------

        if self.use_sanitizer:

            command.extend([
                "-fsanitize=address,undefined",
                "-fno-omit-frame-pointer",
                "-g"
            ])

        else:

            command.append("-g")

        # ----------------------------------------------------
        # Security options
        # ----------------------------------------------------

        security_options = (
            self._docker_security_options()
        )

        # Put Docker security options before image
        image_index = command.index(
            DOCKER_IMAGE
        )

        command[
            image_index:image_index
        ] = security_options

        # ----------------------------------------------------
        # Execute compilation
        # ----------------------------------------------------

        try:

            result = subprocess.run(
                command,

                capture_output=True,

                text=True,

                timeout=COMPILE_TIMEOUT
            )

        except FileNotFoundError:

            self.status = (
                "docker_unavailable"
            )

            self.error = (
                "Docker was not found. "
                "Make sure Docker Desktop is "
                "installed and running."
            )

            return

        except subprocess.TimeoutExpired:

            self.status = (
                "compile_timeout"
            )

            self.error = (
                f"Compilation exceeded "
                f"{COMPILE_TIMEOUT} seconds."
            )

            return

        # ----------------------------------------------------
        # Compilation failed
        # ----------------------------------------------------

        if result.returncode != 0:

            self.status = (
                "compile_error"
            )

            self.error = (
                result.stderr
            )

            return

        # ----------------------------------------------------
        # Success
        # ----------------------------------------------------

        self.status = "success"
        self.error = ""

    # ========================================================
    # RUN PROGRAM
    # ========================================================

    def run(
        self,
        user_input,
        timeout=DEFAULT_RUN_TIMEOUT
    ):

        if self.status != "success":

            return {
                "status": self.status,
                "stdout": "",
                "stderr": self.error,
                "exit_code": None,
                "runtime": 0
            }

        # ----------------------------------------------------
        # Unique container
        # ----------------------------------------------------

        container_name = (
            "bmc-" +
            uuid.uuid4().hex[:12]
        )

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # -i keeps STDIN attached to the container.
        #
        # Without this, cin >> n may not receive the
        # input supplied by Python.
        # ----------------------------------------------------

        command = [
            "docker",
            "run",

            "-i",

            "--rm",

            "--name",
            container_name,

            # ------------------------------------------------
            # Security
            # ------------------------------------------------

            "--network",
            "none",

            "--cap-drop",
            "ALL",

            "--security-opt",
            "no-new-privileges",

            # ------------------------------------------------
            # Resource limits
            # ------------------------------------------------

            "--memory",
            MEMORY_LIMIT,

            "--memory-swap",
            MEMORY_LIMIT,

            "--cpus",
            CPU_LIMIT,

            "--pids-limit",
            PIDS_LIMIT,

            # ------------------------------------------------
            # Filesystem
            # ------------------------------------------------

            "--read-only",

            "--tmpfs",
            "/tmp:rw,nosuid,size=64m",

            # ------------------------------------------------
            # Non-root
            # ------------------------------------------------

            "--user",
            "1000:1000",

            # ------------------------------------------------
            # Mount executable
            # ------------------------------------------------

            "-v",
            f"{self.build_dir}:/app:ro",

            DOCKER_IMAGE,

            "/app/main"
        ]

        start = time.perf_counter()

        process = None

        try:

            process = subprocess.Popen(
                command,

                stdin=subprocess.PIPE,

                stdout=subprocess.PIPE,

                stderr=subprocess.PIPE,

                text=True,

                start_new_session=True
            )

            stdout, stderr = process.communicate(
                input=user_input,
                timeout=timeout
            )

            runtime = (
                time.perf_counter()
                - start
            )

            # ------------------------------------------------
            # Successful program
            # ------------------------------------------------

            if process.returncode == 0:

                return {
                    "status": "success",
                    "stdout": stdout,
                    "stderr": stderr,
                    "exit_code": process.returncode,
                    "runtime": runtime
                }

            # ------------------------------------------------
            # Program exited with error
            # ------------------------------------------------

            return {
                "status": "runtime_error",
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": process.returncode,
                "runtime": runtime
            }

        except FileNotFoundError:

            return {
                "status": "docker_unavailable",
                "stdout": "",
                "stderr": (
                    "Docker command was not found. "
                    "Make sure Docker Desktop is running."
                ),
                "exit_code": None,
                "runtime": 0
            }

        except subprocess.TimeoutExpired:

            # ------------------------------------------------
            # Kill Python's docker client process
            # ------------------------------------------------

            try:

                os.killpg(
                    os.getpgid(
                        process.pid
                    ),
                    signal.SIGKILL
                )

            except (
                ProcessLookupError,
                AttributeError
            ):

                pass

            # ------------------------------------------------
            # Collect remaining output
            # ------------------------------------------------

            try:

                stdout, stderr = (
                    process.communicate()
                )

            except Exception:

                stdout = ""
                stderr = ""

            # ------------------------------------------------
            # Force remove container
            # ------------------------------------------------

            try:

                subprocess.run(
                    [
                        "docker",
                        "rm",
                        "-f",
                        container_name
                    ],

                    capture_output=True,

                    text=True,

                    timeout=5
                )

            except Exception:

                pass

            runtime = (
                time.perf_counter()
                - start
            )

            return {
                "status": "timeout",
                "stdout": stdout,
                "stderr": (
                    "Program exceeded "
                    "time limit"
                ),
                "exit_code": None,
                "runtime": runtime
            }

    # ========================================================
    # CLEANUP
    # ========================================================

    def close(self):

        try:

            self.temp_dir.cleanup()

        except Exception:

            pass


# ============================================================
# BACKWARDS COMPATIBILITY
# ============================================================

def run_cpp(
    code,
    user_input,
    timeout=DEFAULT_RUN_TIMEOUT
):

    program = CppProgram(
        code,
        use_sanitizer=True
    )

    try:

        return program.run(
            user_input,
            timeout
        )

    finally:

        program.close()