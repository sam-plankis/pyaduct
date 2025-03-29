from pathlib import Path

from zmq.auth import create_certificates

from .utils import generate_random_md5


def generate_certificates(path: Path) -> Path:
    """Generate client and server CURVE certificate files"""
    random_dir = generate_random_md5()
    write_path = path / random_dir
    Path.mkdir(write_path, parents=True, exist_ok=True)
    create_certificates(write_path, "server")
    create_certificates(write_path, "client")
    return write_path
