
import asyncio
import os
import sys
import json

sys.path.append(os.getcwd())

from backend.app.core.auth.security import decrypt_config

encrypted_payload = {
  "encrypted": "gAAAAABpYQUHgWosgeQvmmj4OPXFgBgQal12zgvtgyuJHAM2yFdP4IumSWr_6mfvVxL_NokTIwks4CCta9l3T9O0zY1tsEZnx-92CkAzhj2LSvvKaVRezDOCEGSG5-kVnDoSA3OlmXQ0TO4r5MFkekfDW8WqlFWmK34OIkcaD8cDQay1KK-YXhyvGW_Q88MUmVuf53nahMyukmkOHZMu6yRxJvz3TRKAFi48UyNiY4-y5WRW4FspdBZcf_BWPy7K0o2F-nXgMenERGnuMz6nxcaiVYlCbIkSQv2Tc0G745sdu4UBfEPmRc3z9X1q1ewcrnvZ3_P2mwb4cppusVn_U-MGTvazoubW9t23_Wb0QCJ_wAv8VJpMjqFMuGVq8cdlaatFHuzKV807pEjnyNn44nIm8lOHiTD_ozQwWaAHv_BLGZBRLb6q1kYOMleSyRVku0E05WRkhfUhXKyg1pXn8AMAUu7OKbWy3UTCOu0qfDyrAIeQnG5pXqomgGSfTzHxxAjLYHifJV24c1HeqO9XBbo_8gZ-3krPhxlWh8ToiB7Wb4us_lWwCdY="
}

try:
    decrypted = decrypt_config(encrypted_payload)
    print("--- DECRYPTED CONFIG ---")
    print(json.dumps(decrypted, indent=2))
except Exception as e:
    print(f"Decryption failed: {e}")
