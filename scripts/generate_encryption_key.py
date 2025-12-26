
from cryptography.fernet import Fernet

def generate_key():
    key = Fernet.generate_key().decode()
    print("\n🔑 Your Permanent Encryption Key:")
    print("=" * 45)
    print(key)
    print("=" * 45)
    print("\n👉 To use this key:")
    print("1. Copy the key above.")
    print("2. Open your '.env' file in the project root.")
    print("3. Add the following line:")
    print(f"   ENCRYPTION_KEY={key}")
    print("\n⏳ Note: After setting this key, you must restart your application.")
    print("   Any servers added while using a temporary key will need to be re-added.")

if __name__ == "__main__":
    generate_key()
