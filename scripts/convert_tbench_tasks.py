import shutil
from pathlib import Path

import toml
import typer
import yaml
from rich.console import Console

app = typer.Typer()
console = Console()


def convert_task(task_path: Path, output_dir: Path):
    """Converts a single terminal-bench task to the new sandboxes format."""
    task_name = task_path.name
    new_task_path = output_dir / task_name
    new_task_path.mkdir(exist_ok=True)

    # 1. Copy compatible directories and handle environment files
    
    # Create the 'environment' directory in the new structure
    env_dir = new_task_path / "environment"
    env_dir.mkdir(exist_ok=True)
    
    # Copy Dockerfile and docker-compose.yaml into the new 'environment' directory
    for env_file in ["Dockerfile", "docker-compose.yaml"]:
        src_file = task_path / env_file
        if src_file.exists():
            shutil.copy(src_file, env_dir / env_file)

    # Copy other directories as-is
    for dir_name in ["solution", "tests"]:
        src_dir = task_path / dir_name
        if src_dir.exists():
            shutil.copytree(src_dir, new_task_path / dir_name, dirs_exist_ok=True)

    # 2. Read old task.yaml
    yaml_path = task_path / "task.yaml"
    if not yaml_path.exists():
        console.print(f"[yellow]Skipping {task_name}: task.yaml not found.[/yellow]")
        return

    try:
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        console.print(f"[red]Error reading {yaml_path}: {e}[/red]")
        return

    # 3. Create instruction.md
    instruction_md_path = new_task_path / "instruction.md"
    instruction = data.get("instruction", "")
    instruction_md_path.write_text(instruction)

    # 4. Create task.toml
    task_toml = {
        "info": {
            "name": task_name,
            "author_name": data.get("author_name"),
            "author_email": data.get("author_email"),
            "difficulty": data.get("difficulty"),
            "category": data.get("category"),
            "tags": data.get("tags", []),
        },
        "agent": {"timeout_sec": data.get("max_agent_timeout_sec", 900.0)},
        "verifier": {"timeout_sec": data.get("max_test_timeout_sec", 180.0)},
    }
    toml_path = new_task_path / "task.toml"
    with open(toml_path, "w") as f:
        toml.dump(task_toml, f)

    console.print(f"[green]Successfully converted {task_name}[/green]")


@app.command()
def convert_tbench_tasks(
    input_dir: Path = typer.Option(
        ...,
        "--input-dir",
        "-i",
        help="Path to the root of terminal-bench/tasks directory.",
    ),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        "-o",
        help="Path to the output directory for converted sandboxes tasks.",
    ),
):
    """Converts a directory of terminal-bench tasks to the new sandboxes format."""
    if not input_dir.is_dir():
        console.print(f"[red]Error: Input directory {input_dir} not found.[/red]")
        raise typer.Exit(1)

    output_dir.mkdir(exist_ok=True)
    console.print(
        f"Starting conversion of tasks from [bold]{input_dir}[/bold] to [bold]{output_dir}[/bold]"
    )

    for task_path in sorted(input_dir.iterdir()):
        if task_path.is_dir():
            convert_task(task_path, output_dir)

    console.print("\n[bold green]Conversion complete![/bold green]")


if __name__ == "__main__":
    app()
