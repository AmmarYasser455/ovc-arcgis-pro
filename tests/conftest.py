# -*- coding: utf-8 -*-
"""Test setup: arcpy is provided by ArcGIS Pro, so stub it before imports."""
import os
import sys
from unittest.mock import MagicMock

sys.modules.setdefault("arcpy", MagicMock())

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
