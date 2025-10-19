import shutil
from pathlib import Path

import toml
import typer
import yaml
from rich.console import Console
import tempfile

app = typer.Typer()
console = Console()


def convert_task(task_path: Path, output_dir: Path) -> bool:
    """Converts a single terminal-bench task to the new sandboxes format.

    Returns True on success, False otherwise. Work is done in a temp dir and
    only moved into place on success.
    """
    task_name = task_path.name

    # 1. Read old task.yaml first (fail fast before any copying)
    yaml_path = task_path / "task.yaml"
    if not yaml_path.exists():
        console.print(f"[yellow]Skipping {task_name}: task.yaml not found.[/yellow]")
        return False

    try:
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        console.print(f"[red]Error reading {yaml_path}: {e}[/red]")
        return False

    # 2. Create a temp dir to build the converted task
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"convert_{task_name}_", dir=output_dir))
    try:
        tmp_task_path = tmp_dir

        # 3. Write instruction.md
        instruction_md_path = tmp_task_path / "instruction.md"
        instruction = data.get("instruction", "")
        instruction_md_path.write_text(instruction)

        # 4. Create task.toml
        task_toml = {
            "metadata": {
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
        toml_path = tmp_task_path / "task.toml"
        with open(toml_path, "w") as f:
            toml.dump(task_toml, f)

        # 5. Copy environment (prefer full directory if present)
        src_env_dir = task_path / "environment"
        dst_env_dir = tmp_task_path / "environment"
        if src_env_dir.exists():
            shutil.copytree(src_env_dir, dst_env_dir, dirs_exist_ok=True)
        else:
            dst_env_dir.mkdir(exist_ok=True)
            for env_file in ["Dockerfile", "docker-compose.yaml"]:
                src_file = task_path / env_file
                if src_file.exists():
                    shutil.copy(src_file, dst_env_dir / env_file)

        # 6. Copy other directories as-is
        for dir_name in ["solution", "tests"]:
            src_dir = task_path / dir_name
            if src_dir.exists():
                shutil.copytree(src_dir, tmp_task_path / dir_name, dirs_exist_ok=True)

        # 7. Move temp dir into final location atomically
        final_task_path = output_dir / task_name
        if final_task_path.exists():
            shutil.rmtree(final_task_path)
        shutil.move(str(tmp_task_path), str(final_task_path))

        console.print(f"[green]Successfully converted {task_name}[/green]")
        return True

    except Exception as e:
        console.print(f"[red]Failed converting {task_name}: {e}[/red]")
        # Cleanup temp dir on any failure
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return False


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

    n_total = 0
    n_ok = 0
    failed: list[str] = []

    for task_path in sorted(input_dir.iterdir()):
        if task_path.is_dir():
            n_total += 1
            ok = convert_task(task_path, output_dir)
            if ok:
                n_ok += 1
            else:
                failed.append(task_path.name)

    console.print(
        f"\n[bold green]Conversion complete![/bold green] Converted {n_ok}/{n_total} tasks."
    )
    if failed:
        console.print(
            f"[yellow]Skipped/failed ({len(failed)}): {', '.join(sorted(failed))}[/yellow]"
        )


if __name__ == "__main__":
    app()
