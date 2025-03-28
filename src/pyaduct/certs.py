from pathlib import Path

from zmq.auth import create_certificates

from .utils import generate_random_md5


def generate_certificates(path: Path) -> Path:
    """Generate client and server CURVE certificate files"""
    random_dir = generate_random_md5()
    write_path = path / random_dir
    Path.mkdir(write_path, parents=True, exist_ok=True)
    server_cert_paths = create_certificates(write_path, "server")
    client_cert_paths = create_certificates(write_path, "client")
    return server_cert_paths, client_cert_paths
