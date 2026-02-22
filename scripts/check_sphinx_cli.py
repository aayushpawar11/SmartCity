import subprocess
import sys
import shutil


def run(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def main():
    path = shutil.which("sphinx-cli")
    if not path:
        print("ERROR: sphinx-cli not found on PATH")
        sys.exit(1)
    print(f"sphinx-cli found at: {path}")

    result = run(["sphinx-cli", "chat", "--help"])
    print(result.stdout[:1500])

    if result.returncode != 0:
        print("ERROR: sphinx-cli not working")
        sys.exit(result.returncode)

    print("OK: sphinx-cli is available and help command works.")


if __name__ == "__main__":
    main()
