"""Export public contracts without loading deployment secrets or connecting to a network."""
import json
from pathlib import Path
from typing import cast
from infradeck.api import create_app
from infradeck.config import Settings
from infradeck.identity import Identity
from infradeck.inventory import Inventory
settings = Settings.model_construct(origin='http://localhost:5173',production=False)
app = create_app(settings,cast(Identity,object()),cast(Inventory,object()))
Path('contracts/openapi.json').write_text(json.dumps(app.openapi(),indent=2,ensure_ascii=False)+'\n')
