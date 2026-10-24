"""Allow ``python -m mddoctor``."""

import sys

from mddoctor.cli import main

if __name__ == "__main__":
    sys.exit(main())
