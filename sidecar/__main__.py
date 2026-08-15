"""Run the sidecar with validated configuration."""

import uvicorn

from .app import create_app
from .config import SidecarConfig


def main() -> None:
    config = SidecarConfig.from_env()
    uvicorn.run(create_app(config), host=config.bind_host, port=config.port, access_log=False)


if __name__ == "__main__":
    main()
