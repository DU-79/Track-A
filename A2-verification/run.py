#!/usr/bin/env python3

import os
import sys

SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
sys.path.insert(0, SRC_DIR)

from pipeline import main

if __name__ == "__main__":
    main()
