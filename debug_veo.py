"""Standalone Veo diagnostics — run without starting the bot."""
from __future__ import annotations

import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

import config

print("=== Veo config ===")
print(f"VEO_API_KEY:          {'✅ set (' + config.VEO_API_KEY[:8] + '...)' if config.VEO_API_KEY else '❌ not set'}")
print(f"GOOGLE_SA_JSON:       {'✅ set' if config.GOOGLE_SA_JSON else '❌ not set'}")
print(f"GOOGLE_CLOUD_PROJECT: {config.GOOGLE_CLOUD_PROJECT or '❌ not set'}")
print(f"GOOGLE_CLOUD_LOCATION:{config.GOOGLE_CLOUD_LOCATION}")
print(f"VEO_MODEL:            {config.VEO_MODEL}")
print()

# Step 1: import
try:
    from google import genai
    print("✅ google-genai import ok")
except ImportError as e:
    print(f"❌ google-genai import failed: {e}")
    sys.exit(1)

# Step 2: client init
try:
    from video.veo import _make_client
    client = _make_client()
    print("✅ client init ok")
except Exception as e:
    print(f"❌ client init failed: {e}")
    sys.exit(1)

# Step 3: list models (free, no quota)
print()
print("=== Available Veo models ===")
try:
    models = list(client.models.list())
    veo_models = [m for m in models if "veo" in getattr(m, "name", "").lower()]
    if veo_models:
        for m in veo_models:
            print(f"  {m.name}")
    else:
        print("  (no veo models found — check billing/access)")
        print(f"  Total models available: {len(models)}")
except Exception as e:
    print(f"❌ models.list() failed: {e}")
    sys.exit(1)

# Step 4: try generate_videos (initiate only, don't wait)
print()
print("=== Test generate_videos call ===")
try:
    from google.genai import types
    operation = client.models.generate_videos(
        model=config.VEO_MODEL,
        prompt="A person says hello, portrait, 9:16",
        config=types.GenerateVideosConfig(aspect_ratio="9:16"),
    )
    print(f"✅ generate_videos initiated — operation name: {getattr(operation, 'name', 'unknown')}")
    print("   (not waiting for result — this was just a connectivity test)")
except Exception as e:
    print(f"❌ generate_videos failed: {e}")
