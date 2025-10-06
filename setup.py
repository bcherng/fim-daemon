from setuptools import setup

setup(
    name="fim-daemon",
    version="1.0.0",
    description="File Integrity Monitoring Daemon (Python)",
    author="bcherng",
    packages=["src"],
    install_requires=["watchdog"],
    entry_points={
        "console_scripts": [
            "fim-daemon=src.windows:main",
        ],
    },
)
