# Auto-update: 2026-03-26 10:58:04 UTC
import base64
import random
import time
import requests
from seleniumbase import SB
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich import box

# ─────────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────────
ENCODED_CHANNEL = "YnJ1dGFsbGVz"
PLATFORM_URL    = "https://www.twitch.tv/{channel}"
PROXY           = False
SLEEP_RANGE     = (450, 800)
MAX_DRIVERS     = 2          # primary + secondary
ACCEPT_BTN      = 'button:contains("Accept")'
WATCH_BTN       = 'button:contains("Start Watching")'
STREAM_INDICATOR = "#live-channel-stream-information"

console = Console()


# ─────────────────────────────────────────────────────────────────
#  GEO RESOLVER
# ─────────────────────────────────────────────────────────────────
class GeoProfile:
    """Resolves geographic identity from public IP."""

    API_ENDPOINT = "http://ip-api.com/json/"

    def __init__(self):
        console.log("[bold cyan]🌍 Resolving geographic profile…[/]")
        data = requests.get(self.API_ENDPOINT, timeout=10).json()

        self.latitude      = data["lat"]
        self.longitude     = data["lon"]
        self.timezone      = data["timezone"]
        self.country_code  = data["countryCode"].lower()
        self.city          = data.get("city", "Unknown")
        self.isp           = data.get("isp", "Unknown")

    @property
    def geoloc(self) -> tuple:
        return (self.latitude, self.longitude)

    def display(self):
        table = Table(
            title="📡 Geo Profile",
            box=box.ROUNDED,
            title_style="bold green",
            border_style="bright_blue",
        )
        table.add_column("Property", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")
        table.add_row("Latitude",     str(self.latitude))
        table.add_row("Longitude",    str(self.longitude))
        table.add_row("Timezone",     self.timezone)
        table.add_row("Country Code", self.country_code)
        table.add_row("City",         self.city)
        table.add_row("ISP",          self.isp)
        console.print(table)


# ─────────────────────────────────────────────────────────────────
#  CHANNEL DECODER
# ─────────────────────────────────────────────────────────────────
def decode_channel(encoded: str) -> str:
    """Decodes a base64-encoded channel name."""
    decoded = base64.b64decode(encoded).decode("utf-8")
    console.log(f"[bold magenta]🔓 Channel decoded:[/] [underline]{decoded}[/]")
    return decoded


# ─────────────────────────────────────────────────────────────────
#  BROWSER HELPERS
# ─────────────────────────────────────────────────────────────────
def dismiss_dialogs(driver, label: str = "primary"):
    """Clicks through consent / start-watching overlays."""
    for selector, name in [(ACCEPT_BTN, "Accept"), (WATCH_BTN, "Start Watching")]:
        if driver.is_element_present(selector):
            console.log(f"  [yellow]⚡ [{label}] Clicking '{name}'[/]")
            driver.cdp.click(selector, timeout=4)
            driver.sleep(2)


def animated_sleep(driver, seconds: int, label: str = "Watching"):
    """Sleep with a pretty progress bar so the audience sees activity."""
    with Progress(
        SpinnerColumn("dots"),
        TextColumn(f"[bold green]{label}[/]"),
        BarColumn(bar_width=40, complete_style="green", finished_style="bright_green"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(label, total=seconds)
        for _ in range(seconds):
            time.sleep(1)
            progress.advance(task, 1)
    # keep the actual driver timer roughly in sync
    driver.sleep(1)


def open_stream(driver, url: str, geo: GeoProfile, label: str = "primary"):
    """Navigate to the stream and handle overlays."""
    console.log(f"[bold blue]🚀 [{label}] Navigating to stream…[/]")
    driver.activate_cdp_mode(url, tzone=geo.timezone, geoloc=geo.geoloc)
    driver.sleep(2)
    dismiss_dialogs(driver, label)
    animated_sleep(driver, 10, label=f"[{label}] Loading stream")
    dismiss_dialogs(driver, label)          # second pass after load


def spawn_secondary_driver(primary, url: str, geo: GeoProfile):
    """Opens a second undetectable browser instance on the same stream."""
    console.log("[bold yellow]🪟 Spawning secondary driver…[/]")
    secondary = primary.get_new_driver(undetectable=True)
    open_stream(secondary, url, geo, label="secondary")
    return secondary


# ─────────────────────────────────────────────────────────────────
#  MAIN LOOP
# ─────────────────────────────────────────────────────────────────
def run():
    console.print(
        Panel(
            "[bold bright_white]Automated Stream Viewer[/]\n"
            "[dim]Undetectable  •  Geo-spoofed  •  Multi-driver[/]",
            border_style="bright_magenta",
            box=box.DOUBLE_EDGE,
            padding=(1, 4),
        )
    )

    geo     = GeoProfile()
    geo.display()
    channel = decode_channel(ENCODED_CHANNEL)
    url     = PLATFORM_URL.format(channel=channel)

    console.print(
        Panel(f"[link={url}]{url}[/link]", title="🎯 Target", border_style="red")
    )

    cycle = 0
    while True:
        cycle += 1
        hold_time = random.randint(*SLEEP_RANGE)
        console.rule(f"[bold cyan]Cycle {cycle}  •  Hold {hold_time}s")

        with SB(
            uc=True,
            locale="en",
            ad_block=True,
            chromium_arg="--disable-webgl",
            proxy=PROXY,
        ) as browser:
            open_stream(browser, url, geo, label="primary")

            # Check if the stream is actually live
            if not browser.is_element_present(STREAM_INDICATOR):
                console.print(
                    "[bold red]❌ Stream appears offline. Exiting loop.[/]"
                )
                break

            console.log("[bold green]✅ Stream is LIVE[/]")
            dismiss_dialogs(browser, "primary")

            # --- secondary driver ---
            secondary = spawn_secondary_driver(browser, url, geo)

            # --- hold period ---
            animated_sleep(browser, hold_time, label="Holding viewers")

        console.log(f"[dim]♻️  Cycle {cycle} complete. Restarting…[/]\n")


# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    run()
