import subprocess
import sys

print("=== Running M11-HL Full Cycle ===")
print("\n[1/4] Generating M31 Funding Signals...")
subprocess.run([sys.executable, "exchanges/hyperliquid/m31_funding_generator.py"])

print("\n[2/4] Generating M35 EMA Signals...")
subprocess.run([sys.executable, "exchanges/hyperliquid/m35_ema_generator.py"])

print("\n[3/4] Generating M40 Pullback Signals...")
subprocess.run([sys.executable, "exchanges/hyperliquid/m40_generator.py"])

print("\n[4/4] Running M11-HL Allocator...")
subprocess.run([sys.executable, "exchanges/hyperliquid/m11_hl_allocator.py"])

print("\n=== Cycle Complete ===")
