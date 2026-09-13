# Legacy Bash script

`main.sh` is the original implementation of Pen-Andro, kept here for
reference. It has been superseded by the `pen_andro` Python package in the
repository root — see the top-level `README.md` for the current tool.

It is **not maintained** and should not be used for new setups: it has no
tests, hardcodes `127.0.0.1:8080` for Burp, refuses to run with more than
one ADB device attached, and downloads several APKs/modules from
third-party mirrors with no version pinning.
