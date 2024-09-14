import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from hwilib.udevinstaller import UDevInstaller, _resource_path

from bitcoin_usb.i18n import translate


class UDevWrapper:
    def find_filename_in_dir(self, filename: str, dir: Path) -> Optional[Path]:
        """
        Searches for a file in the specified directory that matches the filename exactly.
        Returns the Path object for the file if found, otherwise None.

        Args:
        filename (str): The exact filename to search for.
        dir (Path): The directory path to search in.

        Returns:
        Optional[Path]: The path to the file that matches the filename exactly, or None if no match is found.
        """
        if not dir.is_dir():
            return None

        # Iterate over all files in the directory
        for file in dir.iterdir():
            if file.is_file() and file.name == filename:
                return file

        # Return None if no file was found
        return None

    def get_udev_destination(
        self,
    ) -> Path:
        return Path("/etc/udev/rules.d/")

    def get_udev_source(self, absolute: bool) -> str:
        source_dir = "udev"
        return _resource_path(source_dir) if absolute else source_dir

    def linux_execute_sudo_script(self, script_content: str):
        terminals = ["konsole", "gnome-terminal", "xterm", "lxterminal", "xfce4-terminal"]

        # Create a temporary file to write the shell script
        with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".sh") as temp_script:
            # Write commands to temp file
            temp_script.write("#!/bin/bash\n")
            temp_script.write(f"""echo '{translate("bitcoin_usb","Executing the script")}:'\n""")
            temp_script.write("echo '''\n" + script_content + "\n'''\n")
            temp_script.write(script_content)  # Add actual commands to be executed after confirmation
            temp_script_path = temp_script.name

        # Make the temporary script executable
        os.chmod(temp_script_path, 0o755)

        # Command to be executed with sudo
        full_cmd = f"bash {temp_script_path}"

        # Find a terminal emulator that is available and execute the script
        try:
            found_terminal = False
            for terminal in terminals:
                if shutil.which(terminal):
                    found_terminal = True
                    exec_cmd = [terminal, "-e", full_cmd]
                    if terminal == "konsole":
                        exec_cmd = [terminal, "-e", full_cmd]  # Removed --hold
                    elif terminal in ["gnome-terminal", "xfce4-terminal"]:
                        exec_cmd = [terminal, "-x", full_cmd]
                    subprocess.run(exec_cmd)
                    break
            if not found_terminal:
                print(translate("bitcoin_usb", "No suitable terminal emulator found."), file=sys.stderr)
                return False
        finally:
            # Optionally remove the script after execution
            os.unlink(temp_script_path)

        return True

    def _linux_cmd_install_udev(
        self,
    ) -> bool:
        "Needs root permission.  So actually execute it with sudo_linux_cmd_install_udev"
        source_dir = self.get_udev_source(absolute=False)
        destination = self.get_udev_destination()
        installer = UDevInstaller()
        print(f"Copies the rules from {self.get_udev_source(absolute=True)} to {destination}")
        return installer.install(source=str(source_dir), location=str(destination))

    def linux_cmd_install_udev_as_sudo(self, sleep=3):
        "Calls python as sudo and runs _linux_cmd_install_udev"
        python_executable_path = sys.executable
        script_content = f"""
                        #!/bin/bash
                        sudo {python_executable_path} {Path(__file__).absolute()} --install_linux_udev
                        sleep {sleep}
                        """
        self.linux_execute_sudo_script(script_content)

    def _all_files_present(self, source: Path, destination: Path, file_extension: str) -> bool:
        """
        Checks if all files with a specific file extension in the 'source' directory are present in the 'destination' directory.

        Args:
        source (Path): Path to the source directory.
        destination (Path): Path to the destination directory.
        file_ending (str): The file extension to filter by, e.g., '.rules'.

        Returns:
        bool: True if all files with the specified file extension from the source are present in the destination, False otherwise.
        """
        if not source.is_dir() or not destination.is_dir():
            return False  # Return False if either path is not a directory

        # Gather filenames with the specified file extension from source directory
        source_files = {
            file.name for file in source.iterdir() if file.is_file() and file.suffix == file_extension
        }

        # Gather filenames with the specified file extension from destination directory
        destination_files = {
            file.name for file in destination.iterdir() if file.is_file() and file.suffix == file_extension
        }

        # Check if all filtered files from the source are in the destination
        return source_files <= destination_files  # Subset check

    def all_udev_files_installed(self) -> bool:
        source = Path(self.get_udev_source(absolute=True))
        destination = self.get_udev_destination()

        return self._all_files_present(source, destination, file_extension="rule")


if __name__ == "__main__":
    # since
    import argparse

    parser = argparse.ArgumentParser(description="Can install the udev rules")
    parser.add_argument("--install_linux_udev", action="store_true")
    parser.add_argument("--test", action="store_true")

    args = parser.parse_args()

    udev_wrapper = UDevWrapper()
    if args.install_linux_udev:
        if udev_wrapper._linux_cmd_install_udev():
            print(translate("bitcoin_usb", "Successfully installed the udev rules"))
        else:
            print(translate("bitcoin_usb", "Could not install udev rules"))

        if udev_wrapper.all_udev_files_installed():
            print(translate("bitcoin_usb", "All udev files were successfully copied"))

    else:
        udev_wrapper.linux_cmd_install_udev_as_sudo()
