from wfglink.cli import main

# The guard matters: process worker mode spawns a child that imports this module again.
if __name__ == "__main__":
    raise SystemExit(main())
