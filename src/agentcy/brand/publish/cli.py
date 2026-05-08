"""Publish CLI commands."""
from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from agentcy.brand.cli_utils import emit, pick_format, status

publish_app = typer.Typer(help="Social publishing commands.")
queue_cli_app = typer.Typer(help="Queue management commands.")
console = Console()


@publish_app.command("post")
def post(
    brand: str = typer.Option(..., "--brand", "-b", help="Brand name"),
    platform: str | None = typer.Option(None, "--platform", "-p", help="Specific platform"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without posting"),
    all_pending: bool = typer.Option(False, "--all", help="Post all pending items"),
) -> None:
    """Post content from queue."""
    from agentcy.brand.publish.queue import get_next_pending, get_queue, update_queue_item
    from agentcy.brand.publish.rate_limit import can_post, record_post

    if all_pending:
        items = get_queue(brand, status="pending", platform=platform)
    else:
        item = get_next_pending(brand, platform=platform)
        items = [item] if item else []

    if not items:
        console.print("No pending items to post.")
        return

    for item in items:
        platform_name = item.platform or "twitter"

        console.print(f"\n[bold]Posting to {platform_name}[/bold]")
        console.print(f"Content: {item.content[:100]}...")

        if dry_run:
            console.print("[yellow]DRY RUN - not posting[/yellow]")
            continue

        if not can_post(platform_name, brand):
            console.print(f"[red]Rate limited for {platform_name}[/red]")
            continue

        # Get publisher
        from agentcy.brand.publish.platforms import get_publisher

        publisher = get_publisher(platform_name)
        if not publisher:
            console.print(f"[red]No publisher for {platform_name}[/red]")
            continue

        # Post
        result = publisher(item.content)

        if result.get("success"):
            console.print("[green]Posted successfully![/green]")
            if result.get("url"):
                console.print(f"URL: {result['url']}")

            update_queue_item(brand, item.id, status="posted")
            record_post(platform_name, brand)
        else:
            console.print(f"[red]Failed: {result.get('error')}[/red]")
            update_queue_item(brand, item.id, status="failed")


@publish_app.command("platforms")
def platforms(
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """List available platforms and their status."""
    from agentcy.brand.publish.platforms import list_platforms
    from agentcy.brand.publish.rate_limit import get_rate_status

    available = list_platforms()
    rate_status = get_rate_status()
    resolved_format = pick_format(format, default="table")

    if resolved_format == "table":
        table = Table(title="Platforms")
        table.add_column("Platform")
        table.add_column("Available")
        table.add_column("Posts/Hour")
        table.add_column("Limit")

        for platform in ["twitter", "linkedin", "instagram", "facebook", "threads", "youtube"]:
            is_available = platform in available
            status = "[green]Yes[/green]" if is_available else "[red]No[/red]"

            rate = rate_status.get(platform, {})
            posts = rate.get("posts_last_hour", 0)
            limit = rate.get("limit", "-")

            table.add_row(platform, status, str(posts), str(limit))

        console.print(table)
    else:
        data = {
            "available": available,
            "rate_status": rate_status,
        }
        emit(data, resolved_format)


# Queue subcommands
@queue_cli_app.command("add")
def queue_add(
    content: str = typer.Argument(..., help="Content to queue"),
    brand: str = typer.Option(..., "--brand", "-b", help="Brand name"),
    platform: str | None = typer.Option(None, "--platform", "-p", help="Target platform"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Add content to the queue."""
    from agentcy.brand.publish.queue import add_to_queue

    item = add_to_queue(brand, content, platform=platform)
    status(f"Added to queue: {item.id}")
    emit(item.model_dump(), format)


@queue_cli_app.command("list")
def queue_list(
    brand: str = typer.Option(..., "--brand", "-b", help="Brand name"),
    status: str | None = typer.Option(None, "--status", "-s", help="Filter by status"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """List queued content."""
    from agentcy.brand.publish.queue import get_queue

    items = get_queue(brand, status=status)
    resolved_format = pick_format(format, default="table")

    if resolved_format == "table":
        table = Table(title=f"Queue ({brand})")
        table.add_column("ID")
        table.add_column("Platform")
        table.add_column("Status")
        table.add_column("Content")
        table.add_column("Created")

        for item in items:
            table.add_row(
                item.id,
                item.platform or "-",
                item.status,
                item.content[:40] + "..." if len(item.content) > 40 else item.content,
                item.created_at[:10],
            )

        console.print(table)
    else:
        emit([item.model_dump() for item in items], resolved_format)


@queue_cli_app.command("show")
def queue_show(
    item_id: str = typer.Argument(..., help="Item ID"),
    brand: str = typer.Option(..., "--brand", "-b", help="Brand name"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Show a queue item."""
    from agentcy.brand.publish.queue import get_queue_item

    item = get_queue_item(brand, item_id)
    if not item:
        status(f"[red]Item not found: {item_id}[/red]")
        raise typer.Exit(1)

    emit(item.model_dump(), format, default="yaml")


@queue_cli_app.command("update")
def queue_update(
    item_id: str = typer.Argument(..., help="Item ID"),
    brand: str = typer.Option(..., "--brand", "-b", help="Brand name"),
    content: str | None = typer.Option(None, "--content", "-c", help="New content"),
    platform: str | None = typer.Option(None, "--platform", "-p", help="New platform"),
    status: str | None = typer.Option(None, "--status", "-s", help="New status"),
) -> None:
    """Update a queue item."""
    from agentcy.brand.publish.queue import update_queue_item

    item = update_queue_item(brand, item_id, content=content, platform=platform, status=status)
    if item:
        console.print(f"Updated: {item_id}")
    else:
        console.print(f"[red]Item not found: {item_id}[/red]")
        raise typer.Exit(1)


@queue_cli_app.command("remove")
def queue_remove(
    item_id: str = typer.Argument(..., help="Item ID"),
    brand: str = typer.Option(..., "--brand", "-b", help="Brand name"),
) -> None:
    """Remove an item from the queue."""
    from agentcy.brand.publish.queue import remove_from_queue

    if remove_from_queue(brand, item_id):
        console.print(f"Removed: {item_id}")
    else:
        console.print(f"[red]Item not found: {item_id}[/red]")
        raise typer.Exit(1)


@queue_cli_app.command("clear")
def queue_clear(
    brand: str = typer.Option(..., "--brand", "-b", help="Brand name"),
    status: str | None = typer.Option(None, "--status", "-s", help="Only clear this status"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Clear the queue."""
    from agentcy.brand.publish.queue import clear_queue

    if not force:
        msg = f"Clear queue for {brand}"
        if status:
            msg += f" (status={status})"
        if not typer.confirm(f"{msg}?"):
            raise typer.Abort()

    count = clear_queue(brand, status=status)
    console.print(f"Cleared {count} items")
