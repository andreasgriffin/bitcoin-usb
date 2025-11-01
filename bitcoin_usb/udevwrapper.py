import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from hwilib.udevinstaller import _resource_path

from bitcoin_usb.i18n import translate


class UDevWrapper:
    def list_rule_files(self) -> list[Path]:
        """
        Searches for a file in the specified directory that matches the filename exactly.
        Returns the Path object for the file if found, otherwise None.

        Args:
        filename (str): The exact filename to search for.
        dir (Path): The directory path to search in.

        Returns:
        Optional[Path]: The path to the file that matches the filename exactly, or None if no match is found.
        """
        files: list[Path] = []
        # Iterate over all files in the directory
        for file in self.get_udev_source(absolute=True).iterdir():
            if file.is_file() and file.name.endswith(".rules"):
                files.append(file)
        return files

    def get_udev_source(self, absolute: bool) -> Path:
        source_dir = Path("udev")
        return Path(_resource_path(str(source_dir))) if absolute else source_dir

    def linux_execute_sudo_script(self, script_content: str):
        terminals = [
            "konsole",
            "gnome-terminal",
            "xterm",
            "lxterminal",
            "xfce4-terminal",
        ]

        # Create a temporary file to write the shell script
        with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".sh") as temp_script:
            # Write commands to temp file
            temp_script.write("#!/bin/bash\n")
            temp_script.write(f"""echo '{translate("bitcoin_usb", "Executing the script")}:'\n""")
            temp_script.write("echo '''\n" + script_content + "\n'''\n")
            temp_script.write(script_content)  # Add actual commands to be executed after confirmation
            temp_script_path = temp_script.name

        # Make the temporary script executable
        os.chmod(temp_script_path, 0o755)

        # Find a terminal emulator that is available and execute the script
        try:
            found_terminal = False
            for terminal in terminals:
                if shutil.which(terminal):
                    found_terminal = True
                    if terminal == "konsole":
                        cmd = [terminal, "-e", "bash", temp_script_path]
                    elif terminal in ["gnome-terminal", "xfce4-terminal"]:
                        cmd = [terminal, "-x", "bash", temp_script_path]
                    else:
                        cmd = [terminal, "-e", "bash", temp_script_path]
                    subprocess.run(cmd)
                    break
            if not found_terminal:
                print(
                    translate("bitcoin_usb", "No suitable terminal emulator found."),
                    file=sys.stderr,
                )
                return False
        finally:
            # Optionally remove the script after execution
            os.unlink(temp_script_path)

        return True

    @staticmethod
    def copy_files(full_filenames: list[Path], target_dir: Path) -> None:
        """
        Copy a list of files to a target directory.

        Args:
        full_filenames (List[Path]): A list of paths to files that need to be copied.
        target_dir (Path): The directory to copy the files into.
        """
        for file_path in full_filenames:
            if file_path.is_file():
                shutil.copy(file_path, target_dir)
                print(f"Copied {file_path} to {target_dir}")

    def _create_udev_script(self, sleep=3) -> str:
        temp_dir = Path(tempfile.mkdtemp())

        filename_install_script = "install_udev.sh"
        files = self.list_rule_files() + [Path(__file__).absolute().parent / filename_install_script]
        self.copy_files(files, temp_dir)

        script_content = f"""
                        #!/bin/bash
                        sudo sh {(temp_dir / filename_install_script).absolute()} 
                        sleep {sleep}
                        """
        return script_content

    def linux_cmd_install_udev_as_sudo(self, sleep=3):
        script_content = self._create_udev_script(sleep=sleep)
        self.linux_execute_sudo_script(script_content)


if __name__ == "__main__":
    udev_wrapper = UDevWrapper()
    udev_wrapper.linux_cmd_install_udev_as_sudo()
