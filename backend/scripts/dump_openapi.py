"""Writes the FastAPI app's OpenAPI schema to a file without needing a running
server or a live DB connection -- app.openapi() only introspects the route
definitions. Used by frontend/package.json's gen:api-types and by CI's
api-types drift check (both need the same schema, from the same source)."""

import json
import sys

from app.api.routes import app


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else "openapi.json"
    with open(out_path, "w") as f:
        json.dump(app.openapi(), f)


if __name__ == "__main__":
    main()
