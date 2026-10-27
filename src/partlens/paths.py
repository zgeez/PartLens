"""Read-only bundled resources are separate from persistent user state."""
from pathlib import Path
import os
import sys
import hashlib


def resource_root() -> Path:
    return Path(sys._MEIPASS) if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[2]


def app_home() -> Path:
    if value:=os.environ.get('PARTLENS_APP_HOME'):
        return Path(value).expanduser().resolve()
    return Path(os.environ.get('LOCALAPPDATA',Path.home()/'.local/share'))/'PartLens'


def example_bom(home: Path, *, synthetic: bool) -> Path:
    """Keep approved BOM inputs beyond a one-file extraction's lifetime, without overwriting history."""
    root=resource_root()
    source=root/('tests/fixtures/bom_kicad.csv' if synthetic else 'examples/easyduino-rp2040/bom.csv')
    data=source.read_bytes();folder=Path(home)/'examples'/hashlib.sha256(data).hexdigest()
    folder.mkdir(parents=True,exist_ok=True);target=folder/'bom.csv'
    if not target.exists():
        with target.open('xb') as f:f.write(data)
    if target.read_bytes()!=data:raise ValueError('Stored example input differs from its recorded digest; preserve and inspect it')
    license=(root/'licenses/PartLens-LICENSE.txt' if getattr(sys,'frozen',False) else root/'LICENSE') if synthetic else root/'examples/easyduino-rp2040/LICENSE-CERN-OHL-P-2.0.txt'
    notice=folder/'LICENSE.txt'
    if not notice.exists():
        with notice.open('xb') as f:f.write(license.read_bytes())
    return target
