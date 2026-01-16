import io
import pyzipper


def encrypt_to_zip(file_name: str, file_data: bytes, password: str) -> bytes:
    """
    Encrypts bytes into a ZIP file with AES-256 encryption.
    """
    if not password:
        raise ValueError("Password is required for encryption.")

    buffer = io.BytesIO()

    # Create AES-256 encrypted ZIP
    with pyzipper.AESZipFile(
        buffer, "w", compression=pyzipper.ZIP_LZMA, encryption=pyzipper.WZ_AES
    ) as zf:
        zf.setpassword(password.encode("utf-8"))
        zf.writestr(file_name, file_data)

    return buffer.getvalue()


def decrypt_from_zip(zip_data: bytes, password: str) -> dict[str, bytes]:
    """
    Decrypts a ZIP file and returns a dictionary {filename: content_bytes}.
    """
    if not password:
        raise ValueError("Password is required for decryption.")

    buffer = io.BytesIO(zip_data)

    files = {}
    with pyzipper.AESZipFile(
        buffer, "r", compression=pyzipper.ZIP_LZMA, encryption=pyzipper.WZ_AES
    ) as zf:
        zf.setpassword(password.encode("utf-8"))
        for name in zf.namelist():
            files[name] = zf.read(name)

    return files
