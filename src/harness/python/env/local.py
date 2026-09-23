"""The local env: runs on the laptop.

This is part of the env seam (a behavior seam). Every path goes through
a safe_path check that keeps the agent inside one working folder.
Tools call this module and never touch the disk directly.
"""
